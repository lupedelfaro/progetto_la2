# -*- coding: utf-8 -*-
# lstm_predictor_lite.py - PREDICTOR CON SCIKIT-LEARN SOLO
# Zero dipendenze esterne (RandomForest), funziona al 100%

import numpy as np
import pandas as pd
import logging
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor
import pickle
import os
from datetime import datetime

class LSTMPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.last_training = 0
        self.training_accuracy = 0
        self.features = ['close', 'high', 'low', 'volume', 'rsi', 'atr', 'vwap', 'cvd']
        logging.info("✅ LSTMPredictor (RandomForest/scikit-learn) inizializzato")
        self._carica_modello()
    
    def _carica_modello(self):
        try:
            if os.path.exists("models/rf_model.pkl"):
                with open("models/rf_model.pkl", 'rb') as f:
                    self.model = pickle.load(f)
                logging.info("✅ Modello RandomForest caricato")
        except Exception as e:
            logging.warning(f"⚠️ Errore caricamento modello: {e}")
    
    def allena_modello(self, dati_storici):
        """Allena RandomForest su dati storici"""
        try:
            logging.info(f"🔍 DEBUG TRAIN: Ricevuti {len(dati_storici) if dati_storici else 0} dati per training")
            
            if not dati_storici or len(dati_storici) < 100:
                logging.warning(f"⚠️ Dati insufficienti per training: {len(dati_storici) if dati_storici else 0}")
                return 0
            
            df = pd.DataFrame(dati_storici)
            features_disponibili = [f for f in self.features if f in df.columns]
            
            logging.info(f"🔍 DEBUG FEATURES: {features_disponibili}")
            
            if not features_disponibili:
                logging.warning("⚠️ Nessuna feature disponibile")
                return 0
            
            X = df[features_disponibili].values
            y = ((df['close'].shift(-1) - df['close']) / df['close']).fillna(0).values
            
            self.scaler = MinMaxScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_scaled, y)
            
            accuracy = self.model.score(X_scaled, y)
            self.training_accuracy = max(0, min(accuracy, 1.0))
            self.last_training = datetime.now().timestamp()
            
            os.makedirs("models", exist_ok=True)
            with open("models/rf_model.pkl", 'wb') as f:
                pickle.dump(self.model, f)
            
            logging.info(f"✅ RandomForest Training: Accuracy {self.training_accuracy:.2%}")
            return self.training_accuracy
        except Exception as e:
            logging.error(f"❌ Errore training RandomForest: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return 0
    
    def predici(self, dati_recenti):
        """Predice direzione e prezzo con RandomForest"""
        try:
            logging.info(f"🔍 DEBUG PREDICT: Model={self.model is not None}, Scaler={self.scaler is not None}, Dati={len(dati_recenti) if dati_recenti else 0}")
            
            if not self.model or not self.scaler or not dati_recenti:
                logging.warning("⚠️ Predizione fallback: modello o dati mancanti")
                return self._predizione_fallback()
            
            if len(dati_recenti) < 24:
                logging.warning("⚠️ Dati recenti insufficienti (< 24)")
                return self._predizione_fallback()
            
            df = pd.DataFrame(dati_recenti[-24:])
            features_disponibili = [f for f in self.features if f in df.columns]
            
            if not features_disponibili:
                return self._predizione_fallback()
            
            X = df[features_disponibili].values
            X_scaled = self.scaler.transform(X)
            
            variazione = self.model.predict(X_scaled[-1:].reshape(1, -1))[0]
            prezzo_att = dati_recenti[-1]['close']
            prezzo_pred = prezzo_att * (1 + variazione)
            
            confidence = max(0, min(self.training_accuracy * 100, 100))
            
            if variazione > 0.02:
                direzione = 'BULLISH'
            elif variazione < -0.02:
                direzione = 'BEARISH'
            else:
                direzione = 'NEUTRAL'
            
            logging.info(f"🔮 RandomForest: {direzione} | Var: {variazione*100:+.2f}% | Conf: {confidence:.1f}%")
            
            return {
                'prezzo_predetto': prezzo_pred,
                'variazione_perc': variazione * 100,
                'direzione': direzione,
                'confidence': confidence,
                'is_valido': confidence >= 30,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logging.error(f"❌ Errore predizione RandomForest: {e}")
            return self._predizione_fallback()
    
    def _predizione_fallback(self):
        """Predizione di fallback quando modello non disponibile"""
        return {
            'prezzo_predetto': 0,
            'variazione_perc': 0,
            'direzione': 'NEUTRAL',
            'confidence': 0,
            'is_valido': False,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_status(self):
        """Ritorna status del predictor"""
        return {
            'modello_caricato': self.model is not None,
            'scaler_caricato': self.scaler is not None,
            'training_accuracy': f"{self.training_accuracy:.2%}",
            'last_training': (
                datetime.fromtimestamp(self.last_training).isoformat() 
                if self.last_training else 'Mai'
            )
        }
