# -*- coding: utf-8 -*-
import json

def analizza_performance():
    voti_stats = {}
    SIZE_PER_TRADE = 100  # Ipotizziamo 100$ per ogni operazione su Kraken
    profitto_totale_generale = 0

    print("\n🧐 ANALISI AVANZATA SCATOLA NERA (L&A Sniper)")
    print("==============================================")
    
    try:
        with open("scatola_nera.json", "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    out = data.get("output_brain", {})
                    engine = data.get("input_engine", {})
                    
                    # 1. Pulizia Voto
                    voto = float(out.get("voto", 0))
                    asset = data.get("asset", "N/D")
                    direzione = out.get("direzione", "FLAT")
                    
                    if direzione == "FLAT": continue # Escludiamo i no-trade

                    # 2. Calcolo Profitto Teorico (P&L)
                    # Usiamo i dati reali salvati nel log
                    prezzo_entrata = float(engine.get("prezzo_real", 0))
                    atr = float(engine.get("atr", 0))
                    
                    if prezzo_entrata == 0 or atr == 0: continue
                    
                    # Calcoliamo il TP come fa il tuo bot (Entrata + ATR * 2)
                    distanza_tp = atr * 2.0
                    percentuale_guadagno = (distanza_tp / prezzo_entrata)
                    profitto_dollari = SIZE_PER_TRADE * percentuale_guadagno

                    # 3. Aggregazione Dati
                    if voto not in voti_stats:
                        voti_stats[voto] = {"count": 0, "profitto": 0, "assets": {}}
                    
                    voti_stats[voto]["count"] += 1
                    voti_stats[voto]["profitto"] += profitto_dollari
                    voti_stats[voto]["assets"][asset] = voti_stats[voto]["assets"].get(asset, 0) + 1
                    
                    profitto_totale_generale += profitto_dollari

                except Exception as e:
                    continue
                    
        print(f"{'VOTO':<8} | {'TRADE':<7} | {'PROFITTO STIMATO':<18} | {'ASSET'}")
        print("-" * 70)
        
        # Ordiniamo per voto decrescente
        for v in sorted(voti_stats.keys(), reverse=True):
            stats = voti_stats[v]
            print(f"{v:<8} | {stats['count']:<7} | ${stats['profitto']:>16.2f} | {list(stats['assets'].keys())[:3]}")

        print("-" * 70)
        print(f"💰 PROFITTO TEORICO TOTALE (SULLE VINCITE): ${profitto_totale_generale:.2f}")
        print(f"⚠️ Nota: Il profitto non include le perdite (SL), serve a misurare la potenzialità del voto.")

    except FileNotFoundError:
        print("❌ File scatola_nera.json non trovato.")

if __name__ == "__main__":
    analizza_performance()