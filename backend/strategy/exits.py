"""Exit engine module - TP/SL and dynamic TP"""

from typing import Optional, Dict, List
from collections import deque


class ExitEngine:
    """Manages take profit, stop loss, and dynamic TP"""
    
    def __init__(self, config: dict, htf_indicator=None):
        self.config = config
        
        # Static exits
        self.sl_percent = abs(config.get('stop_loss', {}).get('value', -2.0))
        self.tp_percent = config.get('take_profit', {}).get('value', 5.0)
        
        # Trailing stop (not implemented yet)
        self.trailing_enabled = config.get('trailing_stop', {}).get('enabled', False)
        
        # Dynamic TP
        self.dynamic_tp_enabled = config.get('dynamic_tp', {}).get('enabled', False)
        self.dynamic_tp_rules = config.get('dynamic_tp', {}).get('rules', [])
        self.default_tp_percent = config.get('dynamic_tp', {}).get('default_tp_percent', 5.0)
        
        # HTF indicator for dynamic TP
        self.htf_indicator = htf_indicator
        
        # Track open positions for TP/SL updates
        self.positions: Dict[str, dict] = {}
    
    def initialize_position(self, position_id: str, entry_price: float, direction: int) -> dict:
        """
        Initialize TP/SL for a new position
        
        Args:
            position_id: Unique position identifier
            entry_price: Entry price
            direction: 1 for long, -1 for short
        
        Returns:
            dict with tp_price and sl_price
        """
        tp_percent = self.default_tp_percent if self.dynamic_tp_enabled else self.tp_percent
        
        if direction > 0:  # Long
            tp_price = entry_price * (1 + tp_percent / 100)
            sl_price = entry_price * (1 - self.sl_percent / 100)
        else:  # Short
            tp_price = entry_price * (1 - tp_percent / 100)
            sl_price = entry_price * (1 + self.sl_percent / 100)
        
        self.positions[position_id] = {
            'entry_price': entry_price,
            'direction': direction,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'tp_percent': tp_percent
        }
        
        return {
            'tp_price': tp_price,
            'sl_price': sl_price,
            'tp_percent': tp_percent
        }
    
    def update_dynamic_tp(self, position_id: str, current_price: float) -> Optional[float]:
        """
        Update TP based on HTF indicator (e.g., RSI)
        
        Args:
            position_id: Position to update
            current_price: Current market price
        
        Returns:
            New TP price if updated, None otherwise
        """
        if not self.dynamic_tp_enabled or position_id not in self.positions:
            return None
        
        pos = self.positions[position_id]
        
        # Get HTF RSI value
        htf_value = None
        if self.htf_indicator:
            htf_value = self.htf_indicator.value()
        
        if htf_value is None:
            return None
        
        # Apply dynamic TP rules
        new_tp_percent = self.default_tp_percent
        for rule in self.dynamic_tp_rules:
            condition = rule.get('condition', {})
            operator = condition.get('operator', '>')
            value = condition.get('value', 50)
            
            if operator == '>' and htf_value > value:
                new_tp_percent = rule.get('tp_percent', self.default_tp_percent)
                break
            elif operator == '<' and htf_value < value:
                new_tp_percent = rule.get('tp_percent', self.default_tp_percent)
                break
        
        # Update TP if changed
        if new_tp_percent != pos['tp_percent']:
            pos['tp_percent'] = new_tp_percent
            direction = pos['direction']
            
            if direction > 0:  # Long
                new_tp = pos['entry_price'] * (1 + new_tp_percent / 100)
            else:  # Short
                new_tp = pos['entry_price'] * (1 - new_tp_percent / 100)
            
            pos['tp_price'] = new_tp
            return new_tp
        
        return None
    
    def check_exit(self, position_id: str, current_price: float) -> Optional[str]:
        """
        Check if position should be exited
        
        Args:
            position_id: Position to check
            current_price: Current market price
        
        Returns:
            'tp', 'sl', or None
        """
        if position_id not in self.positions:
            return None
        
        pos = self.positions[position_id]
        direction = pos['direction']
        
        # Check TP
        if direction > 0 and current_price >= pos['tp_price']:
            return 'tp'
        elif direction < 0 and current_price <= pos['tp_price']:
            return 'tp'
        
        # Check SL
        if direction > 0 and current_price <= pos['sl_price']:
            return 'sl'
        elif direction < 0 and current_price >= pos['sl_price']:
            return 'sl'
        
        return None
    
    def close_position(self, position_id: str) -> None:
        """Remove position from tracking"""
        if position_id in self.positions:
            del self.positions[position_id]
    
    def get_position_info(self, position_id: str) -> Optional[dict]:
        """Get position TP/SL info"""
        return self.positions.get(position_id)
