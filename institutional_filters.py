import requests
import logging
import asset_list  # L'unica fonte di verità

class InstitutionalFilters:
    FUNDING_HIGH_THRESHOLD = 0.0003
    FUNDING_LOW_THRESHOLD = -0.0003

    def __init__(self):
        self.logger = logging.getLogger("InstitutionalFilters")

    def is_spot(self, asset):
        # Casa spot: asset simbolo reale come in asset_list
        return asset in ['XXBTZUSD', 'XETHZUSD']

    def is_perpetual(self, asset):
        # Casa perpetual: asset simbolo reale come in asset_list
        return asset in ['BTCPERP', 'ETHPERP']

    def get_kraken_spot_ticker(self, asset):
        # Usa mapping per trovare il ticker Kraken (XXBTZUSD, XETHZUSD, ecc)
        return asset_list.ASSET_MAPPING.get(asset, asset)

    def get_institutional_data(self, asset):
        try:
            # --- CASO 1: SPOT ---
            if self.is_spot(asset):
                kraken_ticker = self.get_kraken_spot_ticker(asset)
                url = f"https://api.kraken.com/0/public/Ticker?pair={kraken_ticker}"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json().get('result', {})
                    if not data:
                        self.logger.warning(f"Nessun risultato ticker Kraken per {kraken_ticker}")
                        return "Dati Spot non disp."
                    main_key = list(data.keys())[0]
                    asset_data = data.get(main_key, {})
                    ask_raw = asset_data.get('a', [None])
                    bid_raw = asset_data.get('b', [None])
                    ask = float(ask_raw[0]) if ask_raw and ask_raw[0] is not None else None
                    bid = float(bid_raw[0]) if bid_raw and bid_raw[0] is not None else None
                    if ask is not None and bid is not None and ask > 0:
                        spread = ((ask - bid) / ask) * 100
                        return f"Spot Spread: {spread:.4f}%"
                    else:
                        self.logger.error(f"Valori ask/bid non validi per {kraken_ticker}: ask={ask}, bid={bid}")
                        return "Dati Spot non disp."
                self.logger.error(f"Errore HTTP {resp.status_code} Kraken per {kraken_ticker}")
                return "Dati Spot non disp."

            # --- CASO 2: PERPETUAL ---
            if self.is_perpetual(asset):
                perp_symbol = self.get_kraken_spot_ticker(asset)
                url = "https://futures.kraken.com/derivatives/api/v3/funding_rates"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for f in data.get('fundingRates', []):
                        # Match simbolo esatto (BTC/USD:BTC vs ETH/USD:ETH, ecc)
                        if f['symbol'] == perp_symbol:
                            rate_raw = f.get('fundingRate', None)
                            if rate_raw is not None:
                                try:
                                    rate = float(rate_raw)
                                except Exception as err:
                                    self.logger.error(f"Conversione fundingRate fallita per {perp_symbol}: {err}")
                                    rate = 0.0
                                bias = "Neutrale"
                                if rate > self.FUNDING_HIGH_THRESHOLD: bias = "Ribassista"
                                elif rate < self.FUNDING_LOW_THRESHOLD: bias = "Rialzista"
                                return f"Funding: {rate*100:.3f}% ({bias})"
                            else:
                                self.logger.warning(f"Funding rate non disponibile per {perp_symbol}")
                    return "Funding: 0.000% (Neutrale)"
                else:
                    self.logger.error(f"Errore HTTP {response.status_code} Kraken Futures")
                    return "Funding non disp."

            return "Tipo asset non gestito"

        except Exception as e:
            self.logger.error(f"Errore analisi istituzionale per {asset}: {e}")
            return "Analisi non disp."

    def get_institutional_analysis(self, asset):
        """Metodo di interfaccia per il bot"""
        return self.get_institutional_data(asset)

    def validate_entry_institutional(self, asset, direction, price):
        """Validazione per il BrainLA"""
        analysis = self.get_institutional_analysis(asset)
        return True, analysis