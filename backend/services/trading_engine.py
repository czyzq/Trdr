"""Trading engine - extracted from main.py"""
import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime

# Import Signal and SignalDirection from models
from models import Signal, SignalDirection

# Import async_timed decorator
from utils.decorators import async_timed

# Lazy imports used inside functions to avoid circular dependency
# (imported from main.py at function call time)


async def auto_trade_loop():
    """
    Background loop that runs autonomously:
    1. Updates prices & checks TP/SL on open positions (auto-closes hits)
    2. Generates fresh signals for all instruments
    3. Opens trades automatically when signal is strong enough
    4. Persists account state to DB
    """
    # Lazy imports to avoid circular dependency
    from main import (
        account, INSTRUMENTS, get_news_client, sync_account_from_closed_trades, 
        async_save_account, log_event
    )
    from circuit_breaker import check_circuit_breaker
    from market_hours import is_market_open, get_market_hours
    from signal_generator import calculate_position_size

    # Wait a few seconds for startup to finish
    await asyncio.sleep(5)
    log_event("[AUTO-TRADE] Background trading loop started", "event")

    iteration_count = 0
    while True:
        iteration_count += 1
        try:
            print(f"[DEBUG AUTO-TRADE] Loop iteration #{iteration_count} at {datetime.utcnow().isoformat()}")
            if not AUTO_TRADE_ENABLED:
                await asyncio.sleep(AUTO_TRADE_INTERVAL_SEC)
                continue

            # ── Step 1: Update prices & auto-close TP/SL ──
            auto_closed = await broker._async_update_prices()
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

            # ── Step 2: Generate fresh signals ──
            signals = await generate_signals()

            # Update signals cache for TP/SL reference
            signals_cache = {s.symbol: s for s in signals}

            # ── Step 3: Auto-execute trades on strong signals ──
            can_trade, reason = check_circuit_breaker()
            # Get risk adjustments from circuit breaker
            size_multiplier = account.get("_risk_multiplier", 1.0)
            min_score_boost = account.get("_min_score_boost", 0.0)

            if can_trade:
                # ── Step 2.5: Dynamic Positions - close weak profitable positions ──
                current_signals = {s.symbol: s.score for s in signals if s.direction not in (SignalDirection.NEUTRAL,)}
                positions_to_close = broker.check_dynamic_exit(current_signals)
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
                    info = INSTRUMENTS.get(sym, {})
                    min_score = info.get("min_score", 0.15) + min_score_boost

                    if abs(signal.score) < min_score:
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
                    try:
                        from main import _get_cached_candles
                        from indicators import TechnicalIndicators
                        fresh_candles = await _get_cached_candles(sym, "60", 50)
                        if fresh_candles and len(fresh_candles) >= 20:
                            ind = TechnicalIndicators.calculate_all(fresh_candles, period=14)
                            atr = ind.get("atr_14", entry_price * 0.01)
                        else:
                            atr = entry_price * 0.01
                    except Exception:
                        atr = entry_price * 0.01

                    if direction == "buy":
                        take_profit = entry_price + (atr * 3)
                        stop_loss = entry_price - (atr * 2)
                    else:
                        take_profit = entry_price - (atr * 3)
                        stop_loss = entry_price + (atr * 2)

                    size = calculate_position_size(sym, entry_price, stop_loss) * size_multiplier

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
            from main import signal_history_cache
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
        
        try:
            for i in range(sleep_cycles):
                await asyncio.sleep(60)
            if remaining > 0:
                await asyncio.sleep(remaining)
        except Exception as e:
            log_event(f"[AUTO-TRADE] Error in sleep: {str(e)}", "error")
            await asyncio.sleep(30)


async def execute_trade(symbol: str, direction: str, volume: float) -> Dict:
    """Execute a trade - wrapper around broker.open_position"""
    from main import broker
    result = await broker.open_position(
        symbol=symbol,
        direction=direction,
        size=volume,
    )
    return result


def check_circuit_breaker() -> bool:
    """Check if trading should be allowed - wrapper"""
    from circuit_breaker import check_circuit_breaker as _cb
    allowed, _ = _cb()
    return allowed


