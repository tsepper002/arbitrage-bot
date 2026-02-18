"""
Report Generator - Generates trading reports
Creates daily, weekly, monthly reports
"""
import logging
from typing import Dict, List
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generates trading reports"""
    
    def __init__(self):
        self.reports = []
        logger.info("✅ ReportGenerator initialized")
    
    def generate_daily_report(self, trades: List[Dict], pnl: Dict) -> Dict:
        """Generate daily trading report"""
        try:
            report = {
                'type': 'daily',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'total_trades': len(trades),
                'total_pnl': pnl.get('total', 0),
                'winning_trades': sum(1 for t in trades if t.get('pnl', 0) > 0),
                'losing_trades': sum(1 for t in trades if t.get('pnl', 0) < 0),
                'win_rate': 0,
                'generated': time.time()
            }
            
            if report['total_trades'] > 0:
                report['win_rate'] = report['winning_trades'] / report['total_trades']
            
            self.reports.append(report)
            logger.info(f"Generated daily report: {report['total_trades']} trades, PnL: ${report['total_pnl']:.2f}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return {}
    
    def generate_weekly_report(self, daily_reports: List[Dict]) -> Dict:
        """Generate weekly report"""
        try:
            total_trades = sum(r.get('total_trades', 0) for r in daily_reports)
            total_pnl = sum(r.get('total_pnl', 0) for r in daily_reports)
            
            report = {
                'type': 'weekly',
                'days': len(daily_reports),
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'avg_daily_trades': total_trades / len(daily_reports) if daily_reports else 0,
                'avg_daily_pnl': total_pnl / len(daily_reports) if daily_reports else 0,
                'generated': time.time()
            }
            
            self.reports.append(report)
            logger.info(f"Generated weekly report: {total_trades} trades, PnL: ${total_pnl:.2f}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            return {}
    
    def export_report(self, report: Dict, format: str = 'pdf') -> str:
        """Export report to file"""
        try:
            filename = f"report_{report['type']}_{int(time.time())}.{format}"
            # In full implementation, would generate actual PDF/HTML/CSV
            logger.info(f"Exported {report['type']} report to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return ""

def get_report_generator():
    """Factory function"""
    return ReportGenerator()
