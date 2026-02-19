# -*- coding: utf-8 -*-
# bot_la.py - L&A INSTITUTIONAL TERMINAL v5.1 HYBRID MODE + LSTM LITE

import time
import requests
import ccxt
import config_la
import json
import os
import logging
import asset_list
import engine_la
import shutil
import traceback
from google import genai
import pandas_ta as ta   
import xgboost           
from asset_list import ASSET_MAPPING
from institutional_filters import InstitutionalFilters
from collections import deque
from engine_la import EngineLA
from brain_la import BrainLA
from manager_la import ManagerLA
from performer_la import PerformerLA
from feedback_engine import FeedbackEngine
from telegram_alerts_la import TelegramAlerts
from position_tracker_la import PositionTracker
from trade_manager_advanced_la import TradeManager
from learning_engine_advanced_la import LearningEngineAdvanced
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

# --- Setup logging SOLO su file! Nessun print/stream verso console ---
logger = logging.getLogger("bot_la")
logger.setLevel(logging.INFO)
LOG_FORMAT = '[%(asctime)s][%(levelname)s] %(message)s'
if not logger.hasHandlers():
    file_handler = logging.FileHandler('sniper_history.log')
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

# ============================================================================
# CONFIGURAZIONE KRAKEN
# ============================================================================

KRAKEN_API_KEY = config_la.KRAKEN_KEY
KRAKEN_API_SECRET = config_la.KRAKEN_SECRET
KRAKEN_FUTURES_API_KEY = config_la.KRAKEN_FUTURES_API_KEY
KRAKEN_FUTURES_API_SECRET = config_la.KRAKEN_FUTURES_API_SECRET

