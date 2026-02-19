# -*- coding: utf-8 -*-
# manager_la.py - RISK MANAGEMENT ENGINE v3.0 HYBRID
# Protezioni complete contro divisioni per zero e dati invalidi
# Integrato con guardrail logico

import logging
from config_auto_apprendimento import GEMINI_MODEL
import traceback
from config_auto_apprendimento import KELLY_FRACTION
SIZE_MINIMO_FALLBACK = 0.001  # oppure un valore minimo adatto al tuo exchange (es. 1, 10, ecc)
class ManagerLA:
    """
    Gestisce il rischio: Position Sizing, Stop Loss, Take Profit
    Fasi: 0=Monitoraggio, 1=Break Even, 2=Moon Phase, 3=Scudo
    """
    
    def __init__(self, account_balance, risk_per_trade=0.03):
        self.account_balance = max(account_balance, 1.0)
        self.risk_per_trade = max(min(risk_per_trade, 0.05), 0.01)
        self.kelly_fraction = KELLY_FRACTION
        logging.info(f"ManagerLA inizializzato: Saldo={self.account_balance}, Risk={self.risk_per_trade*100}%")

    def calculate_position_size(self, prezzo_entry, stop_loss, voto_ia, atr):
        try:
            # PATCH: estrai i valori base
            if isinstance(prezzo_entry, tuple): prezzo_entry = prezzo_entry[0]
            if isinstance(stop_loss, tuple): stop_loss = stop_loss[0]
            if isinstance(voto_ia, tuple): voto_ia = voto_ia[0]
            if isinstance(atr, tuple): atr = atr[0]

            if None in (prezzo_entry, stop_loss, voto_ia, atr) or prezzo_entry <= 0:
                logging.warning(f"[PATCH] Dati invalidi per size: {prezzo_entry}, {stop_loss}, {voto_ia}, {atr}")
                return 0

            risk_assoluto = self.account_balance * self.risk_per_trade
            distanza_sl = abs(prezzo_entry - stop_loss)
            
            if distanza_sl == 0:
                return SIZE_MINIMO_FALLBACK

            win_probability = min(voto_ia / 10.0, 0.95)
            loss_probability = 1 - win_probability
            profit_factor = 2.0
            
            kelly = ((profit_factor * win_probability - loss_probability) / profit_factor)
            kelly = max(min(kelly * self.kelly_fraction, 0.25), 0.01)
            
            size_finale = (risk_assoluto / distanza_sl) * kelly
            size_finale = min(max(size_finale, SIZE_MINIMO_FALLBACK), self.account_balance * 0.5)
            
            return size_finale
        except Exception as e:
            logging.error(f"Errore calcolo size: {e}")
            return SIZE_MINIMO_FALLBACK

    def gestisci_posizione(self, posizione, dati_correnti, macro_data=None):
        """
        Monitora la posizione e gestisce le fasi (BE al 50%, Moon Phase, SL update)
        Versione integrale per Andrea.
        """
        try:
            if not posizione or not dati_correnti:
                return None
            
            # --- RECUPERO DATI ---
            asset = posizione.get('asset', 'N/D')
            p_att = dati_correnti.get('prezzo_real', dati_correnti.get('close', 0))
            p_ent = posizione.get('p_entrata', 0)
            sl = posizione.get('sl', 0)
            tp = posizione.get('tp', 0)
            fase = posizione.get('fase', 0)
            direzione = posizione.get('direzione', 'LONG')

            if p_att == 0 or p_ent == 0 or tp == 0:
                return None

            # --- 1. CALCOLO PROGRESSO VERSO IL TARGET DI GEMINI ---
            # prog = 0.0 (all'entrata), prog = 1.0 (al TP), prog = 0.5 (metà strada)
            if direzione == 'LONG':
                denominator = (tp - p_ent)
                prog = (p_att - p_ent) / denominator if denominator != 0 else 0
            else: # SHORT
                denominator = (p_ent - tp)
                prog = (p_ent - p_att) / denominator if denominator != 0 else 0

            # --- 2. FASE 1: PROTEZIONE 50% GAIN (BREAK-EVEN) ---
            # Se siamo in fase 0 e abbiamo percorso il 50% della strada verso il TP
            if fase == 0 and prog >= 0.50:
                logging.info(f"🎯 50% GAIN RAGGIUNTO per {asset}! Sposto SL a Pareggio.")
                return {
                    'sl': p_ent, 
                    'fase': 1, 
                    'msg': f"🚀 Andrea, siamo a metà strada per il TP su {asset}! Stop Loss spostato a Pareggio ({p_ent})."
                }

            # --- 3. FASE 2: MOON PHASE (TP RAGGIUNTO) ---
            # Se il prezzo tocca il Take Profit, lo rimuoviamo per lasciar correre
            if fase <= 1 and prog >= 1.0:
                logging.info(f"🌙 MOON PHASE per {asset}: TP raggiunto! Rimuovo TP e lascio correre.")
                return {
                    'remove_tp': True, 
                    'fase': 2, 
                    'msg': f"🔥 TP Raggiunto su {asset}! Entriamo in FASE DUE: TP rimosso e Moon Phase attiva per Andrea!"
                }

            # --- 4. TRAILING SL UPDATE (Protezione Dinamica) ---
            from config_auto_apprendimento import ATR_FALLBACK, TRAILING_SCUDO_ATR_MULT
            
            vwap = dati_correnti.get('vwap', p_att)
            poc = dati_correnti.get('poc', p_att)
            atr = dati_correnti.get('atr', ATR_FALLBACK)
            
            if fase == 2:
                # In Moon Phase usiamo un trailing più stretto
                nuovo_sl = self._calcola_trailing_moon(p_att, direzione, vwap, poc, atr)
            else:
                # In fase normale o BE usiamo lo scudo standard
                nuovo_sl = self._calcola_trailing_sl(p_att, p_ent, direzione, vwap, poc, atr, TRAILING_SCUDO_ATR_MULT)

            # Applichiamo l'update solo se il nuovo SL è migliorativo (più alto per LONG, più basso per SHORT)
            if sl is not None and ((direzione == 'LONG' and nuovo_sl > sl) or (direzione == 'SHORT' and nuovo_sl < sl)):
                logging.info(f"🛡️ Update SL su {asset} ({direzione}) -> Nuovo SL: {nuovo_sl}")
                return {
                    'sl': nuovo_sl, 
                    'fase': fase,
                    'msg': f"🛡️ SL aggiornato per {asset}: {nuovo_sl:.2f}"
                }

            return None
        except Exception as e:
            logging.error(f"❌ Errore critico gestione posizione: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None

    def _calcola_trailing_sl(self, p_att, p_ent, direzione, vwap, poc, atr, atr_mult):
        dist = atr * atr_mult
        if direzione == 'LONG':
            return max(max(vwap, poc) - dist, p_ent)
        return min(min(vwap, poc) + dist, p_ent)

    def _calcola_trailing_moon(self, p_att, direzione, vwap, poc, atr):
        dist = atr * 0.5 # Molto stretto in Moon Phase
        if direzione == 'LONG':
            return max(p_att - dist, vwap - atr)
        return min(p_att + dist, vwap + atr)