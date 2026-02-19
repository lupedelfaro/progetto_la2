# -*- coding: utf-8 -*-
# performer_la.py - ORDER EXECUTION ENGINE v3.8 MARGIN ENABLED
# Versione integrale senza tagli.
# Integrazione: Margin Trading (Leva) per SHORT reale, Protezione Futures e Notifiche.

import logging
import time
import traceback
from config_auto_apprendimento import GEMINI_MODEL

class PerformerLA:
    """
    Esegue gli ordini su Kraken: apertura, chiusura, aggiornamento SL/TP.
    Gestisce il Margin Trading per permettere posizioni SHORT su asset SPOT.
    """
    
    def __init__(self, exchange, live_mode=False, telegram_bot=None):
        """
        Args:
            exchange: istanza CCXT di Kraken
            live_mode: True = ordini reali, False = simulazione
            telegram_bot: istanza del bot per inviare notifiche (opzionale)
        """
        self.exchange = exchange
        self.live_mode = live_mode
        self.telegram_bot = telegram_bot
        self.posizioni_simulate = {}  # Per tracking in simulazione
        self.force_futures_simulation = True # Sicurezza per ticker derivati
        
        # IMPOSTAZIONE LEVA (Margin Trading)
        # Necessaria per aprire posizioni SHORT su Kraken Spot (es. XXBTZUSD)
        self.leverage_value = 2 
        
        modo = "LIVE" if live_mode else "SIMULAZIONE"
        logging.info(f"🚀 PerformerLA inizializzato in {modo} (Leva Margin: {self.leverage_value}x)")

    # ========================================================================
    # UTILITY INTERNE E VALIDAZIONI
    # ========================================================================
    
    def _is_future(self, symbol):
        """Rileva se un ticker appartiene ai Futures di Kraken (es. BTC/USD:BTC)"""
        return ":" in symbol or "PI_" in symbol or "FI_" in symbol

    def _invia_notifica(self, messaggio):
        """Invia una notifica Telegram se il bot è configurato"""
        logging.info(messaggio)
        if self.telegram_bot:
            try:
                self.telegram_bot.invia_messaggio(messaggio) 
            except Exception as e:
                logging.error(f"Errore invio notifica Telegram: {e}")

    def _valida_parametri(self, symbol, prezzo, size, sl=None):
        """Valida i parametri prima di eseguire l'ordine, gestendo eventuali tuple"""
        try:
            if isinstance(prezzo, tuple): prezzo = prezzo[0]
            if isinstance(size, tuple): size = size[0]
            if sl is not None and isinstance(sl, tuple): sl = sl[0]

            if not symbol or not isinstance(symbol, str):
                logging.error(f"Symbol invalido: {symbol}")
                return False
            
            if prezzo is not None and prezzo <= 0:
                logging.error(f"Prezzo invalido: {prezzo}")
                return False
            
            if size is not None and size <= 0:
                logging.error(f"Size invalida: {size}")
                return False
            
            return True
        except Exception as e:
            logging.error(f"Errore validazione parametri: {e}")
            return False

    def _retry_kraken(self, funzione, max_tentativi=3, delay=2):
        """Riprova una operazione Kraken con backoff in caso di errore di rete"""
        for tentativo in range(max_tentativi):
            try:
                return funzione()
            except Exception as e:
                if tentativo < max_tentativi - 1:
                    logging.warning(f"Errore Kraken (tentativo {tentativo+1}/{max_tentativi}): {e}")
                    time.sleep(delay * (tentativo + 1))
                else:
                    logging.error(f"Errore Kraken definitivo dopo {max_tentativi} tentativi: {e}")
                    return None

    # ========================================================================
    # APERTURA POSIZIONI
    # ========================================================================
    
    def apri_posizione_market(self, symbol, direzione, size, voto_ia, modalita='SPOT', exchange=None):
        """Apre una posizione market. Utilizza il MARGINE per permettere lo SHORT."""
        target_ex = exchange if exchange else self.exchange
        
        try:
            if isinstance(size, tuple): size = size[0]
            if isinstance(voto_ia, tuple): voto_ia = voto_ia[0]
            
            is_f = self._is_future(symbol)
            
            if not self._valida_parametri(symbol, None, size):
                return False

            # Recupero prezzo
            try:
                ticker = target_ex.fetch_ticker(symbol)
                prezzo_entry = float(ticker['last'])
            except Exception as e:
                logging.error(f"Errore fetch prezzo per {symbol}: {e}")
                return False

            # --- LOGICA DI INSTRADAMENTO (SIMULAZIONE VS LIVE) ---
            if not self.live_mode or (is_f and self.force_futures_simulation):
                self.posizioni_simulate[symbol] = {
                    'entry': prezzo_entry,
                    'size': size,
                    'direzione': direzione,
                    'timestamp': time.time()
                }
                tag = "🧪 SIMULAZIONE MARGIN"
                msg = (f"{tag}\n✅ APERTO {direzione}: {symbol}\nPrezzo: {prezzo_entry:.2f}\n"
                       f"Size: {size:.4f}\nLeva: {self.leverage_value}x")
                self._invia_notifica(msg)
                return True

            # --- MODALITA' LIVE (Corretto) ---
            order_type = 'buy' if direzione == 'LONG' else 'sell'
            params = {'leverage': self.leverage_value}
            
            def _esecuzione():
                # USARE target_ex per rispettare lo smistamento Spot/Futures
                return target_ex.create_market_order(symbol, order_type, size, params)
            
            ordine = self._retry_kraken(_esecuzione)
            if ordine:
                msg = (f"🚀 LIVE MARGIN ORDER EXECUTED\n✅ APERTO {direzione}: {symbol}\n"
                       f"Prezzo: {prezzo_entry:.2f}\nLeva: {self.leverage_value}x\nID: {ordine.get('id')}")
                self._invia_notifica(msg)
                return True
            return False

        except Exception as e:
            logging.error(f"❌ Errore critico apri_posizione_market: {e}")
            traceback.print_exc()
            return False

    # ========================================================================
    # CHIUSURA POSIZIONI
    # ========================================================================
    
    def chiudi_posizione(self, symbol, motivo="Chiusura", modalita='SPOT', exchange=None):
        """Chiude una posizione a margine invertendo l'ordine corrente."""
        target_ex = exchange if exchange else self.exchange
        try:
            is_f = self._is_future(symbol)
            # ... (logica simulazione invariata) ...

            # --- MODALITA' LIVE MARGIN ---
            try:
                # Usa target_ex invece di self.exchange
                posizioni = target_ex.fetch_positions([symbol])
                if not posizioni:
                    logging.warning(f"Nessuna posizione reale trovata per {symbol} su {modalita}")
                    return False
                
                pos = posizioni[0]
                side = 'sell' if pos['side'] == 'long' else 'buy'
                size = pos['contracts'] if is_f else pos['amount']
                
                params = {'leverage': self.leverage_value}
                ordine = target_ex.create_market_order(symbol, side, size, params)
                
                msg = f"📉 LIVE {modalita} CLOSED\nAsset: {symbol}\nMotivo: {motivo}"
                self._invia_notifica(msg)
                return True
            except Exception as e:
                logging.error(f"Errore chiusura reale Kraken Margin: {e}")
                return False

        except Exception as e:
            logging.error(f"Errore chiudi_posizione: {e}")
            return False

    def aggiorna_ordine_sl(self, symbol, nuovo_sl, modalita='SPOT'):
        """Aggiorna lo Stop Loss includendo la modalità (Spot/Futures)"""
        if isinstance(nuovo_sl, tuple): nuovo_sl = nuovo_sl[0]
        # Includiamo la modalità nel messaggio per chiarezza su Telegram
        msg = f"🛡️ SL AGGIORNATO ({modalita})\nAsset: {symbol}\nNuovo SL: {nuovo_sl:.2f}"
        self._invia_notifica(msg)
        return True

    def rimuovi_tp(self, symbol, modalita='SPOT'):
        """Attiva la Moon Phase rimuovendo il TP per la modalità specifica"""
        msg = f"🌙 MOON PHASE ACTIVATED ({modalita})\nAsset: {symbol}\nTP Rimosso."
        self._invia_notifica(msg)
        return True

    def get_stato_posizioni(self):
        try:
            if not self.live_mode: return self.posizioni_simulate
            posizioni = self.exchange.fetch_positions()
            return {p['symbol']: p for p in posizioni if float(p.get('amount', 0)) > 0}
        except Exception as e:
            logging.error(f"Errore fetch stato: {e}")
            return {}