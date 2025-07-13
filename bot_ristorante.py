import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)

NOME, TAVOLO, ORDINE, QUANTITA, VARIAZIONI, SALSE, VARIAZIONI_EXTRA, INSERISCI_VARIAZIONI = range(8)

ID_GRUPPO_CUCINA = -1002381060811
TOKEN = "7832282694:AAGu8F-73l7z-0gXpoZOvxwwNmLsYb1sI24"

utenti = {}
numero_ordine = 0

MENU = ["Mozzarella Stick", "Nuggets", "Panino con Salsiccia", "Patatine", "Patate Dolci", "Mix Frittini"]
SALSE_BASE = ["Ketchup", "Maionese", "Cheddar"]

def get_salse_per_pietanza(pietanza):
    if pietanza in ["Patatine", "Patate Dolci"]:
        return [s for s in SALSE_BASE if s != "Cheddar"]
    return SALSE_BASE

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    utenti[user_id] = {'ordine': []}
    await update.message.reply_text("🍽️ Inserisci il numero del tavolo:")
    return TAVOLO

async def ricevi_tavolo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    utenti[user_id]['tavolo'] = update.message.text
    utenti[user_id]['ordine'] = []

    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in MENU]
    keyboard.append([
        InlineKeyboardButton("🛑 Fine Ordine", callback_data="fine_ordine"),
        InlineKeyboardButton("❌ Annulla Ordine", callback_data="annulla_ordine")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 Seleziona una pietanza dal menu:", reply_markup=reply_markup)
    return ORDINE

async def seleziona_pietanza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scelta = query.data
    user_id = query.from_user.id

    if scelta == "fine_ordine":
        return await fine_ordine(update, context)
    elif scelta == "annulla_ordine":
        return await annulla(update, context)

    context.user_data['pietanza_selezionata'] = scelta

    keyboard = [[InlineKeyboardButton(str(i), callback_data=str(i))] for i in range(1, 6)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"🍴 Quante porzioni di {scelta}?", reply_markup=reply_markup)
    return QUANTITA

async def ricevi_quantita_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quantita = query.data
    pietanza = context.user_data.get('pietanza_selezionata')
    context.user_data['quantita'] = quantita

    keyboard = [
        [
            InlineKeyboardButton("Sì", callback_data="variazioni_si"),
            InlineKeyboardButton("No", callback_data="variazioni_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"❓ Variazioni per {pietanza}?", reply_markup=reply_markup)
    return VARIAZIONI

async def gestisci_variazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scelta = query.data
    pietanza = context.user_data.get('pietanza_selezionata')
    quantita = context.user_data.get('quantita')

    if scelta == "variazioni_si":
        context.user_data['salse_da_togliere'] = []
        salse_disponibili = get_salse_per_pietanza(pietanza)
        keyboard = []
        for s in salse_disponibili:
            testo = f"✅ {s}"  # inizialmente tutte selezionate con spunta verde
            keyboard.append([InlineKeyboardButton(testo, callback_data=f"salsa_{s}")])
        keyboard.append([InlineKeyboardButton("Fatto", callback_data="salse_fine")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("👉 Seleziona le salse da togliere (clicca per togliere/riaggiungere):", reply_markup=reply_markup)
        return SALSE

    elif scelta == "variazioni_no":
        utenti[query.from_user.id]['ordine'].append((pietanza, quantita, ""))
        return await mostra_menu(update, context)

async def seleziona_salsa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    salsa = query.data.replace("salsa_", "")
    toglier = context.user_data.get('salse_da_togliere', [])

    if salsa in toglier:
        toglier.remove(salsa)
    else:
        toglier.append(salsa)
    context.user_data['salse_da_togliere'] = toglier

    pietanza = context.user_data.get('pietanza_selezionata')
    salse_disponibili = get_salse_per_pietanza(pietanza)

    keyboard = []
    for s in salse_disponibili:
        if s in toglier:
            testo = f"❌ {s}"  # salsa esclusa = croce rossa
        else:
            testo = f"✅ {s}"  # salsa inclusa = spunta verde
        keyboard.append([InlineKeyboardButton(testo, callback_data=f"salsa_{s}")])
    keyboard.append([InlineKeyboardButton("Fatto", callback_data="salse_fine")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("👉 Seleziona le salse da togliere (clicca per togliere/riaggiungere):", reply_markup=reply_markup)

async def fine_salse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pietanza = context.user_data.get('pietanza_selezionata')
    quantita = context.user_data.get('quantita')
    salse_togliute = context.user_data.get('salse_da_togliere', [])

    variazioni = ""
    if salse_togliute:
        variazioni = ", ".join([f"-{s}" for s in salse_togliute])

    utenti[user_id]['ordine'].append((pietanza, quantita, variazioni))

    keyboard = [
        [
            InlineKeyboardButton("Sì", callback_data="variazioni_extra_si"),
            InlineKeyboardButton("No", callback_data="variazioni_extra_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("✍️ Vuoi aggiungere altre variazioni personalizzate? (es. aggiungi cipolla)", reply_markup=reply_markup)
    return VARIAZIONI_EXTRA

async def gestisci_variazioni_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scelta = query.data

    if scelta == "variazioni_extra_si":
        await query.edit_message_text("✍️ Scrivi qui le altre variazioni da aggiungere:")
        return INSERISCI_VARIAZIONI
    else:
        return await mostra_menu(update, context)

async def inserisci_variazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    variazioni_extra = update.message.text

    if utenti[user_id]['ordine']:
        piatto, q, variaz = utenti[user_id]['ordine'][-1]
        if variaz:
            variaz += ", " + variazioni_extra
        else:
            variaz = variazioni_extra
        utenti[user_id]['ordine'][-1] = (piatto, q, variaz)

    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in MENU]
    keyboard.append([
        InlineKeyboardButton("🛑 Fine Ordine", callback_data="fine_ordine"),
        InlineKeyboardButton("❌ Annulla Ordine", callback_data="annulla_ordine")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("✅ Variazioni salvate! Vuoi ordinare altro?", reply_markup=reply_markup)
    return ORDINE

async def mostra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in MENU]
    keyboard.append([
        InlineKeyboardButton("🛑 Fine Ordine", callback_data="fine_ordine"),
        InlineKeyboardButton("❌ Annulla Ordine", callback_data="annulla_ordine")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text("📋 Seleziona una pietanza dal menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("📋 Seleziona una pietanza dal menu:", reply_markup=reply_markup)
    return ORDINE

async def confermato_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception as e:
        logging.error(f"Errore eliminando messaggio: {e}")

async def fine_ordine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global numero_ordine
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not utenti[user_id]['ordine']:
        await query.edit_message_text("⚠️ Non hai aggiunto nessuna pietanza.")
        return await mostra_menu(update, context)

    numero_ordine += 1
    testo_ordine = f"🧾 Ordine #{numero_ordine}\nTavolo: {utenti[user_id]['tavolo']}\n\n"
    for i, (piatto, q, variaz) in enumerate(utenti[user_id]['ordine'], start=1):
        testo_ordine += f"{i}. {piatto} x{q}"
        if variaz:
            testo_ordine += f" ({variaz})"
        testo_ordine += "\n"

    # Bottoni per conferma ordine (da gruppo cucina)
    keyboard = [
        [InlineKeyboardButton("✅ Confermato", callback_data="confermato")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(ID_GRUPPO_CUCINA, testo_ordine, reply_markup=reply_markup)

    await query.edit_message_text("✅ Ordine inviato! Grazie.")
    utenti.pop(user_id, None)
    return ConversationHandler.END

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    utenti.pop(user_id, None)
    await query.edit_message_text("❌ Ordine annullato.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TAVOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_tavolo)],
            ORDINE: [CallbackQueryHandler(seleziona_pietanza)],
            QUANTITA: [CallbackQueryHandler(ricevi_quantita_callback)],
            VARIAZIONI: [CallbackQueryHandler(gestisci_variazioni)],
            SALSE: [
                CallbackQueryHandler(seleziona_salsa, pattern=r"^salsa_"),
                CallbackQueryHandler(fine_salse, pattern="^salse_fine$")
            ],
            VARIAZIONI_EXTRA: [CallbackQueryHandler(gestisci_variazioni_extra)],
            INSERISCI_VARIAZIONI: [MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_variazioni)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(confermato_callback, pattern="^confermato$"))
    app.run_polling()

if __name__ == '__main__':
    main()
