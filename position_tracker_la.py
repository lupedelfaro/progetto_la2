# -*- coding: utf-8 -*-
# position_tracker_la.py - L&A INSTITUTIONAL POSITION TRACKER v1.6
# Gestione integrata: SPOT, MARGIN (SHORT) e PERPETUAL/FUTURES.

import json
import logging
import os
import numpy as np
from datetime import datetime

class PositionTracker:
    """
    SISTEMA DI TRACCIAMENTO E ANALISI POSIZIONI
    Responsabile della memorizzazione delle operazioni e del calcolo dei profitti 
    in tempo reale, adattando la logica per posizioni Long, Short e Derivati.
    """
    
    def __init__(self, file_posizioni="posizioni_aperte.json"):
        """
        INIZIALIZZAZIONE TRACKER
        Configura il logger e carica le posizioni esistenti.
        """
        self.file_posizioni = file_posizioni
        # FIX CRITICO: Il logger deve essere creato PRIMA di caricare i dati
        self.logger = logging.getLogger("PositionTracker")
        self.posizioni_aperte = self._carica_posizioni()
        self.storico_trades = []

    # ========================================================================
    # SEZIONE 1: PERSISTENZA E GESTIONE FILE (FIX JSON)
    # ========================================================================
    
    def _carica_posizioni(self):
        """CARICAMENTO DATABASE JSON CON PROTEZIONE FILE VUOTO"""
        if os.path.exists(self.file_posizioni):
            try:
                with open(self.file_posizioni, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except Exception as e:
                # Ora il logger esiste e non darà più errore
                self.logger.error(f"⚠️ Errore caricamento posizioni: {e}")
                return {}
        return {}
    
    def salva_posizioni(self, posizioni_da_salvare=None):
        """SALVATAGGIO STATO CORRENTE SUL DISCO"""
        if posizioni_da_salvare is not None:
            self.posizioni_aperte = posizioni_da_salvare
        try:
            with open(self.file_posizioni, "w") as f:
                json.dump(self.posizioni_aperte, f, indent=4)
        except Exception as e:
            self.logger.error(f"⚠️ Errore salvataggio posizioni: {e}")

    # ========================================================================
    # SEZIONE 2: INTERFACCIA PER TRADEMANAGER (Apertura/Chiusura)
    # ========================================================================
    
    def aggiungi_posizione(self, asset, dati):
        """REGISTRAZIONE NUOVO TRADE (Sincronizzato con TradeManager)"""
        dati.setdefault('fase', 0)
        dati.setdefault('data_apertura', datetime.now().isoformat())
        dati.setdefault('max_profitto', 0.0)
        dati.setdefault('pnl_perc', 0.0)
        
        # Salviamo l'asset anche dentro il dizionario per il mapping inverso
        dati['asset_real'] = asset 
        
        self.posizioni_aperte[asset] = dati
        self.salva_posizioni()
        self.logger.info(f"✅ Posizione registrata: {asset} ({dati.get('direzione')})")

    def rimuovi_posizione(self, asset):
        """RIMOZIONE ASSET DOPO CHIUSURA"""
        if asset in self.posizioni_aperte:
            del self.posizioni_aperte[asset]
            self.salva_posizioni()
            self.logger.info(f"🗑️ {asset} rimosso dal tracker.")

    # ========================================================================
    # SEZIONE 3: MOTORE PnL E FIX MAPPING PERPETUAL (BTC/USD:BTC)
    # ========================================================================

    def aggiorna_pnl(self, asset, prezzo_corrente):
        """CALCOLO PnL DINAMICO - RISOLVE IL PROBLEMA DEI PALLINI BIANCHI"""
        pos_key = asset
        if asset not in self.posizioni_aperte:
            for k, v in self.posizioni_aperte.items():
                if asset == v.get('asset_real') or k in asset or asset in k:
                    pos_key = k
                    break
        if pos_key not in self.posizioni_aperte:
            return None
        
        pos = self.posizioni_aperte[pos_key]
        # PATCH: caso None/zero su entry/prezzo_corrente
        try:
            entry = float(pos['p_entrata'])
        except (KeyError, TypeError, ValueError):
            self.logger.warning(f"Entry None o non numerico - asset: {asset}")
            return None
        if entry is None or entry == 0 or prezzo_corrente is None or prezzo_corrente == 0:
            self.logger.warning(f"Entry o prezzo_corrente None o zero - asset: {asset}, entry={entry}, prezzo_corrente={prezzo_corrente}")
            return None

        direzione = pos.get('direzione', 'LONG').upper()
        if direzione == 'SHORT':
            pnl_perc = ((entry - prezzo_corrente) / entry) * 100
        else:
            pnl_perc = ((prezzo_corrente - entry) / entry) * 100

        pos['pnl_perc'] = round(pnl_perc, 2)
        pos['prezzo_attuale'] = prezzo_corrente 
        if pnl_perc > pos.get('max_profitto', 0):
            pos['max_profitto'] = pnl_perc
        return pos

    # ========================================================================
    # SEZIONE 4: UTILITY E GESTIONE FASI
    # ========================================================================

    def ottieni_tutte_posizioni(self):
        """RITORNA IL DIZIONARIO DELLE POSIZIONI PER LA TABELLA"""
        return self.posizioni_aperte

    def aggiorna_fase(self, asset, nuova_fase):
        """AGGIORNA FASE (0=Monitor, 1=BE, 2=Moon Phase)"""
        if asset in self.posizioni_aperte:
            self.posizioni_aperte[asset]['fase'] = nuova_fase
            self.salva_posizioni()
            return True
        return False