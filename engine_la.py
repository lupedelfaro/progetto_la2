# -*- coding: utf-8 -*-
# engine_la.py - VERSIONE MULTITIMEFRAME DEFINITIVA + HYBRID LOGIC v5.0 + LSTM

import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import numpy as np
import time
import logging
import asset_list  
import config_la  

class EngineLA:
    def __init__(self, exchange_id='kraken'):
        self.exchange = getattr(ccxt, exchange_id)({
            'apiKey': config_la.KRAKEN_KEY,
            'secret': config_la.KRAKEN_SECRET,
            'enableRateLimit': True,
            'timeout': 30000,
            'options': {
                'defaultType': 'spot',
            }
        })
        self.exchange.load_markets()
        self.cache_macro = {'timestamp': 0, 'data': {}, 'sentiment': 'NEUTRAL'}
        self.cache_timeout = 300  # 5 minuti

    def get_macro_data(self):
        """Recupera dati macro (DXY, NASDAQ) con cache"""
        try:
            if time.time() - self.cache_macro['timestamp'] < self.cache_timeout:
                return self.cache_macro['data'], self.cache_macro['sentiment']
            dxy = yf.Ticker("DX-Y.NYB").history(period="2d", timeout=15)
            ndx = yf.Ticker("^IXIC").history(period="2d", timeout=15)
            if dxy.empty or ndx.empty: 
                return {}, "NEUTRAL"
            if len(dxy) < 2 or len(ndx) < 2:
                return {}, "NEUTRAL"
            dxy_price = float(dxy['Close'].iloc[-1])
            dxy_prev = float(dxy['Close'].iloc[-2])
            ndx_price = float(ndx['Close'].iloc[-1])
            ndx_prev = float(ndx['Close'].iloc[-2])
            if dxy_prev == 0 or ndx_prev == 0:
                return {}, "NEUTRAL"
            res = {
                "DXY": {"price": dxy_price, "change": (dxy_price / dxy_prev) - 1},
                "NASDAQ": {"price": ndx_price, "change": (ndx_price / ndx_prev) - 1}
            }
            if res["NASDAQ"]["change"] > 0 and res["DXY"]["change"] < 0:
                sentiment = "BULLISH"
            elif res["NASDAQ"]["change"] < 0 and res["DXY"]["change"] > 0:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"
            self.cache_macro = {'timestamp': time.time(), 'data': res, 'sentiment': sentiment}
            return res, sentiment
        except Exception as e:
            logging.error(f"Errore recupero macro data: {e}")
            return {}, "NEUTRAL"

    def get_dati_multitimeframe(self, ticker, exchange=None):
        """
        Recupera dati OHLCV per più timeframe. Ticker viene risolto da asset_list.ASSET_MAPPING
        """
        ex = exchange if exchange else self.exchange
        is_futures = hasattr(ex, 'futures') and ex.futures or 'futures' in str(type(ex)).lower()
        try:
            # Timeframe mapping
            timeframes = {
                '15m': ('15m' if is_futures else '15', 60),
                '1h':  ('1h'  if is_futures else '60', 100),
                '4h':  ('4h'  if is_futures else '240', 60),
                '1D':  ('1d'  if is_futures else '1440', 30)
            }
            dati_multitf = {}
            for tf, (tf_kraken, limit) in timeframes.items():
                try:
                    ohlcv = ex.fetch_ohlcv(ticker, timeframe=tf_kraken, limit=limit)
                    if not ohlcv or len(ohlcv) < 20:
                        logging.warning(f"Dati insufficienti per {ticker} {tf}")
                        continue
                    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
                    if df['close'].iloc[-1] <= 0 or df['volume'].sum() == 0:
                        logging.warning(f"Dati invalidi per {ticker} {tf}")
                        continue
                    df['rsi'] = ta.rsi(df['close'], length=14)
                    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
                    df['sma_50'] = ta.sma(df['close'], length=50)
                    df['sma_200'] = ta.sma(df['close'], length=200)
                    macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
                    if macd_result is not None and not macd_result.empty:
                        df['macd'] = macd_result.iloc[:, 0]
                        df['macd_signal'] = macd_result.iloc[:, 1]
                    else:
                        df['macd'] = 0
                        df['macd_signal'] = 0
                    avg_vol = df['volume'].tail(20).mean()
                    df['vsa'] = np.where(df['volume'] > avg_vol * 1.5, "HIGH_VOL", "NORMAL")
                    prezzo_attuale = float(df['close'].iloc[-1])
                    sma50 = float(df['sma_50'].iloc[-1]) if pd.notna(df['sma_50'].iloc[-1]) else prezzo_attuale
                    sma200 = float(df['sma_200'].iloc[-1]) if pd.notna(df['sma_200'].iloc[-1]) else prezzo_attuale
                    if prezzo_attuale > sma50 > sma200:
                        trend = "UPTREND"
                    elif prezzo_attuale < sma50 < sma200:
                        trend = "DOWNTREND"
                    else:
                        trend = "NEUTRAL"
                    dati_multitf[tf] = {
                        'prezzo': prezzo_attuale,
                        'rsi': float(df['rsi'].iloc[-1]) if pd.notna(df['rsi'].iloc[-1]) else 50,
                        'atr': float(df['atr'].iloc[-1]) if pd.notna(df['atr'].iloc[-1]) else 0,
                        'sma_50': sma50,
                        'sma_200': sma200,
                        'trend': trend,
                        'vsa': df['vsa'].iloc[-1],
                        'macd': float(df['macd'].iloc[-1]) if 'macd' in df and pd.notna(df['macd'].iloc[-1]) else 0,
                        'volume': float(df['volume'].iloc[-1]),
                        'volume_sma': float(avg_vol)
                    }
                except Exception as e:
                    logging.error(f"Errore timeframe {tf} su {ticker}: {e}")
                    continue
            if not dati_multitf:
                logging.error(f"Dati multitimeframe totalmente assenti per {ticker}")
                return None
            return {
                'symbol': ticker,
                'multitimeframe': dati_multitf,
                'prezzo_real': dati_multitf.get('1h', {}).get('prezzo', 0),
                'rsi': dati_multitf.get('1h', {}).get('rsi', 50),
                'atr': dati_multitf.get('1h', {}).get('atr', 0),
                'vsa_status': dati_multitf.get('1h', {}).get('vsa', 'NORMAL'),
                'trend_1d': dati_multitf.get('1D', {}).get('trend', 'NEUTRAL'),
                'trend_4h': dati_multitf.get('4h', {}).get('trend', 'NEUTRAL'),
                'trend_1h': dati_multitf.get('1h', {}).get('trend', 'NEUTRAL')
            }
        except Exception as e:
            logging.error(f"Errore recupero dati multitimeframe per {ticker}: {e}")
            return None

    def get_dati_storici_per_lstm(self, ticker, exchange=None):
        """
        Recupera ultimi 30 giorni di dati OHLCV per LSTM training.
        """
        ex = exchange if exchange else self.exchange
        try:
            is_futures = hasattr(ex, 'futures') and ex.futures or 'futures' in str(type(ex)).lower()
            tf_lstm = '1h' if is_futures else '60'
            ohlcv = ex.fetch_ohlcv(ticker, timeframe=tf_lstm, limit=720)
            if not ohlcv or len(ohlcv) < 100:
                logging.warning(f"❌ Dati LSTM insufficienti per {ticker}")
                return None
            df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            df['ts'] = pd.to_datetime(df['ts'], unit='ms')
            df.set_index('ts', inplace=True)
            df.sort_index(inplace=True)
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
            df['cvd'] = (df['volume'] * (df['close'].diff() > 0).astype(int)).cumsum()
            df['rsi'] = df['rsi'].ffill().fillna(50)
            df['atr'] = df['atr'].ffill().fillna(0)
            df['vwap'] = df['vwap'].ffill().fillna(df['close'])
            df['cvd'] = df['cvd'].ffill().fillna(0)
            dati_lista = df[['close', 'high', 'low', 'volume', 'rsi', 'atr', 'vwap', 'cvd']].reset_index().to_dict('records')
            logging.info(f"✅ Dati LSTM puliti per {ticker}: {len(dati_lista)} candele")
            return dati_lista
        except Exception as e:
            logging.error(f"❌ Errore recupero dati LSTM per {ticker}: {e}")
            return None

    def get_market_context(self, asset, exchange=None):
        """Recupera contesto di mercato (VWAP, POC, CVD)"""
        try:
            ex = exchange if exchange else self.exchange
            ohlcv = ex.fetch_ohlcv(asset, timeframe='1h', limit=100)
            if not ohlcv: return None
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
            df['vwap'] = df['vwap'].ffill().fillna(df['close'])
            price_bins = pd.cut(df['close'], bins=20)
            poc = df.groupby(price_bins, observed=True)['volume'].sum().idxmax().mid
            df['delta'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
            cvd = df['delta'].rolling(window=24).sum().ffill().fillna(0).iloc[-1]
            return {
                'vwap': float(df['vwap'].iloc[-1]),
                'poc': float(poc),
                'cvd': float(cvd),
                'last_close': float(df['close'].iloc[-1])
            }
        except Exception as e:
            logging.error(f"❌ Errore calcolo contesto per {asset}: {e}")
            return None

    def get_guardrail_logico(self, dati, contesto):
        """
        Calcola guardrail logico per Hybrid Mode
        """
        try:
            if not dati or 'multitimeframe' not in dati:
                return {'voto_minimo': 0, 'voto_massimo': 10, 'ragioni': ['Dati insufficienti']}
            if not contesto:
                return {'voto_minimo': 0, 'voto_massimo': 10, 'ragioni': ['Contesto insufficiente']}
            mtf = dati['multitimeframe']
            voto_min = 0
            voto_max = 10
            ragioni = []
            trend_1d = mtf.get('1D', {}).get('trend', 'NEUTRAL')
            if trend_1d == 'UPTREND':
                voto_min = 5
                ragioni.append("Trend 1D UP: favorisci LONG")
            elif trend_1d == 'DOWNTREND':
                voto_max = 5
                ragioni.append("Trend 1D DOWN: limita LONG")
            rsi_1h = mtf.get('1h', {}).get('rsi', 50)
            if rsi_1h > 75:
                voto_max = min(voto_max, 6)
                ragioni.append(f"RSI 1h alto ({rsi_1h:.0f}): max voto 6")
            elif rsi_1h < 25:
                voto_min = max(voto_min, 5)
                ragioni.append(f"RSI 1h basso ({rsi_1h:.0f}): min voto 5")
            cvd = contesto.get('cvd', 0)
            if cvd < -10:
                voto_max = min(voto_max, 5)
                ragioni.append(f"CVD negativo ({cvd:.1f}): limita LONG")
            elif cvd > 10:
                voto_min = max(voto_min, 6)
                ragioni.append(f"CVD positivo ({cvd:.1f}): favorisci LONG")
            prezzo = dati.get('prezzo_real', 0)
            vwap = contesto.get('vwap', prezzo)
            differenza_pct = ((prezzo - vwap) / vwap * 100) if vwap > 0 else 0
            if prezzo > vwap * 1.02:
                if trend_1d != 'UPTREND':
                    voto_max = min(voto_max, 6)
                    ragioni.append(f"Prezzo sopra VWAP (+{differenza_pct:.1f}%): cautela")
            elif prezzo < vwap * 0.98:
                if trend_1d != 'DOWNTREND':
                    voto_min = max(voto_min, 6)
                    ragioni.append(f"Prezzo sotto VWAP ({differenza_pct:.1f}%): buy signal")
            atr_1h = mtf.get('1h', {}).get('atr', 0)
            atr_4h = mtf.get('4h', {}).get('atr', 0)
            if atr_1h > 0 and atr_4h > 0:
                vol_ratio = atr_1h / atr_4h
                if vol_ratio > 1.5:
                    voto_max = min(voto_max, 7)
                    ragioni.append(f"Volatilità 1h alta: riduci aggressività")
            asset = dati.get('symbol')
            oi_data = self.get_open_interest_data(asset)
            if oi_data:
                oi_delta = oi_data.get('oi_24h', 0)
                trend_1h = dati.get('trend_1h', 'NEUTRAL')
                if trend_1h == 'UPTREND' and oi_delta > 2:
                    voto_min = max(voto_min, 6)
                    ragioni.append(f"OI in aumento (+{oi_delta:.1f}%): Forza Istituzionale")
                elif trend_1h == 'UPTREND' and oi_delta < -2:
                    voto_max = min(voto_max, 5)
                    ragioni.append(f"OI in calo ({oi_delta:.1f}%): Rialzo debole/Squeeze")
                elif trend_1h == 'DOWNTREND' and oi_delta > 2:
                    voto_max = min(voto_max, 4)
                    ragioni.append(f"OI in aumento su DownTrend: Accumulo Short")
            return {
                'voto_minimo': int(voto_min),
                'voto_massimo': int(voto_max),
                'ragioni': ragioni
            }
        except Exception as e:
            logging.error(f"Errore calcolo guardrail: {e}")
            return {'voto_minimo': 0, 'voto_massimo': 10, 'ragioni': ['Errore calcolo guardrail']}

    def get_open_interest_data(self, asset):
        """
        Recupera Open Interest globale. Mappa i ticker di asset_list.py ai codici API di Kraken Futures.
        """
        try:
            ticker_mappato = asset_list.ASSET_MAPPING.get(asset, asset)
            # Configurazione mapping dinamica: lascia la logica ai contenuti di asset_list.py
            api_mapping = {
                'XXBTZUSD': 'PI_XBTUSD',
                'XETHZUSD': 'PI_ETHUSD',
                'BTC/USD:BTC': 'PI_XBTUSD',
                'ETH/USD:ETH': 'PI_ETHUSD'
            }
            target_api = api_mapping.get(ticker_mappato)
            if not target_api:
                logging.warning("Asset non trovato in mapping OI/futures.")
                return None
            import requests
            url = "https://futures.kraken.com/derivatives/api/v3/tickers"
            response = requests.get(url, timeout=10).json()
            if response.get('result') == 'success':
                for t in response.get('tickers', []):
                    if t.get('symbol') == target_api:
                        return {
                            "oi": float(t.get('openInterest', 0)),
                            "oi_24h": float(t.get('change24h', 0)),
                            "prezzo_f": float(t.get('last', 0))
                        }
            return None
        except Exception as e:
            logging.error(f"⚠️ Errore recupero OI (Nessun conflitto): {e}")
            return None

    def get_full_analysis(self, asset, exchange_futures=None):
        """
        Restituisce tutto il pacchetto dati per il brain.
        """
        ticker = asset_list.ASSET_MAPPING.get(asset, asset)  # mapping sempre esterno!
        dati_mtf = self.get_dati_multitimeframe(ticker)
        if not dati_mtf:
            logging.warning(f"[ENGINE] Dati multitimeframe assenti per {asset} ({ticker})")
            return None
        contesto = self.get_market_context(ticker, exchange=exchange_futures)
        macro_data, sentiment_macro = self.get_macro_data()
        oi_data = self.get_open_interest_data(asset)
        dati_lstm = self.get_dati_storici_per_lstm(ticker, exchange=exchange_futures)
        contesto_istituzionale = {
            "macro": macro_data,
            "macro_sentiment": sentiment_macro,
            "volume_profile": {
                "poc": contesto.get('poc') if contesto else None,
                "cvd": contesto.get('cvd') if contesto else None,
                "vwap": contesto.get('vwap') if contesto else None
            },
            "open_interest": oi_data,
            "guardrail": self.get_guardrail_logico(dati_mtf, contesto)
        }
        return {
            "dati_tecnici": dati_mtf,
            "contesto_istituzionale": contesto_istituzionale,
            "dati_lstm": dati_lstm
        }