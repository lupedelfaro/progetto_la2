import re
import json
from collections import defaultdict
from datetime import datetime

def parse_log(filename):
    """Legge e analizza sniper_history.log"""
    trades = []
    closed_trades = defaultdict(list)
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Estrai POSIZIONE CHIUSA
                if "POSIZIONE CHIUSA" in line or "PnL:" in line:
                    match = re.search(r'(\w+)\s*\|\s*PnL:\s*([-\d.]+)%\s*\(\$?([-\d.]+)\)', line)
                    if match:
                        asset, pnl_perc, pnl_usd = match.groups()
                        trades.append({
                            'asset': asset,
                            'pnl_perc': float(pnl_perc),
                            'pnl_usd': float(pnl_usd),
                            'timestamp': line.split('|')[0].strip()
                        })
                
                # Estrai VOTO
                if "Voto" in line:
                    match = re.search(r'(\w+):\s*Voto\s*([\d.]+)/10', line)
                    if match:
                        asset, voto = match.groups()
    except Exception as e:
        print(f"Errore lettura log: {e}")
    
    return trades

def analyze_performance(trades):
    """Analizza la performance del bot"""
    
    if not trades:
        print("❌ Nessun trade trovato nel log!")
        return
    
    print("\n" + "="*60)
    print("📊 ANALISI PERFORMANCE BOT")
    print("="*60)
    
    # WIN RATE
    wins = len([t for t in trades if t['pnl_perc'] > 0])
    losses = len([t for t in trades if t['pnl_perc'] < 0])
    total = len(trades)
    win_rate = (wins / total * 100) if total > 0 else 0
    
    print(f"\n🏆 WIN RATE")
    print(f"   Vinti: {wins}/{total} ({win_rate:.1f}%)")
    print(f"   Persi: {losses}/{total}")
    
    # PnL TOTALE
    total_pnl = sum(t['pnl_usd'] for t in trades)
    print(f"\n💰 PnL TOTALE: ${total_pnl:.2f}")
    
    # ASSET PERFORMANCE
    asset_stats = defaultdict(lambda: {'pnl': 0, 'count': 0})
    for trade in trades:
        asset_stats[trade['asset']]['pnl'] += trade['pnl_usd']
        asset_stats[trade['asset']]['count'] += 1
    
    print(f"\n📈 MIGLIORI ASSET:")
    for asset, stats in sorted(asset_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)[:3]:
        print(f"   {asset}: ${stats['pnl']:.2f} ({stats['count']} trade)")
    
    print(f"\n📉 PEGGIORI ASSET:")
    for asset, stats in sorted(asset_stats.items(), key=lambda x: x[1]['pnl'])[:3]:
        print(f"   {asset}: ${stats['pnl']:.2f} ({stats['count']} trade)")
    
    # SUGGERIMENTI
    print(f"\n💡 SUGGERIMENTI DI MIGLIORAMENTO:")
    if win_rate < 50:
        print("   ⚠️  Win rate basso (<50%) - Migliora la strategia di entry")
    if total_pnl < 0:
        print("   ⚠️  PnL negativo - Riduci il rischio per trade")
    if wins == 0:
        print("   🔴 NESSUN TRADE VINTO - Cambia completamente la strategia!")
    else:
        print("   ✅ Continua a tradare gli asset con PnL positivo")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    trades = parse_log('sniper_history.log')
    analyze_performance(trades)
