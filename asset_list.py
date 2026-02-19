# --- DEFINISCI GLI ASSET SPOT E FUTURES ---
SPOT = [
    'XXBTZUSD',
    'XETHZUSD'
    # altri spot se servono...
]

#FUTURES = [
    #'BTC/USD:BTC',
    #'ETH/USD:ETH'
# --- CONFIGURAZIONE ASSET ---

SPOT = [
    'XXBTZUSD',
    'XETHZUSD'
]

# Invece di commentare la riga, la rendiamo una lista vuota
# Così il bot non dà errore "NameError" ma non analizza nulla qui dentro
FUTURES = [] 

# Ora questa riga non darà più errore perché FUTURES esiste (è vuota)
ATTIVI = SPOT #+ FUTURES

ASSET_MAPPING = {
    # Mapping spot
    'XXBTZUSD':      'XXBTZUSD',
    'XETHZUSD':      'XETHZUSD',
    
    # Se vuoi aggiungere i futures in futuro, toglierai i # qui sotto
    # 'BTCPERP':       'BTC/USD:BTC',
    # 'ETHPERP':       'ETH/USD:ETH'
}

def get_trading_ticker_and_type(coin):
    # Prende il ticker reale dal mapping, se non esiste usa il nome originale
    trading_ticker = ASSET_MAPPING.get(coin, coin)
    
    # Determina se è futures o spot (restituisce True o False)
    # Usiamo una lista vuota di backup se FUTURES o SPOT non fossero definiti
    is_futures = trading_ticker in (FUTURES if 'FUTURES' in locals() or 'FUTURES' in globals() else [])
    is_spot = trading_ticker in (SPOT if 'SPOT' in locals() or 'SPOT' in globals() else [])
    
    # RESTITUISCE ESATTAMENTE 3 VALORI
    return trading_ticker, is_futures, is_spot
# --- TEST ---
if __name__ == "__main__":
    for asset in ATTIVI:
        t, f, s = get_trading_ticker_and_type(asset)
        print(f"Asset: {asset} | Ticker: {t} | Futures: {f} | Spot: {s}")