async def _analyze_single_symbol(symbol: str, info: dict, news_client_instance) -> Signal:
    """Analyze a single symbol - runs in parallel for all symbols."""
    # Lazy imports to avoid circular dependency
    from main import _price_cache, _api_semaphore, get_symbol_strategy, get_strategy_manager
    from services.market_data import get_cached_quote as _get_cached_quote
    
    timeframe = "5"
    
    try:
        async with _api_semaphore:
            quote = await asyncio.wait_for(_get_cached_quote(symbol), timeout=5.0)

        last_known_price = 0.0
        if symbol in _price_cache:
            last_known_price = _price_cache[symbol][0]

        if not quote:
            # Return neutral signal with last known price if available
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=last_known_price,
                time_horizon=timeframe,
                entry_point=last_known_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        current_price = quote["price"]

        # Get timeframe from selected strategy (convert to db_resolution for compatibility)
        selected_strategy = get_symbol_strategy(symbol)
        
        # Use StrategyManager from JSON (supports timeframe)
        manager = get_strategy_manager()
        strategy_obj = manager.strategies.get(selected_strategy)
        if not strategy_obj:
            strategy_obj = manager.strategies.get('xau_v3_exp')
        
        # Handle both string and TimeFrame enum
        tf_value = strategy_obj.timeframe if strategy_obj and hasattr(strategy_obj, 'timeframe') else "5m"
        if hasattr(tf_value, 'value'):
            tf_value = tf_value.value
        
        # Convert to db_resolution (e.g., "5m" -> "5")
        try:
            tf_enum = TimeFrame(tf_value)
            timeframe = tf_enum.db_resolution
        except ValueError:
            timeframe = "5"  # fallback
        
        # Use cached candles with strategy's timeframe
        async with _api_semaphore:
            candles = await asyncio.wait_for(_get_cached_candles(symbol, timeframe, 100), timeout=10.0)
        if not candles or len(candles) < 20:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=current_price,
                time_horizon=timeframe,
                entry_point=current_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        indicators = TechnicalIndicators.calculate_all(candles, period=14)
        if not indicators:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=current_price,
                time_horizon=timeframe,
                entry_point=current_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        # Filter indicators based on per-symbol settings
        enabled_key = f"INDICATORS_{symbol}"
        enabled_indicators = db.get_setting(enabled_key)
        if enabled_indicators:
            # Map indicator names to their keys in the indicators dict
            indicator_map = {
                "RSI": ["rsi_14"],
                "MACD": ["macd", "macd_signal", "macd_hist"],
                "BB": ["bb_upper", "bb_lower", "bb_middle"],
                "SMA": ["sma_20", "sma_50", "sma_200"],
                "ADX": ["adx"],
                "STOCH": ["stoch_k", "stoch_d"],
                "MOMENTUM": ["momentum"],
                "WILLIAMS_R": ["williams_r"],
            }
            # Filter indicators dict to only include enabled ones
            filtered = {"_closes": indicators.get("_closes", [])}
            for ind_name in enabled_indicators:
                keys = indicator_map.get(ind_name, [])
                for key in keys:
                    if key in indicators:
                        filtered[key] = indicators[key]
            indicators = filtered

        indicators["_closes"] = [c["close"] for c in candles]

        # ── Multi-timeframe: fetch daily candles for higher-TF trend ──
        htf_bias = 0.0
        try:
            async with _api_semaphore:
                htf_candles = await asyncio.wait_for(_get_cached_candles(symbol, "D", 60), timeout=10.0)
            if htf_candles and len(htf_candles) >= 20:
                htf_ind = TechnicalIndicators.calculate_all(htf_candles, period=14)
                if htf_ind:
                    htf_sma20 = htf_ind.get("sma_20")
                    htf_sma50 = htf_ind.get("sma_50")
                    htf_adx = htf_ind.get("adx")
                    htf_price = htf_candles[-1]["close"]
                    if htf_sma20 and htf_sma50 and htf_sma50 > 0:
                        sma_diff = ((htf_sma20 - htf_sma50) / htf_sma50) * 100
                        htf_bias = max(-1, min(1, sma_diff / 3))
                    if htf_adx and htf_adx["adx"] > 30 and abs(htf_bias) > 0.1:
                        htf_bias *= 1.3
                        htf_bias = max(-1, min(1, htf_bias))
        except Exception:
            pass  # MTF is optional

        # ── VIX Filter (v2) ──
        # Get instrument-specific volatility index
        vix_data = None
        try:
            from historical_data import get_volatility_index

            vix_data = get_volatility_index(symbol)
            if vix_data:
                indicators["vix"] = vix_data
                print(
                    f"[VIX] {symbol}: {vix_data['value']} ({vix_data['name']}, change: {vix_data['change_pct']:+.1f}%)"
                )
            else:
                # Fallback to standard VIX
                vix_data = get_volatility_index("SPX")
                if vix_data:
                    indicators["vix"] = vix_data
        except Exception as e:
            print(f"[VIX] Could not fetch VIX for {symbol}: {e}")

        # ── Volatility filter ──
        # NOTE: Volatility check now handled by Strategy's filter config
        # The strategy.json defines volatility filter per-strategy
        atr = indicators.get("atr_14", current_price * 0.01)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

        # ── News sentiment (disabled to speed up - optional feature) ──
        news_score = 0.0
        # try:
        #     async with _api_semaphore:
        #         news = await asyncio.wait_for(
        #             news_client_instance.get_news(symbol, 5),
        #             timeout=1.0  # Quick timeout - don't wait for news
        #         )
        #     if news and len(news) > 0:
        #         sentiments = [article.get('sentiment', 0) for article in news]
        #         news_score = sum(sentiments) / len(sentiments) if sentiments else 0
        # except Exception:
        #     pass  # News is optional

        # ── Get selected strategy from DB ──
        selected_strategy = get_symbol_strategy(symbol)
        
        # ── Try JSON-based strategy (if selected or default) ──
        # If user selected a JSON strategy, use that one. Otherwise use any available JSON strategy for this symbol
        new_result = analyze_with_new_strategy(
            symbol, 
            candles, 
            current_price, 
            account.get("balance_usd", 3000),
            requested_strategy=selected_strategy if selected_strategy.startswith("JSON:") else None,
            atr_percent=atr_pct,
            vix_value=vix_data.get('value') if vix_data else None
        )
        
        if new_result:
            print(f"[STRATEGY] Using NEW JSON strategy for {symbol}: {new_result.get('strategy_id')}")
            # Clamp scores to valid range [-1, 1]
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
                take_profit=new_result["take_profit"],
                stop_loss=new_result["stop_loss"],
                risk_reward_ratio=new_result["risk_reward_ratio"],
            )

        # ── Fallback: OLD strategy (DEPRECATED - see strategies.py) ──
        # ⚠️ DEPRECATED: Old strategy code - migrate to JSON-based strategies
        strategy_id = get_symbol_strategy(symbol)
        strategy = get_strategy(strategy_id)
        indicators["_closes"] = [c["close"] for c in candles]

        result = strategy.score(
            candles=candles,
            indicators=indicators,
            symbol=symbol,
            instrument_info=info,
            current_price=current_price,
            htf_bias=htf_bias,
            news_score=news_score,
        )

        # Clamp scores to valid range [-1, 1] - safety guard
        safe_score = max(-1.0, min(1.0, result["score"]))
        safe_technical = max(-1.0, min(1.0, result["technical_score"]))
        
        signal = Signal(
            symbol=symbol,
            direction=result["direction"],
            score=safe_score,
            confidence=result["confidence"],
            technical_score=safe_technical,
            price_action_score=0.0,
            news_score=news_score,
            components=result["components"],
            current_price=current_price,
            time_horizon=timeframe,
            entry_point=current_price,
            take_profit=result["take_profit"],
            stop_loss=result["stop_loss"],
            risk_reward_ratio=result["risk_reward_ratio"],
        )

        return signal

    except Exception as e:
        log_event(f"Error analyzing {symbol}: {e}", "error")
        return Signal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            score=0.0,
            confidence=0.0,
            technical_score=0.0,
            price_action_score=0.0,
            news_score=0.0,
            components=[],
            current_price=0.0,
            time_horizon=timeframe,
            entry_point=0.0,
            take_profit=0.0,
            stop_loss=0.0,
            risk_reward_ratio=0.0,
        )

