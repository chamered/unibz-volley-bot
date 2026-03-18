import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")
UNIBZ_COOKIE = os.environ.get("UNIBZ_COOKIE")

# Configura il logging per vedere eventuali errori nel terminale
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde al comando /start"""
    await update.message.reply_text("Ciao! Usa il comando /volley per vedere gli iscritti di oggi.")

async def check_volley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recupera i dati dal JSON in due step e li invia su Telegram"""
    await update.message.reply_text("Sto cercando l'evento e recuperando gli iscritti...")
    
    # URL di base
    base_url = "https://scub.unibz.it/api/events"
    
    # ⚠️ SE SERVE L'AUTENTICAZIONE, SCOMMENTA QUESTE RIGHE E INSERISCI IL TUO COOKIE
    # headers = {'Cookie': 'NOME_COOKIE=valore_del_cookie'} 
    # Per ora usiamo una variabile vuota se non hai ancora i cookie
    headers = {
        'Cookie': UNIBZ_COOKIE,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    } 

    try:
        # --- STEP 1: Trovare l'ID dell'evento ---
        response_list = requests.get(base_url, headers=headers)
        response_list.raise_for_status()
        data_list = response_list.json()
        
        event_id = None
        
        # Navighiamo la lista "events" del JSON che mi hai incollato
        for event in data_list.get('events', []):
            if "Volleyball Match & Training" in event.get('title', ''):
                event_id = event.get('id')
                break # Trovato l'evento, fermiamo il ciclo!
                
        if not event_id:
            await update.message.reply_text("Non ho trovato nessun evento di Pallavolo programmato.")
            return

        # --- STEP 2: Usare l'ID per prendere i dettagli (e i nomi) ---
        details_url = f"{base_url}/{event_id}"
        response_details = requests.get(details_url, headers=headers)
        response_details.raise_for_status()
        data_details = response_details.json()
        
        iscritti = []

        event_details = data_details.get('event', {})
        
        # ATTENZIONE: Qui sto tirando a indovinare la struttura del SECONDO JSON.
        # Immagino che dentro "bookings" ci sia un dizionario "user" con il "name".
        # Se la struttura è diversa, dovrai aggiustare queste 3 righe.
        for booking in event_details.get('bookings', []):
            # Prova a prendere il nome, se non lo trova mette "Nome Sconosciuto"
            nome_utente = booking.get('user', {}).get('name', 'Nome Sconosciuto')
            # Aggiungiamo solo chi è confermato per sicurezza
            if booking.get('status') == 'CONFIRMED':
                iscritti.append(nome_utente)
        
        # --- PREPARAZIONE DEL MESSAGGIO ---
        if len(iscritti) > 0:
            messaggio = f"🏐 **Volleyball Match & Training**\n"
            messaggio += f"ID Evento: `{event_id}`\n"
            messaggio += f"Totale iscritti: {len(iscritti)}\n\n"
            
            for i, nome in enumerate(iscritti, 1):
                messaggio += f"{i}. {nome}\n"
        else:
            messaggio = "Ho trovato l'evento, ma la lista iscritti sembra vuota o non accessibile."
            
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except requests.exceptions.HTTPError as err:
        # Gestione specifica se il sito ci blocca (es. Errore 401 o 403)
        await update.message.reply_text(f"⚠️ Errore di connessione al sito. Forse serve il login? Dettaglio: `{err}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Si è verificato un errore:\n`{e}`", parse_mode='Markdown')

if __name__ == '__main__':
    # Crea l'applicazione del bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Associa i comandi alle funzioni
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("volley", check_volley))
    
    print("Bot in esecuzione! Vai su Telegram e scrivigli /start")
    
    # Mantiene il bot in ascolto
    app.run_polling()