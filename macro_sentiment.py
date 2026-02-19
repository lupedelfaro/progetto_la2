"""
Analisi Macro Sentiment
- Fear & Greed Index (Alternative.me)
- Position Sizing Adjustment basato su sentiment estremo
"""

import requests
import logging
from datetime import datetime

class MacroSentiment:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Soglie Fear & Greed
        self.EXTREME_FEAR_THRESHOLD = 20  # < 20 = Extreme Fear
        self.FEAR_THRESHOLD = 40          # 20-40 = Fear
        self.GREED_THRESHOLD = 60         # 60-80 = Greed
        self.EXTREME_GREED_THRESHOLD = 80 # > 80 = Extreme Greed
        
        # Multiplier per position sizing
        self.SIZE_REDUCTION_EXTREME = 0.5  # Riduci size al 50% in estremi
        self.SIZE_REDUCTION_MEDIUM = 0.75  # Riduci size al 75% in fear/greed
        
        self.last_fgi_value = None
        self.last_fgi_classification = None
    
    def get_fear_greed_index(self):
        """
        Recupera Fear & Greed Index da Alternative.me
        
        Returns:
            dict: {
                'value': int (0-100),
                'classification': str ('Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'),
                'timestamp': datetime
            }
            None: Se errore API
        """
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            fgi_data = data['data'][0]
            
            value = int(fgi_data['value'])
            classification = fgi_data['value_classification']
            timestamp = datetime.fromtimestamp(int(fgi_data['timestamp']))
            
            self.last_fgi_value = value
            self.last_fgi_classification = classification
            
            result = {
                'value': value,
                'classification': classification,
                'timestamp': timestamp
            }
            
            self.logger.info(f"📊 Fear & Greed Index: {value} ({classification})")
            
            return result
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Errore API Fear & Greed: {e}")
            return None
        
        except (KeyError, ValueError) as e:
            self.logger.error(f"❌ Errore parsing Fear & Greed: {e}")
            return None
    
    def get_position_size_multiplier(self):
        """
        Calcola multiplier per position sizing basato su F&G Index
        
        Returns:
            tuple: (float, str) → (multiplier, reason)
        """
        fgi = self.get_fear_greed_index()
        
        # Se API non disponibile, non riduciamo size (fail-safe)
        if fgi is None:
            return 1.0, "F&G Index non disponibile (size normale)"
        
        value = fgi['value']
        classification = fgi['classification']
        
        # EXTREME FEAR (<20): Riduci size (possibile cascata di vendite)
        if value < self.EXTREME_FEAR_THRESHOLD:
            reason = f"🔴 EXTREME FEAR ({value}/100) - Size ridotto al 50%"
            self.logger.warning(reason)
            return self.SIZE_REDUCTION_EXTREME, reason
        
        # FEAR (20-40): Riduci size moderatamente
        elif value < self.FEAR_THRESHOLD:
            reason = f"🟠 FEAR ({value}/100) - Size ridotto al 75%"
            self.logger.info(reason)
            return self.SIZE_REDUCTION_MEDIUM, reason
        
        # EXTREME GREED (>80): Riduci size (possibile top locale)
        elif value > self.EXTREME_GREED_THRESHOLD:
            reason = f"🔴 EXTREME GREED ({value}/100) - Size ridotto al 50%"
            self.logger.warning(reason)
            return self.SIZE_REDUCTION_EXTREME, reason
        
        # GREED (60-80): Riduci size moderatamente
        elif value > self.GREED_THRESHOLD:
            reason = f"🟠 GREED ({value}/100) - Size ridotto al 75%"
            self.logger.info(reason)
            return self.SIZE_REDUCTION_MEDIUM, reason
        
        # NEUTRAL (40-60): Size normale
        else:
            reason = f"🟢 NEUTRAL ({value}/100) - Size normale"
            self.logger.info(reason)
            return 1.0, reason
    
    def should_trade_in_extreme_conditions(self):
        """
        Verifica se è prudente tradare in condizioni estreme
        (Opzionale: può essere usato per bloccare completamente trade)
        
        Returns:
            tuple: (bool, str) → (can_trade, reason)
        """
        fgi = self.get_fear_greed_index()
        
        if fgi is None:
            return True, "F&G Index non disponibile (trade permesso)"
        
        value = fgi['value']
        
        # Opzionale: blocca trade in estremi assoluti
        if value < 10:
            reason = f"⛔ EXTREME PANIC ({value}/100) - Mercato irrazionale"
            return False, reason
        
        if value > 90:
            reason = f"⛔ EXTREME EUPHORIA ({value}/100) - Mercato irrazionale"
            return False, reason
        
        return True, f"Sentiment: {fgi['classification']} ({value}/100)"


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    sentiment = MacroSentiment()
    
    print("\n=== TEST FEAR & GREED INDEX ===\n")
    
    # Test 1: Get current F&G
    fgi = sentiment.get_fear_greed_index()
    if fgi:
        print(f"Current F&G: {fgi['value']} - {fgi['classification']}")
        print(f"Timestamp: {fgi['timestamp']}\n")
    
    # Test 2: Position size multiplier
    multiplier, reason = sentiment.get_position_size_multiplier()
    print(f"Position Size Multiplier: {multiplier:.2f}x")
    print(f"Reason: {reason}\n")
    
    # Test 3: Extreme conditions check
    can_trade, trade_reason = sentiment.should_trade_in_extreme_conditions()
    print(f"Can Trade: {can_trade}")
    print(f"Reason: {trade_reason}\n")
