# -*- coding: utf-8 -*-
# feedback_engine.py - MOTORE DI FEEDBACK INTELLIGENTE PER AUTO-APPRENDIMENTO v1.0
# Analizza i fallimenti, estrae lezioni, le salva in modo strutturato
# L'IA impara operazione per operazione

import json
import os
import time
import logging
from collections import deque

class FeedbackEngine:
    """
    Analizza ogni trade chiuso e estrae lezioni per l'IA
    - Salva le ultime 100 operazioni
    - Pesa i feedback recenti 3x
    - Identifica pattern di fallimento
    - Passa feedback strutturato all'IA
    """
    
    def __init__(self, max_lezioni=100, peso_recenti=3, recenti_count=10):
        self.max_lezioni = max_lezioni  # Mantieni ultime 100 operazioni
        self.peso_recenti = peso_recenti  # Ultimi 10 trade pesano 3x
        self.recenti_count = recenti_count  # Quanti sono "recenti"
        self.file_lezioni = "lezioni_ia.json"
        self.file_pattern = "pattern_fallimenti.json"
        self.lezioni = self._carica_lezioni()
        
    def _carica_lezioni(self):
        """Carica lezioni precedenti dal file JSON"""
        try:
            if os.path.exists(self.file_lezioni):
                with open(self.file_lezioni, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Errore caricamento lezioni: {e}")
        return []
    
    def _salva_lezioni(self):
        """Salva lezioni nel file JSON"""
        try:
            # Mantieni solo ultime max_lezioni
            lezioni_trim = self.lezioni[-self.max_lezioni:]
            with open(self.file_lezioni, "w", encoding="utf-8") as f:
                json.dump(lezioni_trim, f, indent=2, ensure_ascii=False)
            self.lezioni = lezioni_trim
        except Exception as e:
            logging.error(f"Errore salvataggio lezioni: {e}")
    
    def registra_operazione(self, asset, voto_ia, direzione, indicatori, contesto, outcome, motivo):
        """
        Registra un'operazione chiusa e estrae la lezione
        
        Args:
            asset: XXBTZUSD o XETHZUSD
            voto_ia: voto dato dall'IA (0-10)
            direzione: LONG o SHORT
            indicatori: dict con rsi, atr, macd, ecc
            contesto: dict con vwap, cvd, poc, ecc
            outcome: "WIN" o "LOSS"
            motivo: "TP raggiunto", "SL toccato", ecc
        """
        try:
            lezione = {
                "id": len(self.lezioni) + 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "asset": asset,
                "voto_ia": voto_ia,
                "direzione": direzione,
                "outcome": outcome,
                "motivo": motivo,
                "indicatori": indicatori,
                "contesto": contesto,
                "peso": self.peso_recenti if len(self.lezioni) >= self.max_lezioni - self.recenti_count else 1,
                "lezione_appresa": self._estrai_lezione(voto_ia, direzione, indicatori, contesto, outcome)
            }
            
            self.lezioni.append(lezione)
            self._salva_lezioni()
            
            logging.info(f"✅ Lezione registrata #{lezione['id']}: {asset} - {outcome}")
            
        except Exception as e:
            logging.error(f"Errore registrazione operazione: {e}")
    
    def _estrai_lezione(self, voto, direzione, indicatori, contesto, outcome):
        """
        INTELLIGENTE: Estrae una lezione dal trade
        Analizza PERCHÉ ha vinto/perso, non solo se ha vinto/perso
        """
        try:
            lezioni = []
            
            # Protezione contro dati None
            if not indicatori or not contesto:
                return ["Dati insufficienti per estrarre lezione"]
            
            rsi = indicatori.get('rsi', 50)
            cvd = contesto.get('cvd', 0)
            vwap = contesto.get('vwap', 0)
            prezzo = indicatori.get('prezzo', 0)
            
            # Protezione contro divisioni per zero
            if vwap == 0:
                vwap = prezzo
            
            # --- PATTERN 1: RSI Estremo ---
            if outcome == "LOSS":
                if rsi > 75 and direzione == "LONG":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: RSI ipercomprato ({rsi:.0f}) = Fallimento")
                    lezioni.append("→ Evita LONG quando RSI > 75")
                elif rsi < 25 and direzione == "SHORT":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: RSI ipervenduto ({rsi:.0f}) = Fallimento")
                    lezioni.append("→ Evita SHORT quando RSI < 25")
            else:  # WIN
                if rsi > 60 and rsi < 75 and direzione == "LONG":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: RSI in zona buona ({rsi:.0f}) = Successo")
                    lezioni.append("→ LONG funziona bene con RSI 60-75")
            
            # --- PATTERN 2: CVD (pressione buyers/sellers) ---
            if outcome == "LOSS":
                if cvd < -5 and direzione == "LONG":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: CVD negativo ({cvd:.1f}) = Fallimento")
                    lezioni.append("→ Evita LONG quando CVD è molto negativo (venditori forti)")
                elif cvd > 5 and direzione == "SHORT":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: CVD positivo ({cvd:.1f}) = Fallimento")
                    lezioni.append("→ Evita SHORT quando CVD è positivo (buyers forti)")
            else:  # WIN
                if cvd > 5 and direzione == "LONG":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: CVD positivo ({cvd:.1f}) = Successo")
                    lezioni.append("→ LONG con CVD positivo funziona bene")
                elif cvd < -5 and direzione == "SHORT":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: CVD negativo ({cvd:.1f}) = Successo")
                    lezioni.append("→ SHORT con CVD negativo funziona bene")
            
            # --- PATTERN 3: Prezzo vs VWAP (supporto/resistenza istituzionale) ---
            diff_pct = ((prezzo - vwap) / vwap * 100) if vwap > 0 else 0
            
            if outcome == "LOSS":
                if prezzo > vwap * 1.03 and direzione == "LONG":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: Prezzo sopra VWAP (+{diff_pct:.1f}%) = Fallimento")
                    lezioni.append("→ LONG sopra VWAP rischia resistenza. Aspetta ritracciamento")
                elif prezzo < vwap * 0.97 and direzione == "SHORT":
                    lezioni.append(f"❌ Voto {voto} su {direzione}: Prezzo sotto VWAP ({diff_pct:.1f}%) = Fallimento")
                    lezioni.append("→ SHORT sotto VWAP rischia rimbalzo. Aspetta conferma")
            else:  # WIN
                if prezzo < vwap and direzione == "LONG":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: LONG su supporto VWAP = Successo")
                    lezioni.append("→ LONG sotto VWAP su supporto istituzionale = Good entry")
                elif prezzo > vwap and direzione == "SHORT":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: SHORT su resistenza VWAP = Successo")
                    lezioni.append("→ SHORT sopra VWAP su resistenza istituzionale = Good entry")
            
            # --- PATTERN 4: Voto stesso ---
            if outcome == "LOSS":
                if voto >= 8:
                    lezioni.append(f"❌ Voto ALTO ({voto}/10) ma ha perso = Voto troppo ottimista")
                    lezioni.append("→ Riduci fiducia quando combinazione di indicatori è confusa")
                elif voto < 5:
                    lezioni.append(f"⚠️ Voto BASSO ({voto}/10) e ha perso = Riconoscimento corretto")
                    lezioni.append("→ Mantieni basso voto in queste condizioni")
            else:  # WIN
                if voto >= 7.5:
                    lezioni.append(f"✅ Voto ALTO ({voto}/10) e ha vinto = Valutazione corretta")
                    lezioni.append("→ Quando vedi questi pattern, voto alto è affidabile")
            
            # Se nessuna lezione specifica, dà un feedback generico
            if not lezioni:
                if outcome == "WIN":
                    lezioni.append(f"✅ Voto {voto} su {direzione}: Vincita con questi indicatori")
                else:
                    lezioni.append(f"❌ Voto {voto} su {direzione}: Perdita - analizza gli indicatori")
            
            return lezioni
            
        except Exception as e:
            logging.error(f"Errore estrazione lezione: {e}")
            return [f"Errore estrazione lezione: {e}"]
    
    def genera_feedback_per_ia(self):
        """
        Genera feedback strutturato da passare all'IA
        Prioritizza le lezioni recenti
        """
        try:
            if not self.lezioni:
                return "Nessun dato storico disponibile. Analizza naturalmente."
            
            # Prendi ultime 10 lezioni (le più importanti)
            lezioni_recenti = self.lezioni[-10:]
            
            # Ordina per peso (recenti hanno peso 3x)
            lezioni_ponderate = []
            for lezione in lezioni_recenti:
                peso = lezione.get('peso', 1)
                lezioni_ponderate.extend(lezione.get('lezione_appresa', []) * peso)
            
            # Elimina duplicati mantenendo ordine
            seen = set()
            lezioni_uniche = []
            for l in lezioni_ponderate:
                if l not in seen:
                    lezioni_uniche.append(l)
                    seen.add(l)
            
            # Crea feedback sintetico
            if not lezioni_uniche:
                return "Dati storici non conclusivi. Analizza naturalmente."
            
            # Prendi max 5 lezioni più importanti
            feedback = "LEZIONI APPRESE DALL'ULTIMO ANNO:\n"
            feedback += "=" * 50 + "\n"
            for lezione in lezioni_uniche[:5]:
                feedback += f"• {lezione}\n"
            feedback += "=" * 50 + "\n"
            feedback += "Applica queste lezioni nella tua analisi."
            
            return feedback
            
        except Exception as e:
            logging.error(f"Errore generazione feedback: {e}")
            return "Errore generazione feedback. Analizza naturalmente."
    
    def analizza_pattern_fallimenti(self):
        """
        Analizza i pattern di fallimento ricorrenti
        Salva su file per debug e miglioramento
        """
        try:
            pattern = {
                "totale_operazioni": len(self.lezioni),
                "wins": sum(1 for l in self.lezioni if l.get('outcome') == 'WIN'),
                "losses": sum(1 for l in self.lezioni if l.get('outcome') == 'LOSS'),
                "pattern_ricorrenti": {}
            }
            
            if pattern["totale_operazioni"] == 0:
                return
            
            pattern["win_rate"] = pattern["wins"] / pattern["totale_operazioni"] * 100
            
            # Analizza pattern ricorrenti nei fallimenti
            losses = [l for l in self.lezioni if l.get('outcome') == 'LOSS']
            
            # Pattern 1: RSI alto
            rsi_alto_losses = sum(1 for l in losses if l.get('indicatori', {}).get('rsi', 0) > 75)
            if rsi_alto_losses > 0:
                pattern["pattern_ricorrenti"]["rsi_alto_fallimento"] = {
                    "count": rsi_alto_losses,
                    "pct": rsi_alto_losses / len(losses) * 100 if losses else 0
                }
            
            # Pattern 2: CVD negativo e LONG
            cvd_neg_long_losses = sum(1 for l in losses 
                                     if l.get('direzione') == 'LONG' and l.get('contesto', {}).get('cvd', 0) < -5)
            if cvd_neg_long_losses > 0:
                pattern["pattern_ricorrenti"]["cvd_negativo_long_fallimento"] = {
                    "count": cvd_neg_long_losses,
                    "pct": cvd_neg_long_losses / len(losses) * 100 if losses else 0
                }
            
            # Salva pattern
            with open(self.file_pattern, "w", encoding="utf-8") as f:
                json.dump(pattern, f, indent=2, ensure_ascii=False)
            
            logging.info(f"📊 Pattern analizzati: {pattern['totale_operazioni']} op, {pattern['win_rate']:.1f}% WR")
            
        except Exception as e:
            logging.error(f"Errore analisi pattern: {e}")