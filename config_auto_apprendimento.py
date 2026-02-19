# -*- coding: utf-8 -*-
# config_auto_apprendimento.py - Configurazione centralizzata del bot

# ========================================================================
# GEMINI AI
# ========================================================================
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_RETRIES = 5           # ← MODIFICATO: era 3, ora 5 tentativi
GEMINI_RETRY_DELAY = 10       # ← MODIFICATO: era 2, era 5 secondi ora 10
GEMINI_REQUEST_DELAY = 5    # ← MODIFICATO: era 1, era 3 ora 5 secondi tra richieste

# ========================================================================
# GUARDRAIL LOGICO
# ========================================================================
VOTO_MIN_DEFAULT = 0
VOTO_MAX_DEFAULT = 10

# ========================================================================
# POSITION SIZING & KELLY FRACTION
# ========================================================================
KELLY_FRACTION = 0.5  # Frazione del Kelly Criterion (50% = cautela)
SIZE_MINIMO_FALLBACK = 0.001  # Size minima se calcolo fallisce
ATR_FALLBACK = 100  # ATR di fallback se dati invalidi

# ========================================================================
# TRAILING STOP LOSS
# ========================================================================
TRAILING_SCUDO_ATR_MULT = 1.5  # Moltiplicatore ATR per scudo
TRAILING_MOON_ATR_MULT = 0.5   # Moltiplicatore ATR per moon phase

# ========================================================================
# MULTITIMEFRAME
# ========================================================================
TIMEFRAMES = ['15m', '1h', '4h', '1D']
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 25

# ========================================================================
# FEEDBACK ENGINE
# ========================================================================
MAX_LEZIONI = 100  # Mantieni ultime 100 operazioni
PESO_RECENTI = 3   # Peso moltiplicativo per trade recenti
RECENTI_COUNT = 10 # Quanti trade sono "recenti"

# ========================================================================
# BOT BEHAVIOR
# ========================================================================
LIVE_MODE = False  # False = Simulazione, True = Ordini reali su Kraken
TELEGRAM_ENABLED = True
MONITOR_INTERVAL = 120  # Secondi tra aggiornamenti

# ========================================================================
# RISK MANAGEMENT
# ========================================================================
RISK_PER_TRADE = 0.03  # 3% del saldo per trade
MAX_CONCURRENT_POSITIONS = 3  # Max posizioni aperte contemporaneamente