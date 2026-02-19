# -*- coding: utf-8 -*-
# backtest_strategy_la.py - COMPREHENSIVE BACKTESTING SYSTEM v2.0
# Simulates the REAL L&A Bot strategy using actual Kraken data
# Integrates: EngineLA, BrainLA, ManagerLA, TradeManager, PositionTracker, FeedbackEngine

import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
import json
import time
from datetime import datetime
import yfinance as yf

# Import bot components
import config_la
from engine_la import EngineLA
from brain_la import BrainLA
from manager_la import ManagerLA
from trade_manager_advanced_la import TradeManager
from position_tracker_la import PositionTracker
from feedback_engine import FeedbackEngine
import traceback

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_historical_data(symbol='BTC/USD', timeframe='1h', limit=8760):
    """
    Fetches real historical data from Kraken
    Falls back to yfinance if Kraken API fails
    
    Args:
        symbol: Trading pair (BTC/USD, ETH/USD)
        timeframe: Candle timeframe (1h, 4h, 1d)
        limit: Number of candles to fetch
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        logger.info(f"📊 Fetching {limit} candles of {symbol} ({timeframe}) from Kraken...")
        
        # Initialize Kraken exchange
        exchange = ccxt.kraken({
            'apiKey': config_la.KRAKEN_KEY,
            'secret': config_la.KRAKEN_SECRET,
            'enableRateLimit': True,
            'timeout': 30000
        })
        
        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv or len(ohlcv) < 100:
            raise Exception(f"Insufficient data from Kraken: {len(ohlcv)} candles")
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        logger.info(f"✅ Fetched {len(df)} candles from Kraken")
        return df
        
    except Exception as e:
        logger.warning(f"⚠️ Kraken API failed: {e}")
        logger.exception("Traceback fetch_historical_data:")
        traceback.print_exc()
        logger.info("📊 Falling back to yfinance...")
        
        # Fallback to yfinance
        try:
            ticker_map = {
                'BTC/USD': 'BTC-USD',
                'ETH/USD': 'ETH-USD',
                'BTC/USDT': 'BTC-USD',
                'ETH/USDT': 'ETH-USD'
            }
            
            yf_ticker = ticker_map.get(symbol, 'BTC-USD')
            
            # Determine yfinance interval
            interval_map = {
                '1h': '1h',
                '4h': '1h',  # yfinance doesn't support 4h, we'll resample
                '1d': '1d',
                '15m': '15m'
            }
            yf_interval = interval_map.get(timeframe, '1h')
            
            # Download data
            df = yf.download(yf_ticker, period='1y', interval=yf_interval, progress=False)
            
            if df.empty:
                raise Exception("No data from yfinance")
            
            # Standardize column names
            df.columns = [c.lower() for c in df.columns]
            
            # Resample if needed (e.g., 1h to 4h)
            if timeframe == '4h' and yf_interval == '1h':
                df = df.resample('4h').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            
            logger.info(f"✅ Fetched {len(df)} candles from yfinance")
            return df
            
        except Exception as e2:
            logger.error(f"❌ Both Kraken and yfinance failed: {e2}")
            logger.exception("Traceback fetch_historical_data (yfinance fallback):")
            traceback.print_exc()
            raise Exception("Unable to fetch historical data from any source")


# ============================================================================
# BACKTEST ENGINE
# ============================================================================

class BacktestEngine:
    """
    Comprehensive backtesting engine that simulates the real L&A Bot strategy
    """
    
    def __init__(self, initial_capital=10000, risk_per_trade=0.03, fast_mode=True):
        """
        Initialize backtest engine with all bot components
        
        Args:
            initial_capital: Starting capital in USD
            risk_per_trade: Risk per trade (default 3%)
            fast_mode: If True, skip Gemini API calls and use deterministic logic only
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.fast_mode = fast_mode
        
        logger.info(f"🚀 Initializing BacktestEngine (Fast Mode: {fast_mode})")
        
        # Initialize bot components
        try:
            self.engine = EngineLA(exchange_id='kraken')
            self.feedback_engine = FeedbackEngine()
            self.brain = BrainLA(api_key=config_la.GEMINI_KEY, feedback_engine=self.feedback_engine)
            self.manager = ManagerLA(account_balance=initial_capital, risk_per_trade=risk_per_trade)
            
            # Position tracking (use separate file for backtest)
            self.position_tracker = PositionTracker(file_posizioni='backtest_positions.json')
            
            # Trade manager (no telegram alerts in backtest)
            self.trade_manager = TradeManager(
                position_tracker=self.position_tracker,
                telegram_alerts=None
            )
            
            logger.info("✅ All bot components initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing components: {e}")
            logger.exception("Traceback __init__:")
            traceback.print_exc()
            raise
        
        # Statistics tracking
        self.trades = []
        self.equity_curve = []
        self.commission_rate = 0.001  # 0.1% per trade
        
        # Vote threshold (from bot config)
        self.SOGLIA_VOTO = 6.0
    
    def _calcola_voto_deterministico(self, dati, contesto_istituzionale):
        """
        Deterministic vote calculation (fallback when Gemini is not available)
        Uses only technical logic without AI
        
        Args:
            dati: Technical data from engine
            contesto_istituzionale: Market context (VWAP, CVD, etc.)
        
        Returns:
            float: Vote from 0-10
        """
        try:
            voto = 5  # Base vote
            
            # Multitimeframe analysis
            mtf = dati.get('multitimeframe', {})
            
            # 1D trend (most important)
            trend_1d = mtf.get('1D', {}).get('trend', 'NEUTRAL')
            if trend_1d == 'UPTREND':
                voto += 2
            elif trend_1d == 'DOWNTREND':
                voto -= 1
            
            # 4h trend (confirmation)
            trend_4h = mtf.get('4h', {}).get('trend', 'NEUTRAL')
            if trend_4h == 'UPTREND':
                voto += 1
            elif trend_4h == 'DOWNTREND':
                voto -= 0.5
            
            # RSI (avoid overbought/oversold)
            rsi_1h = mtf.get('1h', {}).get('rsi', 50)
            if 40 < rsi_1h < 60:
                voto += 1
            elif rsi_1h > 75:
                voto -= 1
            elif rsi_1h < 25:
                voto += 0.5
            
            # CVD (cumulative volume delta)
            if contesto_istituzionale:
                cvd = contesto_istituzionale.get('cvd', 0)
                if cvd > 0:
                    voto += 1
                elif cvd < 0:
                    voto -= 0.5
                
                # VWAP
                prezzo = dati.get('prezzo_real', 0)
                vwap = contesto_istituzionale.get('vwap', prezzo)
                if prezzo > vwap:
                    voto += 0.5
                elif prezzo < vwap * 0.98:
                    voto += 1  # Support level
            
            # Macro sentiment
            macro_sentiment = dati.get('macro_sentiment', 'NEUTRAL')
            if macro_sentiment == 'BULLISH':
                voto += 1
            elif macro_sentiment == 'BEARISH':
                voto -= 1
            
            # Clamp to 0-10
            return max(0, min(10, voto))
            
        except Exception as e:
            logger.error(f"Error calculating deterministic vote: {e}")
            logger.exception("Traceback _calcola_voto_deterministico:")
            traceback.print_exc()
            return 5  # Neutral fallback

    def simulate_strategy(self, df, symbol='BTC/USD'):
        """
        Simulates the complete L&A Bot strategy on historical data
        
        For each candle:
        1. Calculate technical indicators via engine_la
        2. Generate AI vote via brain_la (or deterministic fallback)
        3. Apply logical guardrails
        4. Open position if vote >= 6.0
        5. Manage dynamic SL/TP (breakeven, moon phase)
        6. Close position when necessary
        """
        logger.info(f"🔄 Starting strategy simulation on {len(df)} candles...")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Period: {df.index[0]} to {df.index[-1]}")
        logger.info(f"   Vote Threshold: {self.SOGLIA_VOTO}")
        
        start_idx = 50
        
        for i in range(start_idx, len(df)):
            current_bar = df.iloc[:i+1]
            current_price = float(current_bar['close'].iloc[-1])
            current_time = df.index[i]
            
            if i % 100 == 0:
                logger.info(f"   Processing bar {i}/{len(df)} ({i*100//len(df)}%)")
            
            try:
                dati_mtf = self.engine.get_dati_multitimeframe(symbol)
                contesto_ist = self.engine.get_market_context(symbol)
                macro_data, macro_sentiment = self.engine.get_macro_data()
                dati_tecnici = {
                    'symbol': symbol,
                    'prezzo_real': current_price,
                    'multitimeframe': dati_mtf if dati_mtf else {},
                    'macro_sentiment': macro_sentiment,
                    'macro_data': macro_data,
                    'atr': dati_mtf.get('1h', {}).get('atr', 100) if dati_mtf else 100
                }
            except Exception as e:
                logger.warning(f"Error calculating indicators at bar {i}: {e}")
                logger.exception("Traceback simulate_strategy:")
                traceback.print_exc()
                continue
            
            try:
                if self.fast_mode:
                    voto = self._calcola_voto_deterministico(dati_tecnici, contesto_ist)
                    direzione = 'LONG' if voto >= self.SOGLIA_VOTO else 'FLAT'
                    sl_sugg = current_price * 0.98
                    tp_sugg = current_price * 1.04
                else:
                    guardrail = self.engine.get_guardrail_logico(dati_tecnici, contesto_ist)
                    analisi_ia = self.brain.analizza_asset(
                        dati=dati_tecnici,
                        macro_data=macro_data,
                        sentiment_globale=macro_sentiment,
                        history_feedback_generico="",
                        contesto_istituzionale=contesto_ist,
                        posizione_attuale=self.position_tracker.ottieni_posizione(symbol),
                        guardrail=guardrail
                    )
                    voto = analisi_ia.get('voto', 0)
                    direzione = analisi_ia.get('direzione', 'FLAT')
                    sl_sugg = analisi_ia.get('sl', current_price * 0.98)
                    tp_sugg = analisi_ia.get('tp', current_price * 1.04)
            except Exception as e:
                logger.warning(f"Error generating AI vote at bar {i}: {e}")
                logger.exception("Traceback simulate_strategy (voti):")
                traceback.print_exc()
                # traceback.print_exc()  # Solo se vuoi anche su stdout
                voto = self._calcola_voto_deterministico(dati_tecnici, contesto_ist)
                direzione = 'LONG' if voto >= self.SOGLIA_VOTO else 'FLAT'
                sl_sugg = current_price * 0.98
                tp_sugg = current_price * 1.04

            # PATCH ANTI-TUPLE 
            if isinstance(sl_sugg, tuple): sl_sugg = sl_sugg[0]
            if isinstance(tp_sugg, tuple): tp_sugg = tp_sugg[0]
            
            posizioni_aperte = self.position_tracker.ottieni_tutte_posizioni()
            
            if symbol in posizioni_aperte:
                posizione = posizioni_aperte[symbol]
                # PATCH ANTI-TUPLE
                sl = posizione.get('sl', 0)
                if isinstance(sl, tuple): sl = sl[0]
                tp = posizione.get('tp', 0)
                if isinstance(tp, tuple): tp = tp[0]
                direzione_pos = posizione.get('direzione', 'LONG')
                
                pnl_info = self.position_tracker._calcola_pnl(posizione, current_price)
                pnl_perc = pnl_info.get('pnl_perc', 0)
                self.position_tracker.aggiorna_pnl(symbol, current_price)
                should_close = False
                motivo = ""
                
                if direzione_pos == 'LONG':
                    if current_price <= sl:
                        should_close = True
                        motivo = 'SL'
                    elif current_price >= tp:
                        should_close = True
                        motivo = 'TP'
                elif direzione_pos == 'SHORT':
                    if current_price >= sl:
                        should_close = True
                        motivo = 'SL'
                    elif current_price <= tp:
                        should_close = True
                        motivo = 'TP'
                fase = posizione.get('fase', 0)
                if fase == 0 and pnl_perc > 1.0:
                    entry_price = posizione['p_entrata']
                    if isinstance(entry_price, tuple): entry_price = entry_price[0]
                    self.position_tracker.posizioni_aperte[symbol]['sl'] = entry_price
                    self.position_tracker.posizioni_aperte[symbol]['fase'] = 1
                    self.position_tracker.salva_posizioni()
                    logger.info(f"   🛡️ Breakeven activated for {symbol}")
                if should_close:
                    self._chiudi_trade(symbol, current_price, motivo, current_time)
            else:
                if voto >= self.SOGLIA_VOTO and direzione in ['LONG', 'SHORT']:
                    atr = dati_tecnici.get('atr', 100)
                    size = self.manager.calculate_position_size(
                        prezzo_entry=current_price,
                        stop_loss=sl_sugg,
                        voto_ia=voto,
                        atr=atr
                    )
                    if isinstance(size, tuple): size = size[0]
                    if size > 0:
                        if isinstance(sl_sugg, tuple): sl_sugg = sl_sugg[0]
                        if isinstance(tp_sugg, tuple): tp_sugg = tp_sugg[0]
                        self._apri_trade(
                            symbol=symbol,
                            direzione=direzione,
                            prezzo=current_price,
                            size=size,
                            sl=sl_sugg,
                            tp=tp_sugg,
                            voto=voto,
                            timestamp=current_time
                        )
            equity = self._calcola_equity_totale(current_price)
            self.equity_curve.append({
                'timestamp': current_time,
                'equity': equity,
                'price': current_price,
                'positions': len(posizioni_aperte)
            })
        
        logger.info(f"✅ Strategy simulation completed!")
        logger.info(f"   Total trades: {len(self.trades)}")
        logger.info(f"   Final capital: ${self.capital:.2f}")
    
    def _apri_trade(self, symbol, direzione, prezzo, size, sl, tp, voto, timestamp):
        """Records trade opening"""
        if isinstance(size, tuple): size = size[0]
        if isinstance(sl, tuple): sl = sl[0]
        if isinstance(tp, tuple): tp = tp[0]
        commission = prezzo * size * self.commission_rate
        self.capital -= commission
        self.position_tracker.apri_posizione(
            asset=symbol,
            direzione=direzione,
            entry_price=prezzo,
            size=size,
            sl=sl,
            tp=tp,
            voto=voto,
            modalita='SPOT'
        )
        logger.info(
            f"   [{timestamp}] ✅ OPENED {direzione} {symbol} @ {prezzo:.2f} "
            f"(Size: {size:.6f}, SL: {sl:.2f}, TP: {tp:.2f}, Vote: {voto:.1f})"
        )
    
    def _chiudi_trade(self, symbol, prezzo, motivo, timestamp):
        """Records trade closing"""
        posizione = self.position_tracker.ottieni_posizione(symbol)
        if not posizione:
            return
        size = posizione.get('size', 0)
        if isinstance(size, tuple): size = size[0]
        entry_price = posizione.get('p_entrata', 0)
        if isinstance(entry_price, tuple): entry_price = entry_price[0]
        sl = posizione.get('sl', 0)
        if isinstance(sl, tuple): sl = sl[0]
        tp = posizione.get('tp', 0)
        if isinstance(tp, tuple): tp = tp[0]
        pnl_info = self.position_tracker._calcola_pnl(posizione, prezzo)
        pnl_usd = pnl_info.get('pnl_usd', 0)
        pnl_perc = pnl_info.get('pnl_perc', 0)
        commission = prezzo * size * self.commission_rate
        pnl_usd -= commission
        self.capital += pnl_usd
        self.position_tracker.chiudi_posizione(symbol, prezzo, motivo)
        trade = {
            'symbol': symbol,
            'direzione': posizione.get('direzione'),
            'entry_price': entry_price,
            'exit_price': prezzo,
            'size': size,
            'pnl_usd': pnl_usd,
            'pnl_perc': pnl_perc,
            'voto': posizione.get('voto'),
            'motivo': motivo,
            'timestamp_open': posizione.get('data_apertura'),
            'timestamp_close': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        }
        self.trades.append(trade)
        logger.info(
            f"   [{timestamp}] 🛑 CLOSED {symbol} @ {prezzo:.2f} | "
            f"PnL: ${pnl_usd:+.2f} ({pnl_perc:+.2f}%) | Reason: {motivo}"
        )
    
    def _calcola_equity_totale(self, prezzo_corrente):
        equity = self.capital
        for pos in self.position_tracker.ottieni_tutte_posizioni().values():
            pnl_info = self.position_tracker._calcola_pnl(pos, prezzo_corrente)
            equity += pnl_info.get('pnl_usd', 0)
        return equity
    
    def genera_report(self):
        if not self.trades:
            logger.warning("⚠️ No trades executed during backtest")
            return {
                'total_trades': 0,
                'total_return': 0,
                'message': 'No trades executed'
            }
        df_trades = pd.DataFrame(self.trades)
        df_equity = pd.DataFrame(self.equity_curve)
        total_return = (self.capital - self.initial_capital) / self.initial_capital
        winning_trades = len(df_trades[df_trades['pnl_usd'] > 0])
        losing_trades = len(df_trades[df_trades['pnl_usd'] <= 0])
        win_rate = winning_trades / len(df_trades) if len(df_trades) > 0 else 0
        df_equity['cummax'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['cummax']) / df_equity['cummax']
        max_drawdown = df_equity['drawdown'].min()
        df_equity['returns'] = df_equity['equity'].pct_change()
        if df_equity['returns'].std() > 0:
            sharpe = (df_equity['returns'].mean() / df_equity['returns'].std()) * np.sqrt(252)
        else:
            sharpe = 0
        total_wins = df_trades[df_trades['pnl_usd'] > 0]['pnl_usd'].sum()
        total_losses = abs(df_trades[df_trades['pnl_usd'] < 0]['pnl_usd'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        report = {
            'total_trades': len(df_trades),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate * 100,
            'total_return': total_return * 100,
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'net_profit': self.capital - self.initial_capital,
            'max_drawdown': max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'profit_factor': profit_factor,
            'avg_win': df_trades[df_trades['pnl_usd'] > 0]['pnl_usd'].mean() if winning_trades > 0 else 0,
            'avg_loss': df_trades[df_trades['pnl_usd'] < 0]['pnl_usd'].mean() if losing_trades > 0 else 0,
            'largest_win': df_trades['pnl_usd'].max() if len(df_trades) > 0 else 0,
            'largest_loss': df_trades['pnl_usd'].min() if len(df_trades) > 0 else 0,
            'equity_curve': df_equity,
            'trades_df': df_trades
        }
        return report

# ============================================================================
# VISUALIZATION
# ============================================================================

def plot_backtest_results(report):
    df_eq = report['equity_curve']
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))
    axes[0].plot(df_eq['timestamp'], df_eq['equity'], linewidth=2, label='Portfolio Value', color='#2E86AB')
    axes[0].axhline(y=report['initial_capital'], color='gray', linestyle='--', 
                    label=f"Initial Capital (${report['initial_capital']:,.0f})", linewidth=1)
    axes[0].fill_between(df_eq['timestamp'], report['initial_capital'], df_eq['equity'], 
                         where=(df_eq['equity'] >= report['initial_capital']), 
                         alpha=0.3, color='green', label='Profit')
    axes[0].fill_between(df_eq['timestamp'], report['initial_capital'], df_eq['equity'], 
                         where=(df_eq['equity'] < report['initial_capital']), 
                         alpha=0.3, color='red', label='Loss')
    axes[0].set_title('Portfolio Equity Curve', fontsize=16, fontweight='bold', pad=15)
    axes[0].set_ylabel('Equity ($)', fontsize=12)
    axes[0].legend(loc='best', fontsize=10)
    axes[0].grid(True, alpha=0.3, linestyle='--')
    axes[0].set_xlabel('')
    returns = df_eq['equity'].pct_change() * 100
    colors = ['green' if r >= 0 else 'red' for r in returns]
    axes[1].bar(df_eq['timestamp'], returns, alpha=0.6, color=colors, width=0.8)
    axes[1].set_title('Returns Distribution (%)', fontsize=16, fontweight='bold', pad=15)
    axes[1].set_ylabel('Return (%)', fontsize=12)
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    axes[1].grid(True, alpha=0.3, linestyle='--')
    axes[1].set_xlabel('')
    axes[2].fill_between(df_eq['timestamp'], df_eq['drawdown'] * 100, 0, 
                         alpha=0.5, color='#A23B72', label='Drawdown')
    axes[2].set_title('Underwater Plot (Drawdown %)', fontsize=16, fontweight='bold', pad=15)
    axes[2].set_ylabel('Drawdown (%)', fontsize=12)
    axes[2].set_xlabel('Date', fontsize=12)
    axes[2].grid(True, alpha=0.3, linestyle='--')
    axes[2].legend(loc='best', fontsize=10)
    plt.tight_layout()
    metrics_text = (
        f"PERFORMANCE METRICS\n"
        f"{'='*35}\n"
        f"Total Trades:       {report['total_trades']}\n"
        f"Winning Trades:     {report['winning_trades']}\n"
        f"Losing Trades:      {report['losing_trades']}\n"
        f"Win Rate:           {report['win_rate']:.2f}%\n"
        f"\n"
        f"Initial Capital:    ${report['initial_capital']:,.2f}\n"
        f"Final Capital:      ${report['final_capital']:,.2f}\n"
        f"Net Profit:         ${report['net_profit']:+,.2f}\n"
        f"Total Return:       {report['total_return']:+.2f}%\n"
        f"\n"
        f"Max Drawdown:       {report['max_drawdown']:.2f}%\n"
        f"Sharpe Ratio:       {report['sharpe_ratio']:.3f}\n"
        f"Profit Factor:      {report['profit_factor']:.2f}\n"
        f"\n"
        f"Avg Win:            ${report['avg_win']:+,.2f}\n"
        f"Avg Loss:           ${report['avg_loss']:+,.2f}\n"
        f"Largest Win:        ${report['largest_win']:+,.2f}\n"
        f"Largest Loss:       ${report['largest_loss']:+,.2f}\n"
    )
    plt.figtext(0.99, 0.5, metrics_text, fontsize=9,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, pad=1),
                verticalalignment='center', horizontalalignment='left',
                family='monospace')
    output_file = 'backtest_results_REAL_STRATEGY.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    logger.info(f"📊 Chart saved to: {output_file}")
    plt.show()

