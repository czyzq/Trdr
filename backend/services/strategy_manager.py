"""Strategy management service - extracted from main.py"""
import os
import math

# Global strategy manager - loaded once
_strategy_manager = None


def get_symbol_strategy(symbol: str) -> str:
    """Get strategy for symbol - delegates to state"""
    from services.state import get_symbol_strategy as _get
    result = _get(symbol)
    # Also check DB for per-symbol strategy
    strategy_key = f"STRATEGY_{symbol}"
    db_strategy = db.get_setting(strategy_key)
    if db_strategy:
        return db_strategy
    return result


def set_symbol_strategy(symbol: str, strategy_id: str):
    """Set strategy for symbol - delegates to state"""
    from services.state import set_symbol_strategy as _set
    _set(symbol, strategy_id)
    # Also save to DB
    strategy_key = f"STRATEGY_{symbol}"
    db.set_setting(strategy_key, strategy_id, "user")


def get_strategy_manager(force_reload: bool = False):
    """Get or create the JSON-based strategy manager."""
    global _strategy_manager
    
    if _strategy_manager is None or force_reload:
        try:
            from strategy import load_strategies_from_file
            
            # Load from local strategies.json in project root
            json_path = os.path.join(os.path.dirname(__file__), "..", "strategies.json")
            if os.path.exists(json_path):
                _strategy_manager = load_strategies_from_file(json_path)
                print(f"[STRATEGY] Loaded {len(_strategy_manager.strategies)} strategies from JSON")
            else:
                print(f"[STRATEGY] JSON config not found at {json_path}")
                _strategy_manager = None
        except Exception as e:
            print(f"[STRATEGY] Failed to load JSON strategies: {e}")
            _strategy_manager = None
    
    return _strategy_manager


def analyze_with_new_strategy(symbol: str, candles: list, current_price: float,
                            requested_strategy: str = None, atr_percent: float = None, 
                            vix_value: float = None) -> dict:
    """
    Analyze using new JSON-based strategy module.
    Returns dict with direction, score, confidence, etc. or None if not available.
    
    Args:
        symbol: Trading symbol
        candles: Price candles
        current_price: Current price
        requested_strategy: Specific JSON strategy ID to use (e.g., "JSON:btc_v2_core")
        atr_percent: ATR percent for volatility filter
        vix_value: Current VIX value for VIX filter
    """
    manager = get_strategy_manager()
    if not manager:
        return None
    
    # Find strategy - use requested one or find any for symbol
    strategy = None
    
    if requested_strategy:
        # User specifically requested this JSON strategy
        json_id = requested_strategy.replace("JSON:", "")
        if json_id in manager.strategies:
            strategy = manager.strategies[json_id]
            # Only print on first call (check if already printed this session)
            if not getattr(analyze_with_new_strategy, '_logged', False):
                print(f"[STRATEGY] Using requested JSON strategy: {json_id}")
                analyze_with_new_strategy._logged = True
    else:
        # Default: use enabled strategy for this symbol
        for s in manager.get_enabled_strategies():
            if s.symbol.upper() == symbol.upper():
                strategy = s
                break
        
        # If no enabled, try any for this symbol
        if not strategy:
            for s in manager.strategies.values():
                if s.symbol.upper() == symbol.upper():
                    strategy = s
                    break
    
    if not strategy:
        return None
    
    # Update indicators with latest candles
    for candle in candles[-50:]:  # Last 50 candles for warmup
        candle_data = {
            'open': candle.get('open'),
            'high': candle.get('high'),
            'low': candle.get('low'),
            'close': candle.get('close'),
            'volume': candle.get('volume', 0),
            'timestamp': candle.get('timestamp')
        }
        for ind in strategy.indicators.values():
            ind.update(candle_data)
    
    # Get current candle
    if not candles:
        return None
    
    current_candle = candles[-1]
    candle_data = {
        'open': current_candle.get('open'),
        'high': current_candle.get('high'),
        'low': current_candle.get('low'),
        'close': current_candle.get('close'),
        'volume': current_candle.get('volume', 0),
        'timestamp': current_candle.get('timestamp')
    }
    
    # Check if we have enough indicator data
    has_data = all(ind.value() is not None for ind in strategy.indicators.values())
    if not has_data:
        print(f"[DEBUG] {symbol}: Not enough indicator data for {strategy.name}")
        return None
    
    # Check filters (includes volatility and VIX from strategy config)
    filters_passed, failed_filters = strategy.filters.check_all(
        candle_data, symbol, 'long', 
        atr_percent=atr_percent, 
        vix_value=vix_value
    )
    if not filters_passed:
        print(f"[FILTERS] {symbol}: Failed filters: {failed_filters}")
        return None
    
    # Get signal
    signal = strategy.score_engine.get_signal()
    score = strategy.score_engine.compute_score()
    
    if not signal:
        return None
    
    direction = 1 if signal == 'buy' else -1
    
    # Calculate exits
    exits = strategy.exit_engine.initialize_position(
        position_id=f"live_{symbol}",
        entry_price=current_price,
        direction=direction
    )
    
    # Normalize score to [-1, 1] using sigmoid-like scaling
    # This handles any range of raw scores properly
    def normalize_score(s: float) -> float:
        """Normalize score using tanh for smooth scaling to [-1, 1]"""
        # Use larger scale factor to avoid saturation for scores in hundreds
        scale = 200.0
        return math.tanh(s / scale)
    
    normalized_score = normalize_score(score)
    
    return {
        'direction': 'long' if direction > 0 else 'short',
        'score': normalized_score,  # Properly normalized to [-1, 1]
        'confidence': min(1.0, abs(normalized_score)),
        'technical_score': normalized_score,
        'components': [{
            'type': 'technical',
            'name': f'JSON Strategy ({strategy.id})',
            'value': score,
            'description': f'Score: {score:.3f}, Signal: {signal}',
            'confidence': 0.5
        }],
        'exits': exits,
        'strategy_id': strategy.id,
    }
