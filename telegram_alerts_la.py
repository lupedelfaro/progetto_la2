# -*- coding: utf-8 -*-
# telegram_alerts_la.py - SISTEMA COMPLETO DI NOTIFICHE TELEGRAM
# Centralizza TUTTI i messaggi Telegram del bot in un unico file

import requests
import logging
import json
from datetime import datetime

class TelegramAlerts:
    """
    Gestisce TUTTE le notifiche Telegram del bot L&A.
    Centralizza messaggi per: aperture, chiusure, SL/TP, profit, moon phase, ecc.
    """
    
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logging.getLogger("TelegramAlerts")
    
    def invia_messaggio(self, messaggio):
        """Invia messaggio Telegram grezzo con protezioni"""
        if not self.bot_token or not self.chat_id:
            self.logger.warning("⚠️ Token o Chat ID non configurati")
            return False
        
        try:
            # Protezione: limita lunghezza messaggio
            if len(messaggio) > 4000:
                messaggio = messaggio[:3990] + "..."
            
            # Protezione: escape characters per HTML
            messaggio_pulito = messaggio.replace("<", "&lt;").replace(">", "&gt;")
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': self.chat_id,
                'text': messaggio_pulito,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }, timeout=10)
            
            if not resp.ok:
                self.logger.error(f"❌ Errore Telegram: {resp.text}")
                return False
            
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Errore invio Telegram: {e}")
            return False
    
    # ========================================================================
    # MESSAGGI SISTEMA
    # ========================================================================
    
    def sistema_online(self, soglia_entry, modalita="HYBRID"):
        """Bot online - messaggio di avvio"""
        msg = (
            f"🚀 **L&A Terminal v5.0 Online**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Modalità: {modalita}\n"
            f"Stato: AVVIO\n"
            f"Soglia Entry: ⭐ `{soglia_entry}/10`\n"
            f"Messaggi: COMPLETI (con/senza posizione + LSTM Lite)\n"
            f"Neural Network: XGBoost Predictor Attivo ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.invia_messaggio(msg)
    
    def sistema_offline(self):
        """Bot offline - messaggio arresto"""
        msg = "⛔ **L&A Terminal Offline**"
        return self.invia_messaggio(msg)
    
    def errore_critico(self, errore):
        """Errore critico del sistema"""
        msg = f"❌ **ERRORE CRITICO**: {str(errore)[:200]}"
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # APERTURA POSIZIONI
    # ========================================================================
    
    def posizione_aperta(self, asset, direzione, entry_price, size, sl, tp, 
                         voto, lstm_pred=None, modalita="SPOT", funding_rate=None):
        """Notifica apertura nuova posizione"""
        
        direzione_icon = "🟢 LONG" if direzione == "LONG" else "🔴 SHORT"
        lstm_info = ""
        
        if lstm_pred and lstm_pred.get('is_valido'):
            lstm_info = (
                f"LSTM Prediction: `{lstm_pred.get('direzione')}` "
                f"({lstm_pred.get('confidence'):.1f}%)\n"
            )
        funding_str = (
            f"Funding Rate: `{funding_rate:.5f}` ({funding_rate*100:.3f}%)\n"
            if funding_rate is not None else ""
        )
        
        msg = (
            f"🎯 **NUOVA POSIZIONE APERTA**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Asset: `{asset}`\n"
            f"Direzione: `{direzione_icon}`\n"
            f"Voto IA: ⭐ `{voto:.1f}/10`\n"
            f"Entry Price: `{self._format_price(entry_price)}`\n"
            f"Position Size: `{size:.4f}`\n"
            f"Stop Loss: `{self._format_price(sl)}`\n"
            f"Take Profit: `{self._format_price(tp)}`\n"
            f"{lstm_info}"
            f"{funding_str}"
            f"Modalità: `{modalita}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # GESTIONE SL/TP
    # ========================================================================
    
    def sl_adattato_gemini(self, asset, nuovo_sl, confidence, ragione, flessibilita):
        """SL adattato da GEMINI LIVE EVAL"""
        msg = (
            f"🎯 **SL ADATTATO** ({confidence}% confidenza)\n"
            f"Asset: `{asset}`\n"
            f"Nuovo SL: `{self._format_price(nuovo_sl)}`\n"
            f"Ragione: {ragione}\n"
            f"Flessibilità: {flessibilita}"
        )
        return self.invia_messaggio(msg)
    
    def sl_spostato_breakeven(self, asset, nuovo_sl, profit_perc):
        """SL spostato a breakeven (50% profit raggiunto)"""
        msg = (
            f"✅ **SL SPOSTATO A BREAKEVEN**\n"
            f"Asset: `{asset}`\n"
            f"Nuovo SL: `{self._format_price(nuovo_sl)}`\n"
            f"Profitto Raggiunto: `{profit_perc:.2f}%`\n"
            f"Status: ✅ Capitale protetto!"
        )
        return self.invia_messaggio(msg)
    
    def tp_adattato_gemini(self, asset, nuovo_tp, confidence):
        """TP adattato da GEMINI"""
        msg = (
            f"📍 **TP ADATTATO** ({confidence}% confidenza)\n"
            f"Asset: `{asset}`\n"
            f"Nuovo TP: `{self._format_price(nuovo_tp)}`"
        )
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # LIVELLI RAGGIUNTI
    # ========================================================================
    
    def profit_50_raggiunto(self, asset, profit_perc, prezzo_corrente):
        """50% profitto raggiunto - breakeven attivato"""
        msg = (
            f"💰 **50% PROFIT RAGGIUNTO**\n"
            f"Asset: `{asset}`\n"
            f"Profitto: `{profit_perc:.2f}%`\n"
            f"Prezzo Attuale: `{self._format_price(prezzo_corrente)}`\n"
            f"→ SL SPOSTATO A BREAKEVEN"
        )
        return self.invia_messaggio(msg)
    
    def moon_phase_attivata(self, asset, profit_perc, prezzo_corrente):
        """100% profitto raggiunto - moon phase attivata con trailing stop"""
        msg = (
            f"🚀 **MOON PHASE ATTIVATA**\n"
            f"Asset: `{asset}`\n"
            f"Profitto Totale: `{profit_perc:.2f}%`\n"
            f"Prezzo Corrente: `{self._format_price(prezzo_corrente)}`\n"
            f"→ TRAILING STOP AL 50% DEL PROFITTO ATTIVATO\n"
            f"🌙 Caccia ai massimi storici!"
        )
        return self.invia_messaggio(msg)
    
    def trailing_stop_avanzato(self, asset, nuovo_sl, prezzo_corrente, profit_perc):
        """Trailing stop avanzato in moon phase"""
        msg = (
            f"📈 **TRAILING STOP AVANZATO**\n"
            f"Asset: `{asset}`\n"
            f"Nuovo SL: `{self._format_price(nuovo_sl)}`\n"
            f"Prezzo: `{self._format_price(prezzo_corrente)}`\n"
            f"Profitto Protetto: `{profit_perc:.2f}%`"
        )
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # CHIUSURA POSIZIONI
    # ========================================================================
    
    def posizione_chiusa_sl(self, asset, sl, pnl_perc, pnl_usd):
        """Posizione chiusa per SL toccato"""
        emoji = "✅" if pnl_perc > 0 else "❌"
        msg = (
            f"{emoji} **POSIZIONE CHIUSA - SL TOCCATO**\n"
            f"Asset: `{asset}`\n"
            f"Stop Loss: `{self._format_price(sl)}`\n"
            f"PnL: `{pnl_perc:+.2f}%` (`${pnl_usd:+.2f}`)"
        )
        return self.invia_messaggio(msg)
    
    def posizione_chiusa_tp(self, asset, tp, pnl_perc, pnl_usd):
        """Posizione chiusa per TP raggiunto"""
        msg = (
            f"🎯 **TP RAGGIUNTO - POSIZIONE CHIUSA**\n"
            f"Asset: `{asset}`\n"
            f"Take Profit: `{self._format_price(tp)}`\n"
            f"PnL: `{pnl_perc:+.2f}%` (`${pnl_usd:+.2f}`)\n"
            f"✅ Trade vincente!"
        )
        return self.invia_messaggio(msg)
    
    def posizione_chiusa_gemini(self, asset, ragione, confidence, pnl_perc, pnl_usd, flessibilita):
        """Posizione chiusa da GEMINI LIVE EVAL"""
        msg = (
            f"🛑 **CHIUSURA GEMINI LIVE**: `{asset}`\n"
            f"Ragione: {ragione}\n"
            f"Confidenza: `{confidence}%`\n"
            f"PnL: `{pnl_perc:+.2f}%` (`${pnl_usd:+.2f}`)\n"
            f"Scenario Mercato: {flessibilita}"
        )
        return self.invia_messaggio(msg)
    
    def posizione_chiusa_manager(self, asset, motivo, pnl_perc, pnl_usd):
        """Posizione chiusa dal ManagerLA"""
        emoji = "✅" if pnl_perc > 0 else "❌"
        msg = (
            f"{emoji} **CHIUSURA**: `{asset}`\n"
            f"Motivo: {motivo}\n"
            f"PnL: `{pnl_perc:+.2f}%` (`${pnl_usd:+.2f}`)"
        )
        return self.invia_messaggio(msg)
    
    def posizione_ridotta(self, asset, confidence, ragione, flessibilita):
        """Riduzione size consigliata da GEMINI"""
        msg = (
            f"⚠️ **REDUCE CONSIGLIATO** ({confidence}% confidenza)\n"
            f"Asset: `{asset}`\n"
            f"Ragione: {ragione}\n"
            f"Scenario: {flessibilita}"
        )
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # ANALISI COMPLETE
    # ========================================================================
    
    def analisi_completa(self, asset, voto, direzione, prezzo_real, sentiment, 
                         dxy, nasdaq, contesto, dati, mtf, lstm_pred, 
                         r_mentore, a_logica, sl_sugg, tp_sugg, 
                         guardrail_applicato=False, posizione_aperta=None, 
                         valutazione_live=None):
        """Versione Sniper: Massima densità di dati, zero interlinee inutili, mentore asciutto."""
        
        a_logica, lstm_p, cont, d, m = a_logica or {}, lstm_pred or {}, contesto or {}, dati or {}, mtf or {}
        
        g_info = " ⚔️ GUARDRAIL" if guardrail_applicato else ""
        icona_dir = "🟢 LONG" if "LONG" in direzione else "🔴 SHORT"
        if "FLAT" in direzione: icona_dir = "⚪ FLAT"

        # PARTE 1, 2, 3, 4: INTESTAZIONE, MACRO, ISTITUZIONALI E TECNICI (Tutto accorpato)
        msg = (
            f"🤖 **REPORT {asset}** | ⭐ `{voto:.1f}/10` | {icona_dir}{g_info}\n"
            f"💵 `{self._format_price(prezzo_real)}` | Sent: `{sentiment}` | DXY: `{dxy:.2f}` | NAS: `{nasdaq:.2f}`\n"
            f"⚖️ **INST:** VWAP `{self._format_price(contesto.get('vwap', 0))}` | CVD `{contesto.get('cvd', 0):.0f}` | POC `{self._format_price(contesto.get('poc', 0))}`\n"
            f"📊 **TREND:** 1D:{mtf.get('1D', {}).get('trend', 'N/A')} | 4h:{mtf.get('4h', {}).get('trend', 'N/A')} | 1h:{mtf.get('1h', {}).get('trend', 'N/A')}\n"
            f"📉 **TECH:** RSI `{dati.get('rsi', 0):.1f}` | ATR `{dati.get('atr', 0):.2f}` | VSA `{dati.get('vsa_status', 'NORMAL')}`\n"
        )

        # PARTE 5: NEURAL PREDICTION (XGBOOST)
        # PARTE 5: NEURAL PREDICTION (XGBOOST)
        if lstm_pred and lstm_pred.get('is_valido'):
            msg += f"🔮 **XGBOOST:** `{lstm_pred.get('direzione', 'N/A')}` ({lstm_pred.get('confidence', 0):.1f}%) | Var: `{lstm_pred.get('variazione_perc', 0):+.2f}%`\n"
        else:
            try:
                import asset_list
                # Verifica dinamica contro la tua lista ufficiale
                spot_tickers = [asset_list.ASSET_MAPPING.get(c, c) for c in asset_list.ATTIVI]
                is_spot = asset in spot_tickers
            except:
                is_spot = asset in ['XXBTZUSD', 'XETHZUSD'] # Fallback di sicurezza
            
            causa = "Asset Spot" if is_spot else "Dati insufficienti"
            msg += f"🔮 **XGBOOST:** ⏳ {causa}\n"
            
            causa = "Asset Spot" if is_spot else "Dati insufficienti"
            msg += f"🔮 **XGBOOST:** ⏳ {causa}\n"

        # PARTE 6 & 7: MENTORE E LOGICA (ASCIUTTI)
        # Segnalo solo l'essenziale per non intasare Telegram
        msg += f"🧠 **MENTORE:** {r_mentore}\n"
        logica_testo = "\n".join([f"- {k.replace('_',' ').title()}: {v}" for k, v in a_logica.items()])
        msg += f"🔍 **LOGICA:** {logica_testo if logica_testo else 'N/A'}\n"

        # PARTE 8 & 9: LIVELLI E POSIZIONE
        sl_val = self._format_price(sl_sugg) if sl_sugg is not None else "N/A"
        tp_val = self._format_price(tp_sugg) if tp_sugg is not None else "N/A"
        msg += f"🛡️ **LIVELLI:** SL `{sl_val}` | TP `{tp_val}`\n"

        if posizione_aperta:
            pnl = posizione_aperta.get('pnl_perc', 0)
            fase = ["MONIT.", "B.EVEN", "MOON", "SCUDO"][min(posizione_aperta.get('fase', 0), 3)]
            msg += f"📍 **POS:** {posizione_aperta['direzione']} | PnL: `{pnl:+.2f}%` | Fase: `{fase}`\n"
           
            # PARTE 10: LIVE EVAL
            if valutazione_live:
                msg += f"🔬 **LIVE:** {valutazione_live.get('azione', 'HOLD')} ({valutazione_live.get('confidence', 50)}%) | {valutazione_live.get('ragione', 'N/A')}\n"
        else:
            msg += f"📍 **STATO:** ❌ Nessuna posizione attiva\n"

        msg += "━━━━━━━━━━━━━━━━━━━━\n⏰ *Real-Time (Hybrid + XGBoost)*"

        return self.invia_messaggio(msg)
    
    # ========================================================================
    # STATISTICHE E REPORT
    # ========================================================================
    
    def report_giornaliero(self, stats):
        """Report giornaliero con statistiche di performance"""
        msg = (
            f"📊 **REPORT GIORNALIERO**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Trade Totali: `{stats.get('total_trades', 0)}`\n"
            f"Vincenti: `{stats.get('wins', 0)}`\n"
            f"Persi: `{stats.get('losses', 0)}`\n"
            f"Win Rate: `{stats.get('win_rate', 0):.1f}%`\n"
            f"PnL Totale: `${stats.get('total_pnl', 0):+.2f}`\n"
            f"Equity: `${stats.get('equity', 0):.2f}`\n"
            f"Equity Change: `{stats.get('equity_change_perc', 0):+.2f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.invia_messaggio(msg)
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    @staticmethod
    def _format_price(p):
        """Formatta il prezzo con protezione totale per valori None o errori"""
        try:
            if p is None:
                return "0.00"
            p_val = float(p)
            if p_val == 0:
                return "0.00"
            if p_val >= 1000:
                return f"{p_val:,.2f}"
            if p_val >= 1:
                return f"{p_val:.4f}"
            return f"{p_val:.8f}"
        except (TypeError, ValueError):
            return "0.00"