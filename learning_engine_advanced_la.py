# -*- coding: utf-8 -*-
# learning_engine_advanced_la.py - MOTORE DI APPRENDIMENTO AVANZATO
# Analizza i trade chiusi, estrae insights, suggerisce miglioramenti

import json
import logging
import numpy as np
from datetime import datetime
from collections import defaultdict

class LearningEngineAdvanced:
    """
    Motore di apprendimento avanzato che:
    - Analizza tutti i trade chiusi
    - Estrae patterns e insights
    - Calcola metriche di performance
    - Suggerisce ottimizzazioni strategiche
    - Identifica i migliori asset e orari
    """
    
    def __init__(self, position_tracker):
        """
        Args:
            position_tracker (PositionTracker): Tracker con storico trade
        """
        self.position_tracker = position_tracker
        self.logger = logging.getLogger("LearningEngineAdvanced")
        self.insights = []
    
    # ========================================================================
    # ANALISI TRADE STORICI
    # ========================================================================
    
    def analizza_tutti_trade(self):
        """Analizza TUTTI i trade chiusi e estrae insights"""
        
        storico = self.position_tracker.storico_trades
        
        if not storico:
            self.logger.warning("⚠️ Nessun trade nello storico per analizzare")
            return None
        
        self.logger.info(f"🔍 Analizzando {len(storico)} trade...")
        
        insights = {
            'timestamp': datetime.now().isoformat(),
            'total_trades': len(storico),
            'analisi_asset': self._analizza_performance_asset(storico),
            'analisi_direzioni': self._analizza_performance_direzioni(storico),
            'analisi_orari': self._analizza_orari_migliori(storico),
            'patterns_vincenti': self._identifica_patterns_vincenti(storico),
            'patterns_perdenti': self._identifica_patterns_perdenti(storico),
            'raccomandazioni': self._genera_raccomandazioni(storico)
        }
        
        self.insights.append(insights)
        return insights
    
    # ========================================================================
    # ANALISI PERFORMANCE PER ASSET
    # ========================================================================
    
    def _analizza_performance_asset(self, storico):
        """Analizza quale asset è più profittevole"""
        
        performance = defaultdict(lambda: {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'win_rate': 0.0,
            'miglior_trade': 0.0,
            'peggior_trade': 0.0
        })
        
        for trade in storico:
            asset = trade.get('asset', 'UNKNOWN')
            pnl = trade.get('pnl_usd', 0)
            pnl_perc = trade.get('pnl_perc', 0)
            
            perf = performance[asset]
            perf['total_trades'] += 1
            perf['total_pnl'] += pnl
            
            if pnl > 0:
                perf['wins'] += 1
            else:
                perf['losses'] += 1
            
            perf['miglior_trade'] = max(perf['miglior_trade'], pnl_perc)
            perf['peggior_trade'] = min(perf['peggior_trade'], pnl_perc)
        
        # Calcola medie
        for asset, perf in performance.items():
            total = perf['total_trades']
            perf['avg_pnl'] = perf['total_pnl'] / total if total > 0 else 0
            perf['win_rate'] = (perf['wins'] / total * 100) if total > 0 else 0
        
        return dict(performance)
    
    # ========================================================================
    # ANALISI PERFORMANCE PER DIREZIONE
    # ========================================================================
    
    def _analizza_performance_direzioni(self, storico):
        """Analizza quale direzione (LONG/SHORT) performa meglio"""
        
        direzioni = {
            'LONG': {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'win_rate': 0.0
            },
            'SHORT': {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'win_rate': 0.0
            }
        }
        
        for trade in storico:
            direzione = trade.get('direzione', 'LONG')
            pnl = trade.get('pnl_usd', 0)
            
            perf = direzioni[direzione]
            perf['total_trades'] += 1
            perf['total_pnl'] += pnl
            
            if pnl > 0:
                perf['wins'] += 1
            else:
                perf['losses'] += 1
        
        # Calcola medie
        for dir_name, perf in direzioni.items():
            total = perf['total_trades']
            perf['avg_pnl'] = perf['total_pnl'] / total if total > 0 else 0
            perf['win_rate'] = (perf['wins'] / total * 100) if total > 0 else 0
        
        return direzioni
    
    # ========================================================================
    # ANALISI ORARI MIGLIORI
    # ========================================================================
    
    def _analizza_orari_migliori(self, storico):
        """Identifica gli orari in cui si vince più spesso"""
        
        orari = defaultdict(lambda: {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0
        })
        
        for trade in storico:
            # Estrae l'ora dalla data_apertura (formato ISO: YYYY-MM-DDTHH:MM:SS)
            data_apertura = trade.get('data_apertura', '')
            if not data_apertura:
                continue
            
            try:
                ora = int(data_apertura.split('T')[1].split(':')[0])
                pnl = trade.get('pnl_usd', 0)
                
                perf = orari[ora]
                perf['total_trades'] += 1
                perf['total_pnl'] += pnl
                
                if pnl > 0:
                    perf['wins'] += 1
                else:
                    perf['losses'] += 1
            
            except (IndexError, ValueError):
                continue
        
        # Calcola win rate
        for ora, perf in orari.items():
            total = perf['total_trades']
            perf['win_rate'] = (perf['wins'] / total * 100) if total > 0 else 0
        
        # Ordina per win rate decrescente
        orari_ordinati = dict(sorted(
            orari.items(),
            key=lambda x: x[1]['win_rate'],
            reverse=True
        ))
        
        return orari_ordinati
    
    # ========================================================================
    # IDENTIFICAZIONE PATTERNS VINCENTI
    # ========================================================================
    
    def _identifica_patterns_vincenti(self, storico):
        """Identifica le caratteristiche comuni dei trade vincenti"""
        
        trade_vincenti = [t for t in storico if t.get('pnl_usd', 0) > 0]
        
        if not trade_vincenti:
            return {'message': 'Nessun trade vincente'}
        
        patterns = {
            'voto_medio_ia': np.mean([t.get('voto', 0) for t in trade_vincenti]),
            'direzione_preferita': max(
                set([t.get('direzione', 'LONG') for t in trade_vincenti]),
                key=[t.get('direzione', 'LONG') for t in trade_vincenti].count
            ),
            'pnl_medio': np.mean([t.get('pnl_usd', 0) for t in trade_vincenti]),
            'pnl_massimo': max([t.get('pnl_usd', 0) for t in trade_vincenti]),
            'modalita_preferita': max(
                set([t.get('modalita', 'SPOT') for t in trade_vincenti]),
                key=[t.get('modalita', 'SPOT') for t in trade_vincenti].count
            ),
            'motivo_chiusura': self._conta_motivi_chiusura(trade_vincenti),
            'asset_migliori': [t.get('asset') for t in sorted(
                trade_vincenti,
                key=lambda x: x.get('pnl_usd', 0),
                reverse=True
            )[:5]]  # Top 5 asset per PnL
        }
        
        return patterns
    
    # ========================================================================
    # IDENTIFICAZIONE PATTERNS PERDENTI
    # ========================================================================
    
    def _identifica_patterns_perdenti(self, storico):
        """Identifica le caratteristiche comuni dei trade perdenti"""
        
        trade_perdenti = [t for t in storico if t.get('pnl_usd', 0) <= 0]
        
        if not trade_perdenti:
            return {'message': 'Nessun trade in perdita'}
        
        patterns = {
            'voto_medio_ia': np.mean([t.get('voto', 0) for t in trade_perdenti]),
            'direzione_problematica': max(
                set([t.get('direzione', 'LONG') for t in trade_perdenti]),
                key=[t.get('direzione', 'LONG') for t in trade_perdenti].count
            ),
            'pnl_medio': np.mean([t.get('pnl_usd', 0) for t in trade_perdenti]),
            'pnl_minimo': min([t.get('pnl_usd', 0) for t in trade_perdenti]),
            'motivo_chiusura': self._conta_motivi_chiusura(trade_perdenti),
            'asset_problematici': [t.get('asset') for t in sorted(
                trade_perdenti,
                key=lambda x: x.get('pnl_usd', 0)
            )[:5]]  # Bottom 5 asset per PnL
        }
        
        return patterns
    
    # ========================================================================
    # GENERAZIONE RACCOMANDAZIONI
    # ========================================================================
    
    def _genera_raccomandazioni(self, storico):
        """Genera raccomandazioni strategiche basate sui dati"""
        
        raccomandazioni = []
        stats = self.position_tracker.calcola_statistiche()
        
        # Raccomandazione 1: Win Rate
        win_rate = stats.get('win_rate', 0)
        if win_rate < 45:
            raccomandazioni.append({
                'priorita': 'ALTA',
                'categoria': 'Win Rate Basso',
                'descrizione': f'Win rate al {win_rate:.1f}% - Riconsiderare il voto minimo di entry',
                'azione': 'Aumentare SOGLIA_VOTO_ENTRY a 7.0 o superiore'
            })
        elif win_rate > 65:
            raccomandazioni.append({
                'priorita': 'BASSA',
                'categoria': 'Win Rate Elevato',
                'descrizione': f'Win rate al {win_rate:.1f}% - Sistema performante!',
                'azione': 'Mantenere la configurazione attuale'
            })
        
        # Raccomandazione 2: Profit Factor
        profit_factor = stats.get('profit_factor', 0)
        if profit_factor < 1.0:
            raccomandazioni.append({
                'priorita': 'ALTA',
                'categoria': 'Profit Factor Negativo',
                'descrizione': f'PF {profit_factor:.2f} - Perdi più di quanto guadagni',
                'azione': 'Ridurre il numero di trade speculativi, aumentare soglia entry'
            })
        elif profit_factor > 2.0:
            raccomandazioni.append({
                'priorita': 'BASSA',
                'categoria': 'Profit Factor Ottimale',
                'descrizione': f'PF {profit_factor:.2f} - Eccellente gestione del rischio',
                'azione': 'Sistema ben calibrato'
            })
        
        # Raccomandazione 3: Drawdown
        max_dd = stats.get('max_drawdown', 0)
        if max_dd > 20:
            raccomandazioni.append({
                'priorita': 'MEDIA',
                'categoria': 'Drawdown Elevato',
                'descrizione': f'Drawdown massimo {max_dd:.2f}% - Rischio elevato',
                'azione': 'Ridurre la size per trade e implementare position sizing dinamico'
            })
        
        # Raccomandazione 4: Asset Performance
        asset_stats = self._analizza_performance_asset(storico)
        asset_peggiori = sorted(
            asset_stats.items(),
            key=lambda x: x[1]['win_rate']
        )[:3]
        
        for asset, perf in asset_peggiori:
            if perf['total_trades'] >= 5 and perf['win_rate'] < 30:
                raccomandazioni.append({
                    'priorita': 'MEDIA',
                    'categoria': 'Asset Sottoperformante',
                    'descrizione': f'{asset} ha {perf["win_rate"]:.1f}% win rate su {perf["total_trades"]} trade',
                    'azione': f'Considerare di escludere {asset} dalla whitelist'
                })
        
        return raccomandazioni
    
    # ========================================================================
    # UTILITY HELPERS
    # ========================================================================
    
    @staticmethod
    def _conta_motivi_chiusura(trade_list):
        """Conta i motivi di chiusura nei trade"""
        motivi = defaultdict(int)
        for trade in trade_list:
            motivo = trade.get('motivo_chiusura', 'UNKNOWN')
            motivi[motivo] += 1
        return dict(motivi)
    
    # ========================================================================
    # ESPORTAZIONE INSIGHTS
    # ========================================================================
    
    def salva_insights(self, filename="insights_apprendimento.json"):
        """Salva gli insights in un file JSON"""
        try:
            with open(filename, "w") as f:
                json.dump(self.insights, f, indent=4, default=str)
            self.logger.info(f"✅ Insights salvati in {filename}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Errore salvataggio insights: {e}")
            return False
    
    def get_ultimo_insight(self):
        """Ritorna l'ultimo insight generato"""
        return self.insights[-1] if self.insights else None
    
    # ========================================================================
    # GENERAZIONE REPORT TESTUALE
    # ========================================================================
    
    def genera_report_testuale(self):
        """Genera un report testuale leggibile degli insights"""
        
        ultimo = self.get_ultimo_insight()
        if not ultimo:
            return "Nessun insight disponibile"
        
        report = []
        report.append("=" * 80)
        report.append("📊 LEARNING ENGINE - REPORT ANALISI")
        report.append("=" * 80)
        report.append(f"Data: {ultimo['timestamp']}")
        report.append(f"Trade Analizzati: {ultimo['total_trades']}")
        report.append("")
        
        # Performance per Asset
        report.append("📈 PERFORMANCE PER ASSET:")
        report.append("-" * 80)
        asset_perf = ultimo['analisi_asset']
        for asset, perf in sorted(asset_perf.items(), key=lambda x: x[1]['win_rate'], reverse=True):
            report.append(
                f"  {asset:<10} | Trade: {perf['total_trades']:<3} | "
                f"Win Rate: {perf['win_rate']:.1f}% | "
                f"Avg PnL: ${perf['avg_pnl']:+.2f}"
            )
        report.append("")
        
        # Performance per Direzione
        report.append("🔀 PERFORMANCE PER DIREZIONE:")
        report.append("-" * 80)
        dir_perf = ultimo['analisi_direzioni']
        for dir_name, perf in dir_perf.items():
            report.append(
                f"  {dir_name:<6} | Trade: {perf['total_trades']:<3} | "
                f"Win Rate: {perf['win_rate']:.1f}% | "
                f"Total PnL: ${perf['total_pnl']:+.2f}"
            )
        report.append("")
        
        # Orari Migliori
        report.append("🕐 ORARI MIGLIORI:")
        report.append("-" * 80)
        orari = ultimo['analisi_orari']
        for ora, perf in list(orari.items())[:5]:
            report.append(
                f"  Ora {ora:02d}:00 | Trade: {perf['total_trades']:<3} | "
                f"Win Rate: {perf['win_rate']:.1f}%"
            )
        report.append("")
        
        # Raccomandazioni
        report.append("💡 RACCOMANDAZIONI:")
        report.append("-" * 80)
        raccomandazioni = ultimo['raccomandazioni']
        for i, rac in enumerate(raccomandazioni, 1):
            report.append(f"  {i}. [{rac['priorita']}] {rac['categoria']}")
            report.append(f"     → {rac['descrizione']}")
            report.append(f"     → Azione: {rac['azione']}")
            report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
        
    def allena_modello(self):
        """
        Metodo aggiunto per risolvere l'errore AttributeError.
        Dirotta la chiamata sulla funzione di analisi esistente.
        """
        self.logger.info("🧠 Comando 'allena_modello' ricevuto. Avvio analisi...")
        return self.analizza_tutti_trade()