@async_timed("generate_signals")
async def generate_signals() -> List[Signal]:
    """Generate trading signals for all instruments using regime-adaptive scoring - PARALLEL"""
    # Lazy imports to avoid circular dependency
    from main import account, INITIAL_BALANCE_USD, get_news_client, sync_account_from_closed_trades, log_event, INSTRUMENTS
    from services.trading_engine import _analyze_single_symbol
    
    now = datetime.utcnow().isoformat()
    account["last_scan"] = now
    print(f"[DEBUG] generate_signals set last_scan to {now}")

    # Track peak equity (balance + unrealized P&L) for drawdown calculation
    current_equity = account.get("equity_usd", account["balance_usd"])
    if current_equity > account.get("peak_equity_usd", INITIAL_BALANCE_USD):
        account["peak_equity_usd"] = current_equity
    # Keep peak_balance_usd for backward compatibility
    if account["balance_usd"] > account.get("peak_balance_usd", INITIAL_BALANCE_USD):
        account["peak_balance_usd"] = account["balance_usd"]

    news_client_instance = get_news_client()

    # Run all symbol analysis in PARALLEL
    tasks = [_analyze_single_symbol(symbol, info, news_client_instance) for symbol, info in INSTRUMENTS.items()]
    signals = await asyncio.gather(*tasks)

    # Log results
    # Log results
    for signal in signals:
        if signal.direction != SignalDirection.NEUTRAL:
            log_event(
                f"[SIGNAL] {signal.symbol}: {signal.direction.value} | Score: {signal.score:.2f} | Conf: {signal.confidence:.0%} | ${signal.current_price:.2f}",
                "event",
            )

    # Update equity after signals
    await sync_account_from_closed_trades()

    return signals