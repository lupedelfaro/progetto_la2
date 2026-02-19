# -*- coding: utf-8 -*-
import json

def calcola_bilancio_reale():
    totale_netto = 0
    wins = 0
    losses = 0
    stats_monete = {}
    
    print("\n💰 BILANCIO DETTAGLIATO KRAKEN (Netto Commissioni)")
    print("==================================================")
    
    try:
        with open("report_reale.json", "r") as f:
            for line in f:
                data = json.loads(line)
                asset = data.get("asset", "N/D")
                pnl = data.get("pnl_netto", data.get("pnl_dollari", 0))
                totale_netto += pnl
                
                if asset not in stats_monete:
                    stats_monete[asset] = {"pnl": 0, "trades": 0}
                stats_monete[asset]["pnl"] += pnl
                stats_monete[asset]["trades"] += 1
                if pnl > 0: wins += 1
                else: losses += 1
        
        print(f"{'ASSET':<10} | {'TRADES':<8} | {'PNL NETTO'}")
        print("-" * 40)
        for moneta, info in stats_monete.items():
            colore = "+" if info['pnl'] >= 0 else ""
            print(f"{moneta:<10} | {info['trades']:<8} | {colore}${info['pnl']:.2f}")
        
        totali = wins + losses
        win_rate = (wins / totali * 100) if totali > 0 else 0
        print("=" * 40)
        print(f"Trade Chiusi: {totali} ({wins}✅ / {losses}❌)")
        print(f"Win Rate:     {win_rate:.2f}%")
        print(f"BILANCIO NETTO FINALE: ${totale_netto:.2f}")
        print("==================================================")
    except FileNotFoundError:
        print("❌ File 'report_reale.json' non trovato. Il bot non ha ancora chiuso trade.")
    except Exception as e:
        print(f"⚠️ Errore: {e}")

if __name__ == "__main__":
    calcola_bilancio_reale()
