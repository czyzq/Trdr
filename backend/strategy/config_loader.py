"""Config loader - Load strategies from JSON"""

import json
import os
from typing import List, Dict, Optional
from pathlib import Path

from .indicators import create_indicator
from .strategy import Strategy, StrategyManager


class ConfigLoader:
    """Loads and creates strategies from JSON config"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.config: Optional[dict] = None
    
    def load_from_file(self, path: str = None) -> dict:
        """Load config from JSON file"""
        path = path or self.config_path
        if not path:
            raise ValueError("No config path provided")
        
        with open(path, 'r') as f:
            self.config = json.load(f)
        
        return self.config
    
    def load_from_json(self, json_str: str) -> dict:
        """Load config from JSON string"""
        self.config = json.loads(json_str)
        return self.config
    
    def create_strategy_manager(
        self,
        broker_service=None,
        position_service=None,
        settings_service=None,
        market_data_service=None
    ) -> StrategyManager:
        """Create StrategyManager with all strategies"""
        if not self.config:
            raise ValueError("No config loaded")
        
        manager = StrategyManager()
        
        for strategy_config in self.config.get('strategies', []):
            strategy = self._create_strategy(
                strategy_config,
                broker_service,
                position_service,
                settings_service,
                market_data_service
            )
            if strategy:
                manager.add_strategy(strategy)
        
        return manager
    
    def _create_strategy(
        self,
        config: dict,
        broker_service=None,
        position_service=None,
        settings_service=None,
        market_data_service=None
    ) -> Optional[Strategy]:
        """Create single strategy from config"""
        strategy_id = config.get('id')
        if not strategy_id:
            return None
        
        # Create indicators for this strategy
        indicators = {}
        
        score_config = config.get('score', {})
        for ind_config in score_config.get('indicators', []):
            name = ind_config.get('name', '').upper()
            weight = ind_config.get('weight', 0)
            
            if weight == 0:
                continue
            
            # Default parameters per indicator type
            params = self._get_default_indicator_params(name)
            
            try:
                indicators[name] = create_indicator(name, **params)
            except Exception as e:
                print(f"Error creating indicator {name}: {e}")
                continue
        
        # Create strategy
        strategy = Strategy(
            config=config,
            indicators=indicators,
            broker_service=broker_service,
            position_service=position_service,
            settings_service=settings_service,
            market_data_service=market_data_service
        )
        
        return strategy
    
    def _get_default_indicator_params(self, name: str) -> dict:
        """Get default parameters for indicator"""
        defaults = {
            'RSI': {'period': 14, 'source': 'close'},
            'MACD': {'fast': 12, 'slow': 26, 'signal': 9, 'source': 'close'},
            'MOMENTUM': {'lookback': 10, 'source': 'close'},
            'ADX': {'period': 14}
        }
        return defaults.get(name, {})


def load_strategies_from_file(
    path: str,
    broker_service=None,
    position_service=None,
    settings_service=None,
    market_data_service=None
) -> StrategyManager:
    """Convenience function to load strategies from file"""
    loader = ConfigLoader(path)
    loader.load_from_file()
    return loader.create_strategy_manager(
        broker_service=broker_service,
        position_service=position_service,
        settings_service=settings_service,
        market_data_service=market_data_service
    )


def load_strategies_from_json(
    json_str: str,
    broker_service=None,
    position_service=None,
    settings_service=None,
    market_data_service=None
) -> StrategyManager:
    """Convenience function to load strategies from JSON string"""
    loader = ConfigLoader()
    loader.load_from_json(json_str)
    return loader.create_strategy_manager(
        broker_service=broker_service,
        position_service=position_service,
        settings_service=settings_service,
        market_data_service=market_data_service
    )