exchange_spot = ccxt.kraken({
    'apiKey': KRAKEN_API_KEY,
    'secret': KRAKEN_API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

exchange_futures = ccxt.krakenfutures({
    'apiKey': KRAKEN_FUTURES_API_KEY,
    'secret': KRAKEN_FUTURES_API_SECRET,
    'options': {'defaultType': 'futures'},
    'enableRateLimit': True,
})

exchange = exchange_spot

# ============================================================================
# CONFIGURAZIONE CORE
# ============================================================================

API_KEY_GEMINI = config_la.GEMINI_KEY
os.environ["GOOGLE_API_KEY"] = config_la.GOOGLE_API_KEY
client_gemini = genai.Client(api_key=config_la.GOOGLE_API_KEY)
TELEGRAM_TOKEN = config_la.TELEGRAM_TOKEN
CHAT_ID = config_la.CHAT_ID
FILE_POSIZIONI = "posizioni_aperte.json"
SOGLIA_VOTO_ENTRY = 6.0

ultimo_stato_ia = {}
macro_status = {
    "dxy": 0.0,
    "nasdaq": 0.0,
    "sentiment": "NEUTRAL",
    "next_run": 0,
    "last_prices": {},
    "voti_ia": {}
}

logs_queue = deque(maxlen=15)
console = Console()

# ============================================================================
# INIZIALIZZAZIONE MOTORI
# ============================================================================

alerts = TelegramAlerts(bot_token=TELEGRAM_TOKEN, chat_id=CHAT_ID)
position_tracker = PositionTracker(file_posizioni=FILE_POSIZIONI)
feedback_engine = FeedbackEngine()

engine = EngineLA(exchange_id='kraken')
brain = BrainLA(api_key=API_KEY_GEMINI, feedback_engine=feedback_engine)
manager = ManagerLA(account_balance=100.0, risk_per_trade=0.03)
learning_engine = LearningEngineAdvanced(position_tracker=position_tracker)

performer = PerformerLA(exchange_spot, live_mode=False, telegram_bot=alerts)
trade_manager = TradeManager(position_tracker, alerts, performer)

whitelist = asset_list.ATTIVI
from asset_list import get_trading_ticker_and_type

screening_data = {}

for coin in whitelist:
    ticker, is_futures, is_spot = get_trading_ticker_and_type(coin)
    screening_data[coin] = {
        'voto': 0,
        'prezzo': 0,
        'whale': '...',
        'status': 'IDLE',
        'poc': 0,
        'vwap': 0,
        'cvd': 0,
        'vsa': 'NORMAL',
        'vol_ratio': 1.0,
        'trend_1d': 'NEUTRAL',
        'lstm_prediction': 'N/A',
        'market_type': 'FUTURES' if is_futures else ('SPOT' if is_spot else 'UNKNOWN'),
        'ticker': ticker
        # puoi aggiungere in futuro ulteriori chiavi qui!
    }

# (DEBUG opzionale: stampa la screening_data iniziale)
# import pprint
# pprint.pprint(screening_data)
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_event(msg, exc=None):
    logs_queue.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    if exc:
        logger.error(f"{msg}\n{traceback.format_exc()}")
    else:
        logger.info(msg)

def carica_posizioni():
    try:
        return position_tracker.ottieni_tutte_posizioni()
    except Exception:
        log_event("Errore caricamento posizioni", exc=True)
        return {}

def salva_posizioni():
    try:
        position_tracker.salva_posizioni()
    except Exception:
        log_event("Errore salvataggio posizioni", exc=True)

def format_price(p):
    try:
        if isinstance(p, (tuple, list)):
            p = p[0]
        if p is None or p == 0:
            return "0.00"
        if p >= 1000:
            return f"{p:,.2f}"
        if p >= 1:
            return f"{p:.4f}"
        return f"{p:.8f}"
    except Exception:
        log_event("Errore format_price", exc=True)
        return "NA"

# ============================================================================
# INTERFACCIA GRAFICA (Rich UI)
# ============================================================================

def genera_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", ratio=1)
    )
    return layout

def aggiorna_interfaccia(layout, posizioni):
    try:
        header_text = Text(
            f"🤖 L&A INSTITUTIONAL v5.1 HYBRID+LSTM LITE | SENT: {macro_status['sentiment']} | "
            f"DXY: {macro_status['dxy']:.2f} | NASDAQ: {macro_status['nasdaq']:.2f}",
            style="bold white on blue"
        )
        layout["header"].update(
            Panel(header_text, subtitle=f"Prossimo Scan: {macro_status['next_run']}")
        )

        # --- Tabella Asset ---
        table = Table(expand=True, border_style="bright_blue", box=None)
        table.add_column("ASSET", style="cyan", justify="left")
        # AGGIUNTA COLONNA TIPO
        table.add_column("TIPO", style="dim white", justify="center")
        table.add_column("PREZZO", style="yellow", justify="right")
        table.add_column("VOTO IA", style="bold magenta", justify="center")
        table.add_column("TREND 1D", style="green", justify="center")
        table.add_column("LSTM", style="bold cyan", justify="center")
        table.add_column("VWAP", style="blue", justify="right")
        table.add_column("CVD", style="magenta", justify="right")
        table.add_column("STATUS", style="italic white")

        for coin in whitelist:
            d = screening_data.get(coin, {})
            voto_str = f"⭐ {d.get('voto', 0):.1f}" if d.get('voto', 0) > 0 else "-"
            p_str = format_price(d.get('prezzo', 0))
            trend_str = d.get('trend_1d', 'NEUTRAL')
            lstm_str = d.get('lstm_prediction', 'N/A')
            vwap_str = format_price(d.get('vwap', 0))
            cvd_str = f"{d.get('cvd', 0):.2f}"
            
            # Recupero e formattazione TIPO (SPOT/FUTURES)
            m_type = d.get('market_type', 'UNK')
            type_styled = f"[{'bold gold1' if m_type=='SPOT' else 'bold orchid'}]{m_type}[/]"

            table.add_row(
                coin,
                type_styled,
                f"${p_str}",
                voto_str,
                trend_str,
                lstm_str,
                vwap_str,
                cvd_str,
                d.get('status', 'IDLE')
            )
        layout["main"].update(table)

        # --- POS APERTE ---
        pos_items = []
        for k, v in posizioni.items():
            try:
                nome_breve = next((key for key, val in asset_list.ASSET_MAPPING.items() if val == k), k)
                
                # Recupero il market_type salvato nello screening_data
                m_type = screening_data.get(nome_breve, {}).get('market_type') or screening_data.get(k, {}).get('market_type', 'UNK')
                color_type = "gold1" if m_type == 'SPOT' else "orchid"
                
                p_att = screening_data.get(nome_breve, {}).get('prezzo', 0)
                if p_att == 0: p_att = screening_data.get(k, {}).get('prezzo', 0)
                if p_att == 0:
                    p_att = macro_status.get("last_prices", {}).get(nome_breve, 0) or macro_status.get("last_prices", {}).get(k, 0)
                
                if isinstance(p_att, (tuple, list)): p_att = p_att[0]
                p_ent = v.get('p_entrata', 0)
                if isinstance(p_ent, (tuple, list)): p_ent = p_ent[0]
                
                direzione = v.get('direzione', 'LONG').upper()
                sl_val = v.get('sl', "None")
                tp_val = v.get('tp', "None")
                fase = v.get('fase', 0)

                # Calcolo PnL
                if p_att > 0 and p_ent > 0:
                    diff = ((p_att - p_ent) / p_ent * 100) if direzione == 'LONG' else ((p_ent - p_att) / p_ent * 100)
                    color_pnl = "green" if diff > 0.05 else "red" if diff < -0.05 else "yellow"
                    bullet = f"[bold {color_pnl}]●[/bold {color_pnl}]"
                    pnl_str = f"[{color_pnl}]{diff:>+6.2f}%[/{color_pnl}]"
                else:
                    pnl_str = "[white] 0.00%[/white]"
                    bullet = "[white]○[/white]"

                fase_labels = ["MONITORAGGIO", "BREAK EVEN", "MOON PHASE", "SCUDO"]
                fase_idx = int(fase[0]) if isinstance(fase, (list, tuple)) else int(fase)
                fase_str = fase_labels[min(fase_idx, 3)]
                
                ticker_display = nome_breve if len(nome_breve) < 10 else k.split('/')[0]

                # RIGA AGGIORNATA CON TIPO MERCATO
                riga = (
                    f"{bullet} {ticker_display:<8} [{color_type}]{m_type:^7}[/] | {direzione:<5} | PnL: {pnl_str} | "
                    f"Entr: {format_price(p_ent)} | SL: {sl_val} | TP: {tp_val} | {fase_str}"
                )
                pos_items.append(riga)
            except Exception:
                logger.exception(f"Errore visualizzazione posizione: {k}")

        pos_str = "\n".join(pos_items) if pos_items else "Nessuna operazione attiva."
        log_str = "\n".join(logs_queue)
        layout["footer"].split_row(
            Layout(Panel(pos_str, title="[bold green]ACTIVE TRADES[/bold green]", border_style="green"), ratio=3),
            Layout(Panel(log_str, title="[bold white]SYSTEM LOGS[/bold white]", border_style="white"), ratio=2)
        )
    except Exception:
        logger.exception("Errore aggiornamento interfaccia")
def scrivi_scatola_nera(asset, input_motore, output_brain):
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "asset": asset,
        "input_engine": input_motore,
        "output_brain": output_brain
    }
    try:
        with open("scatola_nera.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.exception("Errore scrittura scatola_nera")

# ============================================================================
# CICLO OPERATIVO PRINCIPALE
# ============================================================================

def estrai_float(val):
    if isinstance(val, (tuple, list)):
        return val[0]
    return val

def esegui_ciclo(posizioni_aperte, layout):
    global screening_data, macro_status, ultimo_stato_ia, exchange_spot, exchange_futures
    log_event("🔍 Analisi Asset in corso...")

    try:
        m_data, sentiment = engine.get_macro_data()
        macro_status["dxy"] = m_data.get("DXY", {}).get("price", 0)
        macro_status["nasdaq"] = m_data.get("NASDAQ", {}).get("price", 0)
        macro_status["sentiment"] = sentiment
        macro_status.setdefault("last_prices", {})
        macro_status.setdefault("voti_ia", {})
    except Exception:
        log_event("Errore dati macro", exc=True)

    # --- CICLO ANALISI ASSET ---
    for coin in asset_list.ATTIVI:
        # Recupero corretto a 3 variabili (trading_ticker, is_futures, is_spot)
        # Questo risolve lo sfasamento che mandava BTC/ETH sui futures
        trading_ticker, is_futures, is_spot = asset_list.get_trading_ticker_and_type(coin)
        
        # Smistamento Exchange basato sulla classificazione reale in asset_list.py
        if is_futures:
            current_exchange = exchange_futures
            market_mode = 'FUTURES'
        elif is_spot:
            current_exchange = exchange_spot
            market_mode = 'SPOT'
        else:
            logger.warning(f"[SKIP] {coin} non classificato correttamente in asset_list.py")
            continue

        # 1. FETCH TICKER (Ora XXBTZUSD passerà correttamente da exchange_spot)
        try:
            t_fast = current_exchange.fetch_ticker(trading_ticker)
            price = t_fast.get('last', None)
            
            if price is None or price == 0:
                # Prova fallback se 'last' è vuoto
                price = t_fast.get('close', t_fast.get('bid', 0))
                
            if price == 0:
                logger.warning(f"[SKIP] {trading_ticker} non ha fornito un prezzo valido")
                continue
                
            # Qui usiamo market_mode invece di ricalcolare 'SPOT' if is_spot
            logger.info(f"🔍 Analisi {trading_ticker} | Prezzo: {price} | Mode: {market_mode}")
            
        except Exception as e:
            logger.error(f"[ERROR] Errore critico recupero ticker per {trading_ticker}: {e}")
            continue

        # 2. MULTITIMEFRAME
        dati = engine.get_dati_multitimeframe(trading_ticker, exchange=current_exchange)
        if not dati:
            logger.warning(f"[SKIP] {trading_ticker} - dati multitimeframe insufficienti")
            continue

        # 3. MARKET CONTEXT
        contesto = engine.get_market_context(trading_ticker, exchange=current_exchange)
        # 4. DATI LSTM
        dati_storici_lstm = engine.get_dati_storici_per_lstm(trading_ticker, exchange=current_exchange)
        guardrail = engine.get_guardrail_logico(dati, contesto)

       
       # 5. FILTRI ISTITUZIONALI + FUNDING
        inst_filters = InstitutionalFilters()
        analisi_ist = {}
        funding_rate = 0.0
        
        try:
            analisi_ist = inst_filters.get_institutional_analysis(trading_ticker)
        except Exception:
            logger.exception(f"IstFilter fail: {trading_ticker}")

        # Sostituiamo 'if is_perp' con 'if is_futures' per coerenza con Kraken Futures
        if is_futures: 
            try:
                # Usiamo l'analisi già fatta sopra senza chiamare l'API due volte
                if isinstance(analisi_ist, dict):
                    funding_rate = analisi_ist.get('funding_rate', 0)
                else:
                    funding_rate = 0
                    logger.warning(f"[PATCH] funding_rate non disponibile per {trading_ticker}")
            except Exception:
                logger.exception(f"Funding fail: {trading_ticker}")
        
        dati['funding_rate'] = funding_rate
        
        
        # 6. ANALISI IA - VERSIONE CORRETTA
        logger.info(f"[DEBUG_IA_INPUT] {trading_ticker} | dati={dati} | contesto={contesto}")
        
        try:
            # Protezione contro dati mancanti per evitare crash
            contesto_safe = contesto if contesto is not None else {}
            lstm_safe = dati_storici_lstm if dati_storici_lstm is not None else []
            guardrail_safe = guardrail if guardrail is not None else {'voto_minimo': 0, 'voto_massimo': 10, 'ragioni': []}
            print("========= ARRIVATO PRIMA DELLA IA =========")
            analisi_ia = brain.analizza_asset(
                dati, m_data, sentiment, analisi_ist,
                contesto_istituzionale=contesto_safe,
                posizione_attuale=posizioni_aperte.get(trading_ticker),
                guardrail=guardrail_safe,
                dati_storici_lstm=lstm_safe
            )
            print("========= USCITO DALLA IA ============")       
        except Exception as e:
            logger.error(f"❌ Errore Brain su {trading_ticker}: {e}")
            analisi_ia = {'voto': 0, 'direzione': 'FLAT', 'ragionamento_mentore': 'Errore IA'}

        if not analisi_ia:
            analisi_ia = {'voto': 0, 'direzione': 'FLAT'}
            
        voto = estrai_float(analisi_ia.get('voto', 0))
        prezzo_real = estrai_float(dati.get('prezzo_real', price)) 
        
        macro_status["last_prices"][coin] = prezzo_real
        macro_status["voti_ia"][coin] = f"{voto:.1f}/10"
        
        # Gestione campo LSTM per la tabella
        lstm_field = "N/A"
        pred_data = analisi_ia.get('lstm_predizione')
        if isinstance(pred_data, dict):
            lstm_field = f"{pred_data.get('direzione', 'N/A').upper()} ({pred_data.get('confidence', 0):.1f}%)"
        elif isinstance(pred_data, str):
            lstm_field = pred_data

        cvd_field = contesto_safe.get('cvd', 0)
        mtf = dati.get('multitimeframe', {})

        # AGGIORNAMENTO TABELLA
        screening_data[coin] = {
            'voto': voto,
            'prezzo': prezzo_real,
            'whale': 'NORMAL',
            'status': 'ANALISI OK',
            'poc': estrai_float(contesto_safe.get('poc', 0)),
            'vwap': estrai_float(contesto_safe.get('vwap', 0)),
            'vsa': dati.get('vsa_status', 'NORMAL'),
            'trend_1d': mtf.get('1D', {}).get('trend', 'NEUTRAL'),
            'lstm_prediction': lstm_field,
            'cvd': cvd_field,
            'market_type': 'SPOT' if is_spot else 'FUTURES'
        }

        logger.info(f"[DASH] {trading_ticker} | Voto: {voto} | LSTM: {lstm_field}")
        # 8. SCATOLA NERA
        scrivi_scatola_nera(trading_ticker, dati, analisi_ia)

        # --- PATCH: Moon Phase ---
        if trading_ticker in posizioni_aperte:
            pos = posizioni_aperte[trading_ticker]
            p_att = prezzo_real
            
            # MODIFICA ESSENZIALE: Passiamo modalita ed exchange corretti
            azioni = trade_manager.aggiorna_tutte_posizioni(
                {trading_ticker: p_att}, 
                modalita=market_mode, 
                exchange=current_exchange
            )
            
            if trading_ticker in azioni and any(x in azioni[trading_ticker] for x in ["SL_TOCCATO", "TP_RAGGIUNTO"]):
                posizioni_aperte[trading_ticker]['_da_chiudere'] = True
            
            entry = estrai_float(pos.get('p_entrata', 0))
            tp = estrai_float(pos.get('tp', 0))
            fase = pos.get('fase', 0)

            # ... resto della logica progressione (Fase 1 e 2) invariata ...

            # Controllo validità dati per evitare errori matematici
            # --- INIZIO BLOCCO CORRETTO ---
            if tp is not None and entry is not None and tp > 0 and entry != 0 and p_att is not None and p_att != 0:
                try:
                    prog = abs(p_att - entry) / abs(tp - entry) * 100
                    
                    # --- FASE 1: 50% PROGRESSIONE (STOP LOSS A PAREGGIO) ---
                    if 50 <= prog < 100 and fase < 1:
                        performer.aggiorna_ordine_sl(trading_ticker, entry, modalita=market_mode)
                        posizioni_aperte[trading_ticker].update({'sl': entry, 'fase': 1})
                        
                        msg = (
                            f"🛡️ <b>FASE 1 ATTIVA</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Asset: <b>{trading_ticker}</b>\n"
                            f"Stato: <b>50% Target Raggiunto</b>\n"
                            f"Azione: <b>SL spostato a Pareggio ({entry})</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"<i>Capitale protetto, ora lasciamo correre...</i>"
                        )
                        alerts.invia_messaggio(msg)
                        logger.info(f"[ANDREA] Notifica Fase 1 inviata per {trading_ticker}")

                    # --- FASE 2: 100% PROGRESSIONE (MOON PHASE) ---
                    elif prog >= 100 and fase < 2:
                        performer.rimuovi_tp(trading_ticker, modalita=market_mode)
                        posizioni_aperte[trading_ticker].update({'tp': None, 'fase': 2})
                        
                        msg = (
                            f"🌙 <b>FASE 2: MOON PHASE</b> 🚀\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Asset: <b>{trading_ticker}</b>\n"
                            f"Stato: <b>100% Target Raggiunto!</b>\n"
                            f"Azione: <b>TP RIMOSSO - Trailing Attivo</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"<i>Puntiamo alla Luna! Non si chiude più.</i>"
                        )
                        alerts.invia_messaggio(msg)
                        logger.info(f"[ANDREA] Notifica Fase 2 inviata per {trading_ticker}")

                except ZeroDivisionError:
                    prog = 0
                except Exception as e:
                    logger.error(f"Errore moon phase logic: {e}")
                    prog = 0
            else:
                # Se non c'è una posizione, resettiamo prog a 0 e andiamo avanti
                prog = 0
                logger.debug(f"Nessuna posizione attiva per {trading_ticker}")
            # --- FINE BLOCCO CORRETTO ---
        elif voto is not None and voto >= SOGLIA_VOTO_ENTRY and prezzo_real is not None and prezzo_real > 0:
            sl_ia = estrai_float(analisi_ia.get('sl', 0))
            if sl_ia is not None and sl_ia > 0:
                size = manager.calculate_position_size(prezzo_real, sl_ia, voto, dati.get('atr', 100))
                if size > 0:
                    try:
                        # Qui usiamo market_mode (dinamica) invece di 'SPOT' (fisso)
                        apertura = trade_manager.apri_posizione_market(
                            asset=trading_ticker, direzione=analisi_ia.get('direzione', 'LONG'),
                            entry_price=prezzo_real, size=size, sl=sl_ia, tp=estrai_float(analisi_ia.get('tp', 0)),
                            voto=voto, modalita=market_mode,
                            funding_rate=funding_rate, exchange=current_exchange
                        )
                        if apertura:
                            posizioni_aperte[trading_ticker] = apertura
                            salva_posizioni()
                            try:
                                alerts.posizione_aperta(
                                    asset=trading_ticker,
                                    direzione=analisi_ia.get('direzione', 'LONG'),
                                    entry_price=prezzo_real,
                                    size=size,
                                    sl=sl_ia,
                                    tp=estrai_float(analisi_ia.get('tp', 0)),
                                    voto=voto,
                                    lstm_pred=analisi_ia.get('lstm_predizione'),
                                    modalita=market_mode, # Aggiornato anche qui
                                    funding_rate=funding_rate
                                )
                                logger.info(f"[NOTIF] Telegram APERTURA posizione: {trading_ticker}")
                            except Exception:
                                logger.exception("Telegram apertura posizione fail")
                    except Exception:
                        logger.exception(f"Errore apertura posizione: {trading_ticker}")
            else:
                logger.warning(f"[PATCH] SL IA None o <= 0 per entry: sl_ia={sl_ia}, ticker={trading_ticker}")
        else:
            logger.warning(f"[PATCH] Condizione entry non valida: voto={voto}, prezzo_real={prezzo_real}, ticker={trading_ticker}")
    # Fuori dal ciclo for!
    try:
        da_rimuovere = [k for k, v in posizioni_aperte.items() if v.get('_da_chiudere')]
        for a in da_rimuovere:
            logger.info(f"🧹 Cleanup posizione chiusa: {a}")
            del posizioni_aperte[a]
        
        if da_rimuovere:
            salva_posizioni()
            
        aggiorna_interfaccia(layout, posizioni_aperte)
    except Exception:
        logger.exception("Errore cleanup ciclo")

# ============================================================================
# AVVIO SISTEMA
# ============================================================================

if __name__ == "__main__":
    try:
        # Pulisce il terminale all'avvio
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Inizializzazione dati
        posizioni = carica_posizioni()
        layout = genera_layout()
        
        # Notifica avvio
        alerts.sistema_online(soglia_entry=SOGLIA_VOTO_ENTRY, modalita="HYBRID")
        
        # Avvio interfaccia Live (senza screen=True per evitare bug grafici)
        with Live(layout, refresh_per_second=1): 
            while True:
                try:
                    # 1. ESEGUI PRIMA IL CICLO (Scarica i prezzi da Kraken)
                    # Passiamo 'layout' così esegui_ciclo può aggiornare i log a video
                    esegui_ciclo(posizioni, layout)
                    
                    # 2. AGGIORNA L'INTERFACCIA (Ora i prezzi sono reali)
                    aggiorna_interfaccia(layout, posizioni)
                    
                except Exception as e:
                    logger.exception(f"Errore durante l'esecuzione del ciclo: {e}")
                
                # --- CICLO DI ATTESA (COUNTDOWN) ---
                logger.info("--- ATTESA DI 120 SECONDI PRIMA DEL PROSSIMO SCAN ---")
                for i in range(120, 0, -1):
                    macro_status["next_run"] = f"ANALISI TRA {i}s"
                    try:
                        # Continuiamo ad aggiornare la tabella durante il countdown
                        aggiorna_interfaccia(layout, posizioni)
                    except Exception:
                        pass
                    time.sleep(1)
                
                macro_status["next_run"] = "RIAVVIO..."
                try:
                    aggiorna_interfaccia(layout, posizioni)
                except Exception:
                    pass
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n⛔ Bot arrestato dall'utente (CTRL+C).")
        try:
            alerts.sistema_offline()
        except Exception:
            pass
            
    except Exception as e:
        logger.critical(f"ERRORE CRITICO NEL MAIN: {e}")
        traceback.print_exc()
        try:
            alerts.errore_critico(traceback.format_exc())
        except Exception:
            pass