# -*- coding: utf-8 -*-
# trade_manager_advanced_la.py - L&A INSTITUTIONAL POSITION MANAGER v1.3.1
# Gestione Avanzata Posizioni: Protezione Capitale, Break-Even e Moon Phase.
# Compatibile con Kraken Margin Trading per operazioni SHORT su Spot.

import logging
import traceback

class# -*- coding: utf-8 -*-
# trade_manager_advanced_la.py - L&A INSTITUTIONAL POSITION MANAGER v1.3.1
# Gestione Avanzata Posizioni: Protezione Capitale, Break-Even e Moon Phase.
# Compatibile con Kraken Margin Trading per operazioni SHORT su Spot.

import logging
import traceback

class TradeManager:
    """
    SISTEMA DI GESTIONE TRADE AVANZATO
    Responsabile del monitoraggio delle posizioni attive, della gestione dello Stop Loss
    e dell'attivazione della strategia Moon Phase (Fase 2) per massimizzare i profitti.
    """
    
    def __init__(self, position_tracker, alerts, performer):
        """
        INIZIALIZZAZIONE MANAGER
        Collega il tracker dei dati, il sistema di notifiche e l'esecutore degli ordini.
        """
        self.position_tracker = position_tracker
        self.alerts = alerts
        self.performer = performer
        logging.info("✅ TradeManager Advanced inizializzato correttamente.")

    # ========================================================================
    # SEZIONE 1: APERTURA E REGISTRAZIONE POSIZIONI
    # ========================================================================

    def apri_posizione_market(self, asset, direzione, entry_price, size, sl, tp, voto, modalita='SPOT', funding_rate=0, exchange=None):
        """
        ESECUZIONE ORDINE E SALVATAGGIO DATI
        Invia l'ordine al performer e, in caso di successo, salva i dati nel file JSON.
        """
        # Patch anti-tuple per sicurezza sui dati in ingresso
        if isinstance(entry_price, tuple): entry_price = entry_price[0]
        if isinstance(size, tuple): size = size[0]
        if isinstance(voto, tuple): voto = voto[0]

        # Chiamata al Performer (Gestisce internamente Leva/Margin per lo SHORT)
        successo = self.performer.apri_posizione_market(
            symbol=asset, 
            direzione=direzione, 
            size=size, 
            voto_ia=voto, 
            modalita=modalita, 
            exchange=exchange
        )
        
        if successo:
            nuova_pos = {
                'asset': asset,
                'direzione': direzione,
                'p_entrata': entry_price,
                'size': size,
                'sl': sl,
                'tp': tp,
                'voto': voto,
                'fase': 0, # Fase iniziale: Standard
                'funding': funding_rate,
                'pnl_perc': 0.0,
                '_da_chiudere': False
            }
            # Registrazione persistente nel tracker JSON
            self.position_tracker.aggiungi_posizione(asset, nuova_pos)
            return nuova_pos
        
        return None

    # ========================================================================
    # SEZIONE 2: MONITORAGGIO PREZZI E TARGET
    # ========================================================================

    # Aggiungi i parametri modalita ed exchange
    def aggiorna_tutte_posizioni(self, prezzi_correnti, modalita='SPOT', exchange=None):
        """
        ANALISI LIVE DEI TARGET (SL/TP)
        Ora supporta il passaggio dell'exchange corretto (Spot o Futures).
        """
        azioni = {}
        posizioni = self.position_tracker.ottieni_tutte_posizioni()
        
        for asset, p_att in prezzi_correnti.items():
            if asset not in posizioni:
                continue
                
            # Verifica se la posizione nell'asset tracker corrisponde alla modalità richiesta
            # (Opzionale, ma consigliato per sicurezza)
            pos = posizioni[asset]
            sl = pos.get('sl')
            tp = pos.get('tp')
            direzione = pos.get('direzione', 'LONG')
            fase = pos.get('fase', 0)

            # --- GESTIONE STOP LOSS ---
            if sl:
                if (direzione == 'LONG' and p_att <= sl) or (direzione == 'SHORT' and p_att >= sl):
                    azioni[asset] = ["SL_TOCCATO"]
                    continue

            # --- GESTIONE TAKE PROFIT (Disabilitato in Fase 2) ---
            if tp and fase < 2:
                if (direzione == 'LONG' and p_att >= tp) or (direzione == 'SHORT' and p_att <= tp):
                    azioni[asset] = ["TP_RAGGIUNTO"]

        return azioni

    # ========================================================================
    # SEZIONE 3: MANUTENZIONE E DINAMICA TRADE
    # ========================================================================

    def aggiorna_sl_da_gemini(self, asset, nuovo_sl, confidenza=100, motivo="Update", tipo="Automatico"):
        """
        AGGIORNAMENTO DINAMICO STOP LOSS
        Sposta lo stop loss (es. Break-Even) e sincronizza il cambiamento nel tracker.
        """
        if isinstance(nuovo_sl, tuple): nuovo_sl = nuovo_sl[0]
        
        # Esecuzione tecnica sul Performer
        successo = self.performer.aggiorna_ordine_sl(asset, nuovo_sl)
        
        if successo:
            # Sincronizzazione Tracker locale per persistenza al riavvio
            posizioni = self.position_tracker.ottieni_tutte_posizioni()
            if asset in posizioni:
                posizioni[asset]['sl'] = nuovo_sl
                self.position_tracker.salva_posizioni(posizioni)
                logging.info(f"🛡️ PROTEZIONE AGGIORNATA per {asset}: {nuovo_sl} ({motivo})")
                return True
        return False

    def chiudi_posizione(self, asset, prezzo_uscita, motivo):
        """
        CHIUSURA DEFINITIVA
        Chiude l'ordine su Kraken e rimuove l'asset dal monitoraggio attivo.
        """
        successo = self.performer.chiudi_posizione(asset, motivo)
        if successo:
            # Rimozione dal file JSON
            self.position_tracker.rimuovi_posizione(asset)
            logging.info(f"📉 POSIZIONE CHIUSA: {asset} - Motivo: {motivo}")
            return True
        return False TradeManager:
    """
    SISTEMA DI GESTIONE TRADE AVANZATO
    Responsabile del monitoraggio delle posizioni attive, della gestione dello Stop Loss
    e dell'attivazione della strategia Moon Phase (Fase 2) per massimizzare i profitti.
    """
    
    def __init__(self, position_tracker, alerts, performer):
        """
        INIZIALIZZAZIONE MANAGER
        Collega il tracker dei dati, il sistema di notifiche e l'esecutore degli ordini.
        """
        self.position_tracker = position_tracker
        self.alerts = alerts
        self.performer = performer
        logging.info("✅ TradeManager Advanced inizializzato correttamente.")

    # ========================================================================
    # SEZIONE 1: APERTURA E REGISTRAZIONE POSIZIONI
    # ========================================================================

    def apri_posizione_market(self, asset, direzione, entry_price, size, sl, tp, voto, modalita='SPOT', funding_rate=0, exchange=None):
        """
        ESECUZIONE ORDINE E SALVATAGGIO DATI
        Invia l'ordine al performer e, in caso di successo, salva i dati nel file JSON.
        """
        # Patch anti-tuple per sicurezza sui dati in ingresso
        if isinstance(entry_price, tuple): entry_price = entry_price[0]
        if isinstance(size, tuple): size = size[0]
        if isinstance(voto, tuple): voto = voto[0]

        # Chiamata al Performer (Gestisce internamente Leva/Margin per lo SHORT)
        successo = self.performer.apri_posizione_market(
            symbol=asset, 
            direzione=direzione, 
            size=size, 
            voto_ia=voto, 
            modalita=modalita, 
            exchange=exchange
        )
        
        if successo:
            nuova_pos = {
                'asset': asset,
                'direzione': direzione,
                'p_entrata': entry_price,
                'size': size,
                'sl': sl,
                'tp': tp,
                'voto': voto,
                'fase': 0, # Fase iniziale: Standard
                'funding': funding_rate,
                'pnl_perc': 0.0,
                '_da_chiudere': False
            }
            # Registrazione persistente nel tracker JSON
            self.position_tracker.aggiungi_posizione(asset, nuova_pos)
            return nuova_pos
        
        return None

    # ========================================================================
    # SEZIONE 2: MONITORAGGIO PREZZI E TARGET
    # ========================================================================

    # Aggiungi i parametri modalita ed exchange
    def aggiorna_tutte_posizioni(self, prezzi_correnti, modalita='SPOT', exchange=None):
        """
        ANALISI LIVE DEI TARGET (SL/TP)
        Ora supporta il passaggio dell'exchange corretto (Spot o Futures).
        """
        azioni = {}
        posizioni = self.position_tracker.ottieni_tutte_posizioni()
        
        for asset, p_att in prezzi_correnti.items():
            if asset not in posizioni:
                continue
                
            # Verifica se la posizione nell'asset tracker corrisponde alla modalità richiesta
            # (Opzionale, ma consigliato per sicurezza)
            pos = posizioni[asset]
            sl = pos.get('sl')
            tp = pos.get('tp')
            direzione = pos.get('direzione', 'LONG')
            fase = pos.get('fase', 0)

            # --- GESTIONE STOP LOSS ---
            if sl:
                if (direzione == 'LONG' and p_att <= sl) or (direzione == 'SHORT' and p_att >= sl):
                    azioni[asset] = ["SL_TOCCATO"]
                    continue

            # --- GESTIONE TAKE PROFIT (Disabilitato in Fase 2) ---
            if tp and fase < 2:
                if (direzione == 'LONG' and p_att >= tp) or (direzione == 'SHORT' and p_att <= tp):
                    azioni[asset] = ["TP_RAGGIUNTO"]

        return azioni

    # ========================================================================
    # SEZIONE 3: MANUTENZIONE E DINAMICA TRADE
    # ========================================================================

    def aggiorna_sl_da_gemini(self, asset, nuovo_sl, confidenza=100, motivo="Update", tipo="Automatico"):
        """
        AGGIORNAMENTO DINAMICO STOP LOSS
        Sposta lo stop loss (es. Break-Even) e sincronizza il cambiamento nel tracker.
        """
        if isinstance(nuovo_sl, tuple): nuovo_sl = nuovo_sl[0]
        
        # Esecuzione tecnica sul Performer
        successo = self.performer.aggiorna_ordine_sl(asset, nuovo_sl)
        
        if successo:
            # Sincronizzazione Tracker locale per persistenza al riavvio
            posizioni = self.position_tracker.ottieni_tutte_posizioni()
            if asset in posizioni:
                posizioni[asset]['sl'] = nuovo_sl
                self.position_tracker.salva_posizioni(posizioni)
                logging.info(f"🛡️ PROTEZIONE AGGIORNATA per {asset}: {nuovo_sl} ({motivo})")
                return True
        return False

    def chiudi_posizione(self, asset, prezzo_uscita, motivo):
        """
        CHIUSURA DEFINITIVA
        Chiude l'ordine su Kraken e rimuove l'asset dal monitoraggio attivo.
        """
        successo = self.performer.chiudi_posizione(asset, motivo)
        if successo:
            # Rimozione dal file JSON
            self.position_tracker.rimuovi_posizione(asset)
            logging.info(f"📉 POSIZIONE CHIUSA: {asset} - Motivo: {motivo}")
            return True
        return False
