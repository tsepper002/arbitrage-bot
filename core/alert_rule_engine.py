"""
Alert Rule Engine - Configurable alert rules
Triggers alerts based on custom conditions
"""
import logging
from typing import Dict, List, Callable
import time

logger = logging.getLogger(__name__)

class AlertRuleEngine:
    """Manages alert rules and triggers"""
    
    def __init__(self):
        self.rules = {}
        self.triggered_alerts = []
        logger.info("✅ AlertRuleEngine initialized")
    
    def add_rule(self, rule_id: str, condition: Callable, alert_message: str, severity: str = 'INFO'):
        """Add alert rule"""
        try:
            self.rules[rule_id] = {
                'condition': condition,
                'message': alert_message,
                'severity': severity,
                'enabled': True,
                'last_triggered': 0
            }
            logger.info(f"Added alert rule: {rule_id}")
            
        except Exception as e:
            logger.error(f"Error adding rule: {e}")
    
    def check_rules(self, context: Dict) -> List[Dict]:
        """Check all rules and trigger alerts"""
        try:
            alerts = []
            
            for rule_id, rule in self.rules.items():
                if not rule['enabled']:
                    continue
                
                try:
                    # Check condition
                    if rule['condition'](context):
                        # Check cooldown (don't spam same alert)
                        if time.time() - rule['last_triggered'] < 60:  # 1 minute cooldown
                            continue
                        
                        alert = {
                            'rule_id': rule_id,
                            'message': rule['message'],
                            'severity': rule['severity'],
                            'timestamp': time.time()
                        }
                        
                        alerts.append(alert)
                        self.triggered_alerts.append(alert)
                        rule['last_triggered'] = time.time()
                        
                        logger.warning(f"Alert triggered: {rule_id} - {rule['message']}")
                        
                except Exception as e:
                    logger.error(f"Error checking rule {rule_id}: {e}")
            
            # Keep recent alerts only
            if len(self.triggered_alerts) > 1000:
                self.triggered_alerts = self.triggered_alerts[-500:]
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking rules: {e}")
            return []
    
    def enable_rule(self, rule_id: str):
        """Enable rule"""
        if rule_id in self.rules:
            self.rules[rule_id]['enabled'] = True
            logger.info(f"Enabled rule: {rule_id}")
    
    def disable_rule(self, rule_id: str):
        """Disable rule"""
        if rule_id in self.rules:
            self.rules[rule_id]['enabled'] = False
            logger.info(f"Disabled rule: {rule_id}")
    
    def get_recent_alerts(self, limit: int = 100) -> List[Dict]:
        """Get recent triggered alerts"""
        return self.triggered_alerts[-limit:]

def get_alert_rule_engine():
    """Factory function"""
    return AlertRuleEngine()
