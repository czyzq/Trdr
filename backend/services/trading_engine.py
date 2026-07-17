"""Trading engine - extracted from main.py"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import database as db
from timeframes import TimeFrame
from database import async_save_account
# Import Signal and SignalDirection from models
from app.logging import log_event
from models import Signal, SignalDirection
from services.state import broker, data_provider, open_positions, INSTRUMENTS, AUTO_TRADE_INTERVAL_SEC, INITIAL_BALANCE_USD, get_auto_trade_enabled
from indicators import TechnicalIndicators
from database import async_save_signal_cache_db, async_sync_account_from_closed_trades
from alpha_vantage_news import get_client as get_news_client
# Import async_timed decorator
from utils.decorators import async_timed
from services.strategy_manager import get_symbol_strategy, get_strategy_manager, analyze_with_new_strategy
# Lazy imports used inside functions to avoid circular dependency
# (imported from main.py at function call time)
from services.market_data import get_cached_candles


async def auto_trade_loop():
    """
    Background loop that runs autonomously:
    1. Updates prices & checks TP/SL on open positions (auto-closes hits)
    2. Generates fresh signals for all instruments
    3. Opens trades automatically when signal is strong enough
    4. Persists account state to DB
    """
    # Lazy imports to avoid circular dependency
    from services.state import broker
    
    from services.circuit_breaker import check_circuit_breaker
    from services.market_hours import is_market_open, get_market_hours
    from services.signal_generator import calculate_position_size
    account = broker.get_account()
    closed_positions = broker.get_closed_positions()
    # Wait a few seconds for startup to finish
    await asyncio.sleep(5)
    log_event("[AUTO-TRADE] Background trading loop started", "event")

    iteration_count = 0
    while True:
        iteration_count += 1
        
        # CAŁOŚCIOWY EXCEPTION HANDLER - żeby pętla NIGDY się nie zatrzymała
        try:
            try:
                print(f"[DEBUG AUTO-TRADE] === START ITERATION #{iteration_count} ===")
            except Exception as e:
                print(f"[DEBUG] Failed to print start: {e}")
            
            # Check if auto-trade is enabled
            if not get_auto_trade_enabled():
                print(f"[DEBUG] Auto-trade DISABLED! Sleeping 30s...")
                log_event("[AUTO-TRADE] Auto-trade disabled, sleeping 30s...", "info")
                await asyncio.sleep(30)
                continue
                
            print(f"[DEBUG] Auto-trade enabled, continuing...")

            # ── Step 1: Update prices & auto-close TP/SL ──
            try:
                auto_closed = await asyncio.wait_for(broker._async_update_prices(), timeout=10.0)
                if auto_closed:
                    for closed in auto_closed:
                        pos = closed.get("position", {})
                        reason = closed.get("exit_reason", "TP/SL")
                        pnl = pos.get("pnl_usd", 0)
                        sym = pos.get("symbol", "?")
                        log_event(
                            f"[AUTO-CLOSE] {sym} {pos.get('direction', '').upper()} hit {reason} "
                            f"| P&L: {'+'if pnl>=0 else ''}{pnl:.2f} USD",
                            "success" if pnl >= 0 else "warning",
                        )
                    await async_save_account(account)
            except asyncio.TimeoutError:
                log_event("[AUTO-TRADE] Timeout updating prices!", "error")
            except Exception as e:
                log_event(f"[AUTO-TRADE] Error updating prices: {e}", "error")

            # ── Step 2: Generate fresh signals ──
            try:
                log_event(f"[AUTO-TRADE] Calling generate_signals()...", "info")
                print(f"[DEBUG] About to call generate_signals()")
                signals = await asyncio.wait_for(generate_signals(), timeout=45.0)
                log_event(f"[AUTO-TRADE] generate_signals() returned {len(signals)} signals", "info")
                print(f"[DEBUG] generate_signals() returned {len(signals)} signals")
            except asyncio.TimeoutError:
                log_event("[AUTO-TRADE] Timeout generating signals!", "error")
                signals = []
            except Exception as e:
                log_event(f"[AUTO-TRADE] Error generating signals: {e}", "error")
                signals = []

            # Update signals cache for TP/SL reference
            signals_cache = {s.symbol: s for s in signals}

            # ── Step 3: Auto-execute trades on strong signals ──
            print(f"[DEBUG] Checking circuit breaker...")
            can_trade, reason = check_circuit_breaker()
            print(f"[DEBUG] Circuit breaker check: can_trade={can_trade}, reason={reason}")
            # Get risk adjustments from circuit breaker
            size_multiplier = account.get("_risk_multiplier", 1.0)
            min_score_boost = account.get("_min_score_boost", 0.0)

            if can_trade:
                # ── Step 2.5: Dynamic Positions - close weak profitable positions ──
                current_signals = {s.symbol: s.score for s in signals}
                
                # Get fresh positions from broker
                open_positions = broker.get_open_positions()
                
                # DEBUG: Log all current signals and open positions scores
                log_event(f"[DYNAMIC-DEBUG] Current signals: {current_signals}", "info")
                for pos in open_positions:
                    sym = pos.get("symbol")
                    orig_score = pos.get("original_signal_score", 0)
                    pnl = pos.get("unrealized_pnl_usd", 0)
                    log_event(f"[DYNAMIC-DEBUG] {sym} | orig_score={orig_score:.3f} | curr={current_signals.get(sym, 0):.3f} | PnL=${pnl:.2f}", "info")
                
                positions_to_close = broker.check_dynamic_exit(current_signals)
                log_event(f"[DYNAMIC-EXIT] IDs to close: {positions_to_close} | Open positions: {[p['id'] for p in open_positions]}", "info")
                if positions_to_close:
                    log_event(f"[DYNAMIC-EXIT] Checking {len(positions_to_close)} positions for exit...", "info")
                    for pos_id in positions_to_close:
                        pos = next((p for p in open_positions if p["id"] == pos_id), None)
                        if pos:
                            try:
                                quote = await data_provider.get_quote(pos["symbol"])
                                exit_price = quote.get("price") if quote else None
                            except:
                                exit_price = None
                            result = await broker.close_position(pos_id, exit_price=exit_price)
                            if "error" not in result:
                                pnl = result.get("position", {}).get("pnl_usd", 0)
                                log_event(f"[DYNAMIC-CLOSE] {pos['symbol']} | P&L: ${pnl:.2f} | Signal decayed", "info")
                            else:
                                log_event(f"[DYNAMIC-CLOSE] Failed: {result['error']}", "warning")
                    await async_save_account(account)

                for signal in signals:
                    if signal.direction in (SignalDirection.NEUTRAL,):
                        continue

                    sym = signal.symbol
                    # The strategy's min_score gate already ran inside SignalEngine.evaluate
                    # (backtest applies the identical gate - no live/backtest divergence).
                    # Only the circuit-breaker recovery boost adds an extra hurdle here.
                    if min_score_boost > 0 and abs(signal.score) < min_score_boost:
                        continue

                    if signal.direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY):
                        direction = "buy"
                    elif signal.direction in (SignalDirection.SELL, SignalDirection.STRONG_SELL):
                        direction = "sell"
                    else:
                        continue

                    already_open = any(p["symbol"] == sym and p["direction"] == direction for p in open_positions)
                    if already_open:
                        continue

                    trade_enabled = db.get_setting(f"TRADE_ENABLED_{sym}", 1)
                    if not trade_enabled:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - trading disabled", "info")
                        continue

                    if not is_market_open(sym):
                        log_event(f"[AUTO-TRADE] Skipping {sym} - market closed ({get_market_hours(sym)})", "info")
                        continue

                    max_positions = db.get_setting("MAX_OPEN_POSITIONS", 3)
                    if len(open_positions) >= max_positions:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - max {max_positions} positions reached", "info")
                        continue

                    quote = await data_provider.get_quote(sym)
                    if not quote:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - cannot get current price", "warning")
                        continue

                    entry_price = quote["price"]

                    # Recalculate TP/SL from fresh ATR
                    fresh_candles = None
                    try:
                        fresh_candles = await get_cached_candles(sym, "60", 50, data_provider)
                        if fresh_candles and len(fresh_candles) >= 20:
                            ind = TechnicalIndicators.calculate_all(fresh_candles, period=14)
                            atr = ind.get("atr_14", entry_price * 0.01)
                        else:
                            atr = entry_price * 0.01
                    except Exception:
                        atr = entry_price * 0.01

                    # Get strategy config for TP/SL
                    strategy_id = get_symbol_strategy(sym)
                    strategy_json_id = strategy_id.replace("JSON:", "") if strategy_id else None
                    strategy_config_for_tp = {}
                    if strategy_json_id:
                        from services.strategy_manager import get_strategy_manager
                        manager = get_strategy_manager()
                        if strategy_json_id in manager.strategies:
                            strategy_config_for_tp = manager.strategies[strategy_json_id].config
                    
                    take_profit, stop_loss = get_adaptive_tp_sl(
                        strategy_config=strategy_config_for_tp,
                        candles=fresh_candles,
                        entry_price=entry_price,
                        direction=direction
                    )

                    # Calculate dynamic position size based on signal score, confidence, open positions, volatility
                    open_pos_count = len(broker.get_open_positions())
                    
                    # Get volatility from candles
                    volatility = 0.0
                    if fresh_candles and len(fresh_candles) >= 20:
                        try:
                            
                            ind = TechnicalIndicators.calculate_all(fresh_candles, period=14)
                            atr = ind.get('atr_14', 0)
                            volatility = (atr / entry_price) * 100 if entry_price > 0 else 0
                        except:
                            pass
                    
                    # Get strategy config for position sizing
                    strategy_id = get_symbol_strategy(sym)
                    strategy_json_id = strategy_id.replace("JSON:", "") if strategy_id else None
                    strategy_config = {}
                    if strategy_json_id:
                        from services.strategy_manager import get_strategy_manager
                        manager = get_strategy_manager()
                        if strategy_json_id in manager.strategies:
                            strategy_config = manager.strategies[strategy_json_id].config
                    
                    account = broker.get_account()
                    balance = account.get('balance_usd', 3000)
                    
                    size = calculate_dynamic_position_size(
                        strategy_config=strategy_config,
                        account_balance=balance,
                        entry_price=entry_price,
                        stop_loss_price=stop_loss,
                        signal_score=signal.score,
                        signal_confidence=signal.confidence,
                        open_positions_count=open_pos_count,
                        volatility=volatility
                    ) * size_multiplier

                    result = await broker.open_position(
                        symbol=sym,
                        direction=direction,
                        size=size,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        entry_price=entry_price,
                        signal_score=signal.score,
                    )
                    if "error" not in result:
                        log_event(
                            f"[AUTO-TRADE] Opened {direction.upper()} {sym} @ {entry_price:.2f} "
                            f"| Score: {signal.score:.3f} | SL: {stop_loss:.2f} TP: {take_profit:.2f}",
                            "success",
                        )
                    else:
                        log_event(f"[AUTO-TRADE] Failed to open {sym}: {result['error']}", "warning")
            else:
                log_event(f"[AUTO-TRADE] Skipping: {reason}", "info")

            # ── Step 4: Persist state ──
            await async_save_account(account)
            
            # Get signal history cache
            from services.state import get_signal_history_cache
            signal_history_cache = get_signal_history_cache()
            await async_save_signal_cache_db(signal_history_cache)

            log_event(
                f"[AUTO-TRADE] Scan complete | Balance: ${account['balance_usd']:.2f} USD "
                f"| Open: {len(open_positions)} | Closed: {len(closed_positions)}",
                "info",
            )

        except Exception as e:
            import traceback
            log_event(f"[AUTO-TRADE] Error in trading loop: {str(e)}", "error")
            log_event(f"[AUTO-TRADE] Traceback: {traceback.format_exc()}", "error")

        # Sleep in chunks to avoid event loop issues
        sleep_cycles = AUTO_TRADE_INTERVAL_SEC // 60
        remaining = AUTO_TRADE_INTERVAL_SEC % 60
        
        print(f"[DEBUG] Auto-trade iteration #{iteration_count} complete. Going to sleep for {sleep_cycles*60 + remaining}s...")
        
        try:
            for i in range(sleep_cycles):
                print(f"[DEBUG] Sleep cycle {i+1}/{sleep_cycles}...")
                await asyncio.wait_for(asyncio.sleep(60), timeout=65)
            if remaining > 0:
                print(f"[DEBUG] Final sleep {remaining}s...")
                await asyncio.wait_for(asyncio.sleep(remaining), timeout=remaining + 5)
            print(f"[DEBUG] Wake up! Starting iteration #{iteration_count + 1}")
        except asyncio.TimeoutError:
            print("[DEBUG] Sleep timeout! Continuing anyway...")
            await asyncio.sleep(30)
        except Exception as e:
            print(f"[DEBUG] Sleep exception: {e}")
            log_event(f"[AUTO-TRADE] Error in sleep: {str(e)}", "error")
            await asyncio.sleep(30)
        
        # Final heartbeat - we're still alive!
        print(f"[DEBUG] Final heartbeat for iteration #{iteration_count}")
        
        # ALWAYS continue the loop - this should NEVER be reached unless there's an issue
        print(f"[DEBUG] About to loop back to start...")
        # Explicit continue to make sure we don't exit
        continue


async def execute_trade(symbol: str, direction: str, volume: float, signal_score: float = 0.0, take_profit: float = None, stop_loss: float = None) -> Dict:
    """Execute a trade - wrapper around broker.open_position"""
    from main import broker
    result = await broker.open_position(
        symbol=symbol,
        direction=direction,
        size=volume,
        signal_score=signal_score,
        take_profit=take_profit,
        stop_loss=stop_loss,
    )
    return result


def check_circuit_breaker() -> bool:
    """Check if trading should be allowed - wrapper"""
    from services.circuit_breaker import check_circuit_breaker as _cb
    allowed, _ = _cb()
    return allowed


_api_semaphore = None

def _get_api_semaphore():
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(3)
    return _api_semaphore


def _neutral_signal(symbol: str, price: float = 0.0, timeframe: str = "5") -> Signal:
    """Neutral no-trade signal. Used for every fallback/error path."""
    return Signal(
        symbol=symbol,
        direction=SignalDirection.NEUTRAL,
        score=0.0,
        confidence=0.0,
        technical_score=0.0,
        price_action_score=0.0,
        news_score=0.0,
        components=[],
        current_price=price,
        time_horizon=timeframe,
        entry_point=price,
        take_profit=0.0,
        stop_loss=0.0,
        risk_reward_ratio=0.0,
    )


async def _analyze_single_symbol(symbol: str, info: dict, news_client_instance) -> Signal:
    """Analyze one symbol: quote -> multi-timeframe candle series -> SignalEngine -> Signal."""
    # Lazy imports to avoid circular dependency
    from services.state import get_live_price_cache as _price_cache, get_symbol_strategy
    from services.strategy_manager import get_strategy_manager, analyze_with_new_strategy
    from services.market_data import get_cached_quote as _get_cached_quote
    from services.candle_store import get_candle_store
    from strategy.engine import SignalEngine
    from timeframes import TimeFrame

    timeframe = "5"
    try:
        quote = _get_cached_quote(symbol)

        last_known_price = 0.0
        price_cache = _price_cache()
        if symbol in price_cache:
            last_known_price = price_cache[symbol].get('price', 0)

        if not quote:
            return _neutral_signal(symbol, last_known_price, timeframe)
        current_price = quote["price"]

        manager = get_strategy_manager()
        if not manager or len(manager.strategies) == 0:
            print("[STRATEGY] No strategies available in manager")
            return _neutral_signal(symbol, current_price, timeframe)

        # Resolve the strategy config to learn which timeframes it needs
        selected_strategy = get_symbol_strategy(symbol)
        strategy_obj = manager.strategies.get(selected_strategy.replace("JSON:", ""))
        if strategy_obj is None:
            for cand in manager.get_enabled_strategies():
                if cand.symbol.upper() == symbol.upper():
                    strategy_obj = cand
                    break
        if strategy_obj is None:
            return _neutral_signal(symbol, current_price, timeframe)

        engine = SignalEngine(strategy_obj.config)
        base_tf = engine.base_timeframe()
        timeframe = base_tf.db_resolution

        # One CandleStore fetch per required timeframe; closed candles only.
        store = get_candle_store()
        series = {}
        for tf in engine.required_timeframes():
            tf_series = await store.get_series(symbol, tf, min_bars=120)
            if tf_series.candles:
                series[tf] = tf_series

        base_series = series.get(base_tf)
        if base_series is None or len(base_series.candles) < 20:
            return _neutral_signal(symbol, current_price, timeframe)

        # VIX: TTL-cached, one fetch per index per cycle
        vix_value = None
        try:
            vix_data = await store.get_vix(symbol)
            vix_value = vix_data.get("value") if vix_data else None
        except Exception:
            pass

        new_result = analyze_with_new_strategy(
            symbol,
            base_series.candles,
            current_price,
            requested_strategy=selected_strategy if selected_strategy.startswith("JSON:") else None,
            vix_value=vix_value,
            series=series,
        )

        if not new_result:
            return _neutral_signal(symbol, current_price, timeframe)

        json_score = max(-1.0, min(1.0, new_result["score"]))
        json_technical = max(-1.0, min(1.0, new_result["technical_score"]))

        return Signal(
            symbol=symbol,
            direction=SignalDirection.BUY if new_result["direction"] == "long" else SignalDirection.SELL,
            score=json_score,
            confidence=new_result["confidence"],
            technical_score=json_technical,
            price_action_score=0.0,
            news_score=0.0,
            components=new_result["components"],
            current_price=current_price,
            time_horizon=timeframe,
            entry_point=current_price,
            take_profit=new_result.get("exits", {}).get("tp_price", 0) or 0,
            stop_loss=new_result.get("exits", {}).get("sl_price", 0) or 0,
            risk_reward_ratio=new_result.get("risk_reward_ratio") or 0,
        )

    except Exception as e:
        log_event(f"Error analyzing {symbol}: {e}", "error")
        return _neutral_signal(symbol, 0.0, timeframe)


@async_timed("generate_signals")
async def generate_signals() -> List[Signal]:
    """Generate trading signals for all instruments using regime-adaptive scoring - PARALLEL"""
    try:
        return await asyncio.wait_for(_generate_signals_internal(), timeout=60.0)
    except asyncio.TimeoutError:
        log_event("[SIGNALS] Timeout generating signals!", "error")
        return []

async def _generate_signals_internal() -> List[Signal]:
    """Internal signal generation with timeout wrapper"""
    """Generate trading signals for all instruments using regime-adaptive scoring - PARALLEL"""
    account = broker.get_account()
    now = datetime.utcnow().isoformat()
    account["last_scan"] = now
    print(f"[DEBUG] generate_signals set last_scan to {now}")

    # Track peak equity (balance + unrealized P&L) for drawdown calculation
    current_equity = account.get("equity_usd", account.get("balance_usd", INITIAL_BALANCE_USD))
    if current_equity > account.get("peak_equity_usd", INITIAL_BALANCE_USD):
        account["peak_equity_usd"] = current_equity
    # Keep peak_balance_usd for backward compatibility
    if account["balance_usd"] > account.get("peak_balance_usd", INITIAL_BALANCE_USD):
        account["peak_balance_usd"] = account["balance_usd"]

    news_client_instance = get_news_client()

    # Run all symbol analysis in PARALLEL
    symbols = list(INSTRUMENTS.keys())
    tasks = [_analyze_single_symbol(symbol, info, news_client_instance) for symbol, info in INSTRUMENTS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals = []
    for symbol, res in zip(symbols, results):
        if isinstance(res, BaseException):
            log_event(f"Error analyzing {symbol}: {res}", "error")
            signals.append(_neutral_signal(symbol))
        else:
            signals.append(res)

    # Log results
    # Log results
    for signal in signals:
        if signal.direction != SignalDirection.NEUTRAL:
            log_event(
                f"[SIGNAL] {signal.symbol}: {signal.direction.value} | Score: {signal.score:.2f} | Conf: {signal.confidence:.0%} | ${signal.current_price:.2f}",
                "event",
            )

    # Update equity after signals
    await async_sync_account_from_closed_trades()

    return signals

# === Adaptive TP/SL Helper Functions ===

def calculate_adaptive_tp_sl(strategy_config: dict, candles: list, entry_price: float, direction: str) -> tuple:
    """
    Calculate TP/SL using adaptive algorithm combining:
    - Base percentage from strategy
    - ATR-based levels
    - Support/Resistance levels
    """
    from strategy.support_resistance import calculate_optimal_tp_sl as sr_calc
    
    exits_v2 = strategy_config.get('exits_v2', {})
    
    if not exits_v2 or exits_v2.get('tp_method') != 'adaptive':
        # Fallback to simple percentage
        base_tp = exits_v2.get('base_tp_percent', 2.5) if exits_v2 else 2.5
        base_sl = exits_v2.get('base_sl_percent', 1.5) if exits_v2 else 1.5
        
        if direction == 'buy':
            return (
                entry_price * (1 + base_tp / 100),
                entry_price * (1 - base_sl / 100)
            )
        else:
            return (
                entry_price * (1 - base_tp / 100),
                entry_price * (1 + base_sl / 100)
            )
    
    # Use adaptive algorithm
    result = sr_calc(
        candles=candles,
        entry_price=entry_price,
        direction=direction,
        base_tp_percent=exits_v2.get('base_tp_percent', 2.5),
        base_sl_percent=exits_v2.get('base_sl_percent', 1.5),
        atr_multiplier=exits_v2.get('atr_multiplier', 2.0),
        min_rr_ratio=exits_v2.get('min_rr_ratio', 1.5)
    )
    
    return result['take_profit'], result['stop_loss']


# === Adaptive TP/SL Helper ===
def get_adaptive_tp_sl(strategy_config: dict, candles: list, entry_price: float, direction: str) -> tuple:
    """
    Calculate TP/SL using adaptive algorithm combining base %, ATR, and S/R levels
    """
    try:
        from strategy.support_resistance import calculate_optimal_tp_sl
        
        exits_v2 = strategy_config.get('exits_v2', {}) if strategy_config else {}
        
        if not exits_v2 or exits_v2.get('tp_method') != 'adaptive':
            # Fallback: simple ATR
            atr = entry_price * 0.015
            if direction == 'buy':
                return (entry_price + atr*2, entry_price - atr*1.5)
            else:
                return (entry_price - atr*2, entry_price + atr*1.5)
        
        result = calculate_optimal_tp_sl(
            candles=candles,
            entry_price=entry_price,
            direction=direction,
            base_tp_percent=exits_v2.get('base_tp_percent', 2.5),
            base_sl_percent=exits_v2.get('base_sl_percent', 1.5),
            atr_multiplier=exits_v2.get('atr_multiplier', 2.0),
            min_rr_ratio=exits_v2.get('min_rr_ratio', 1.5)
        )
        return result['take_profit'], result['stop_loss']
    except Exception as e:
        # Fallback
        atr = entry_price * 0.015
        if direction == 'buy':
            return (entry_price + atr*2, entry_price - atr*1.5)
        else:
            return (entry_price - atr*2, entry_price + atr*1.5)


def calculate_dynamic_position_size(
    strategy_config: dict,
    account_balance: float,
    entry_price: float,
    stop_loss_price: float,
    signal_score: float,
    signal_confidence: float,
    open_positions_count: int,
    volatility: float = 0.0
) -> float:
    """
    Calculate position size dynamically based on multiple factors:
    - Signal score (higher score = bigger position)
    - Signal confidence (higher confidence = bigger position)
    - Number of open positions (more positions = smaller size)
    - Volatility (higher volatility = smaller size)
    """
    from app.config import INSTRUMENTS as _INSTRUMENTS
    from services.signal_generator import calculate_position_size

    symbol = strategy_config.get('symbol', 'XAU')
    sizing_v2 = strategy_config.get('position_sizing_v2', {})

    if not sizing_v2 or sizing_v2.get('method') != 'adaptive':
        # Simple fallback: same convention (units of underlying), real symbol and balance
        return calculate_position_size(symbol, entry_price, stop_loss_price, account_balance)

    base_risk_percent = sizing_v2.get('base_risk_percent', 1.5)
    max_leverage = sizing_v2.get('max_leverage', 10)
    min_leverage = sizing_v2.get('min_leverage', 5)
    modifiers = sizing_v2.get('modifiers', {})

    # Modifier 1: signal score, 2: confidence, 3: open positions, 4: volatility
    score_modifier = abs(signal_score)
    confidence_modifier = signal_confidence
    pos_modifiers = modifiers.get('by_open_positions', {})
    if open_positions_count == 0:
        pos_mod = pos_modifiers.get('0', 1.0)
    elif open_positions_count == 1:
        pos_mod = pos_modifiers.get('1', 0.8)
    elif open_positions_count == 2:
        pos_mod = pos_modifiers.get('2', 0.6)
    else:
        pos_mod = pos_modifiers.get('3+', 0.4)
    if volatility > 2.0:
        vol_mod = modifiers.get('by_volatility', {}).get('high', 0.5)
    elif volatility > 1.0:
        vol_mod = modifiers.get('by_volatility', {}).get('medium', 0.75)
    else:
        vol_mod = modifiers.get('by_volatility', {}).get('low', 1.0)

    combined_modifier = score_modifier * confidence_modifier * pos_mod * vol_mod
    adjusted_risk = max(base_risk_percent * combined_modifier, 0.5)  # floor 0.5%

    # Risk-based size in UNITS of the underlying: if SL is hit, loss ~= adjusted_risk% of
    # balance. Same convention as broker P&L (delta_price * size) and the backtester.
    risk_amount = account_balance * (adjusted_risk / 100)
    risk_per_unit = abs(entry_price - stop_loss_price)
    if risk_per_unit <= 0:
        risk_per_unit = entry_price * 0.02
    size = risk_amount / risk_per_unit

    # Leverage caps NOTIONAL, it never multiplies size. Instrument cap always wins.
    instrument_cap = _INSTRUMENTS.get(symbol, {}).get("leverage", 10)
    leverage = max(min_leverage, max_leverage * combined_modifier)
    leverage = min(leverage, max_leverage, instrument_cap)  # cap wins over the floor
    max_size = account_balance * leverage / entry_price
    size = min(size, max_size)

    print(f"[POSITION SIZE] {symbol}: risk {adjusted_risk:.2f}% | size {size:.4f} units | lev cap {leverage:.1f}x")
    return max(round(size, 6), 0.0)