def print_report(report):
    print("\n" + "="*70)
    print("BACKTEST RESULTS - REAL L&A BOT STRATEGY")
    print("="*70)
    print(f"Total Trades:           {report['total_trades']}")
    print(f"Winning Trades:         {report['winning_trades']}")
    print(f"Losing Trades:          {report['losing_trades']}")
    print(f"Win Rate:               {report['win_rate']:.2f}%")
    print("-"*70)
    print(f"Initial Capital:        ${report['initial_capital']:,.2f}")
    print(f"Final Capital:          ${report['final_capital']:,.2f}")
    print(f"Net Profit:             ${report['net_profit']:+,.2f}")
    print(f"Total Return:           {report['total_return']:+.2f}%")
    print("-"*70)
    print(f"Max Drawdown:           {report['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio:           {report['sharpe_ratio']:.3f}")
    print(f"Profit Factor:          {report['profit_factor']:.2f}")
    print("-"*70)
    print(f"Average Win:            ${report['avg_win']:+,.2f}")
    print(f"Average Loss:           ${report['avg_loss']:+,.2f}")
    print(f"Largest Win:            ${report['largest_win']:+,.2f}")
    print(f"Largest Loss:           ${report['largest_loss']:+,.2f}")
    print("="*70)

def save_report_to_json(report, filename='backtest_trades.json'):
    output = {
        'summary': {
            'total_trades': report['total_trades'],
            'winning_trades': report['winning_trades'],
            'losing_trades': report['losing_trades'],
            'win_rate': report['win_rate'],
            'total_return': report['total_return'],
            'initial_capital': report['initial_capital'],
            'final_capital': report['final_capital'],
            'net_profit': report['net_profit'],
            'max_drawdown': report['max_drawdown'],
            'sharpe_ratio': report['sharpe_ratio'],
            'profit_factor': report['profit_factor'],
            'avg_win': report['avg_win'],
            'avg_loss': report['avg_loss'],
            'largest_win': report['largest_win'],
            'largest_loss': report['largest_loss']
        },
        'trades': report['trades_df'].to_dict('records') if 'trades_df' in report else []
    }
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    logger.info(f"💾 Report saved to: {filename}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 L&A BOT - COMPREHENSIVE BACKTESTING SYSTEM v2.0")
    print("="*70)
    print("Simulating REAL strategy with actual Kraken data")
    print("="*70 + "\n")
    SYMBOL = 'BTC/USD'
    TIMEFRAME = '1h'
    LIMIT = 2000  # Number of candles (~ 83 days for 1h)
    INITIAL_CAPITAL = 10000
    RISK_PER_TRADE = 0.03
    FAST_MODE = True  # Set to False to use Gemini API
    try:
        print("📊 Step 1: Fetching historical data...")
        df = fetch_historical_data(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
        print(f"✅ Loaded {len(df)} candles")
        print(f"   Period: {df.index[0]} to {df.index[-1]}")
        print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}\n")
        print("🔄 Step 2: Running backtest simulation...")
        print(f"   Initial Capital: ${INITIAL_CAPITAL:,.2f}")
        print(f"   Risk per Trade: {RISK_PER_TRADE*100}%")
        print(f"   Fast Mode: {FAST_MODE} (Gemini API: {'Disabled' if FAST_MODE else 'Enabled'})")
        print()
        backtest = BacktestEngine(
            initial_capital=INITIAL_CAPITAL,
            risk_per_trade=RISK_PER_TRADE,
            fast_mode=FAST_MODE
        )
        backtest.simulate_strategy(df, symbol=SYMBOL)
        print("\n📈 Step 3: Generating performance report...")
        report = backtest.genera_report()
        print_report(report)
        print("\n📊 Step 4: Creating visualizations...")
        plot_backtest_results(report)
        print("\n💾 Step 5: Saving results to JSON...")
        save_report_to_json(report)
        print("\n" + "="*70)
        print("✅ BACKTEST COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"📊 Chart saved to: backtest_results_REAL_STRATEGY.png")
        print(f"💾 Data saved to: backtest_trades.json")
        print("="*70 + "\n")
    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}")
        logger.exception("Traceback backtest_strategy_la:")
        traceback.print_exc()
        print("\n❌ Backtest failed. Check logs for details.\n")