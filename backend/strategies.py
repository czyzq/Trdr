"""
Trading strategy abstraction layer.

Strategies:
  1. AdaptiveRegime — original multi-factor regime-adaptive scoring
  2. MMS (Mastermind Mean-Reversion) — band-based mean reversion with sequentiality

Each strategy takes candles + indicators and returns (score, direction, components, tp, sl, confidence).
"""
from typing import Dict, List, Optional, Tuple, Any
from models import Signal, SignalDirection, Component, ComponentType
from indicators import TechnicalIndicators
import database as db

# ──────────────────────────────────────────────────────────────────────
# Strategy registry
# ──────────────────────────────────────────────────────────────────────

STRATEGIES: Dict[str, "BaseStrategy"] = {}


def get_strategy(name: str) -> "BaseStrategy":
    return STRATEGIES.get(name, STRATEGIES["adaptive_regime"])


def list_strategies() -> List[Dict[str, str]]:
    return [{"id": k, "name": v.display_name, "description": v.description} for k, v in STRATEGIES.items()]


# ──────────────────────────────────────────────────────────────────────
# Base class
# ──────────────────────────────────────────────────────────────────────

class BaseStrategy:
    id: str = ""
    display_name: str = ""
    description: str = ""

    def score(
        self,
        candles: List[Dict],
        indicators: Dict,
        symbol: str,
        instrument_info: Dict,
        current_price: float,
        htf_bias: float = 0.0,
        news_score: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Returns dict with keys:
          score, direction, components, confidence, take_profit, stop_loss,
          risk_reward_ratio, technical_score
        """
        raise NotImplementedError


# ──────────────────────────────────────────────────────────────────────
# Strategy 1: Adaptive Regime (original)
# ──────────────────────────────────────────────────────────────────────

class AdaptiveRegimeStrategy(BaseStrategy):
    id = "adaptive_regime"
    display_name = "Adaptive Regime"
    description = "Multi-factor regime-adaptive scoring with ADX-based trending/ranging detection"

    def score(self, candles, indicators, symbol, instrument_info, current_price,
              htf_bias=0.0, news_score=0.0):
        components = []
        scores = []
        weights = []

        # --- Detect market regime via ADX ---
        adx_data = indicators.get("adx")
        adx_value = adx_data["adx"] if adx_data else 20
        is_trending = adx_value > 25
        regime = "TRENDING" if is_trending else "RANGING"

        if adx_data:
            trend_dir = "UP" if adx_data["plus_di"] > adx_data["minus_di"] else "DOWN"
            components.append(Component(
                type=ComponentType.TECHNICAL, name="ADX (Trend)",
                value=max(-1, min(1, (adx_value - 25) / 25)) if trend_dir == "UP" else max(-1, min(1, -(adx_value - 25) / 25)),
                description=f"ADX {adx_value:.0f} ({regime}, {trend_dir}) +DI:{adx_data['plus_di']:.0f} -DI:{adx_data['minus_di']:.0f}",
                confidence=0.8 if adx_value > 30 else 0.5, indicators=adx_data
            ))

        # --- RSI ---
        if indicators.get("rsi_14") is not None:
            rsi = indicators["rsi_14"]
            if rsi < 30:
                rsi_score = (30 - rsi) / 30
            elif rsi > 70:
                rsi_score = -((rsi - 70) / 30)
            elif rsi < 45:
                rsi_score = (45 - rsi) / 45 * 0.3
            elif rsi > 55:
                rsi_score = -(rsi - 55) / 45 * 0.3
            else:
                rsi_score = 0
            rsi_score = max(-1, min(1, rsi_score))
            zone = "OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else "NEUTRAL"
            rsi_weight = 0.15 if is_trending else 0.25
            components.append(Component(
                type=ComponentType.TECHNICAL, name="RSI (14)", value=rsi_score,
                description=f"RSI {rsi:.1f} ({zone})",
                confidence=0.85 if abs(rsi - 50) > 20 else 0.5,
                indicators={"value": rsi, "zone": zone}
            ))
            scores.append(rsi_score)
            weights.append(rsi_weight)

        # --- StochRSI ---
        stoch = indicators.get("stoch_rsi")
        if stoch:
            k, d = stoch["k"], stoch["d"]
            if k < 20:
                stoch_score = 0.6 + (20 - k) / 50
            elif k > 80:
                stoch_score = -(0.6 + (k - 80) / 50)
            else:
                stoch_score = 0
            if k > d and k < 30:
                stoch_score = max(stoch_score, 0.5)
            elif k < d and k > 70:
                stoch_score = min(stoch_score, -0.5)
            stoch_score = max(-1, min(1, stoch_score))
            if abs(stoch_score) > 0.1:
                components.append(Component(
                    type=ComponentType.TECHNICAL, name="StochRSI", value=stoch_score,
                    description=f"StochRSI K:{k:.0f} D:{d:.0f}",
                    confidence=0.7 if abs(k - 50) > 30 else 0.4, indicators=stoch
                ))
                scores.append(stoch_score)
                weights.append(0.10)

        # --- MACD ---
        if indicators.get("macd"):
            macd = indicators["macd"]
            if macd.get("histogram") is not None and macd.get("macd_line") is not None:
                histogram = macd["histogram"]
                macd_line = macd["macd_line"]
                signal_line = macd.get("signal_line", 0) or 0
                atr = indicators.get("atr_14", 1) or 1
                norm_hist = histogram / atr
                macd_score = max(-1, min(1, norm_hist * 2))
                cross = "BULLISH" if macd_line > signal_line else "BEARISH"
                macd_weight = 0.25 if is_trending else 0.15
                components.append(Component(
                    type=ComponentType.TECHNICAL, name="MACD", value=macd_score,
                    description=f"MACD {cross} | hist/ATR: {norm_hist:.2f}",
                    confidence=0.8 if abs(norm_hist) > 0.5 else 0.5, indicators=macd
                ))
                scores.append(macd_score)
                weights.append(macd_weight)

        # --- Bollinger Bands ---
        if indicators.get("bollinger_bands"):
            bb = indicators["bollinger_bands"]
            closes = indicators.get("_closes", [])
            if closes:
                cp = closes[-1]
                bb_range = bb["upper"] - bb["lower"] if bb["upper"] != bb["lower"] else 1
                bb_position = ((cp - bb["lower"]) / bb_range) * 2 - 1
                bb_score = -bb_position * 0.8
                zone = "UPPER" if cp > bb["upper"] else "LOWER" if cp < bb["lower"] else "MIDDLE"
                bb_weight = 0.15 if is_trending else 0.25
                components.append(Component(
                    type=ComponentType.TECHNICAL, name="Bollinger Bands",
                    value=max(-1, min(1, bb_score)),
                    description=f"BB {zone} (pos: {bb_position:.2f})",
                    confidence=0.75 if abs(bb_position) > 0.8 else 0.4,
                    indicators={"position": bb_position, "zone": zone}
                ))
                scores.append(max(-1, min(1, bb_score)))
                weights.append(bb_weight)

        # --- SMA Trend ---
        if indicators.get("sma_20") is not None and indicators.get("sma_50") is not None:
            sma_20 = indicators["sma_20"]
            sma_50 = indicators["sma_50"]
            if sma_50 > 0:
                sma_diff_pct = ((sma_20 - sma_50) / sma_50) * 100
                sma_score = max(-1, min(1, sma_diff_pct / 2))
                trend = "BULLISH" if sma_20 > sma_50 else "BEARISH"
                sma_weight = 0.20 if is_trending else 0.10
                components.append(Component(
                    type=ComponentType.TECHNICAL, name="SMA Cross (20/50)", value=sma_score,
                    description=f"SMA20/50: {sma_diff_pct:.2f}% ({trend})",
                    confidence=0.7, indicators={"sma_20": sma_20, "sma_50": sma_50, "trend": trend}
                ))
                scores.append(sma_score)
                weights.append(sma_weight)

        # --- Volume ---
        vol = indicators.get("volume_profile")
        if vol and vol["vol_ratio"] > 1.5:
            vol_bias = max(-0.5, min(0.5, (vol["up_down_ratio"] - 1.0) * 0.3))
            components.append(Component(
                type=ComponentType.TECHNICAL, name="Volume", value=vol_bias,
                description=f"Vol {vol['vol_ratio']:.1f}x avg | Up/Down: {vol['up_down_ratio']:.1f}",
                confidence=0.6, indicators=vol
            ))
            scores.append(vol_bias)
            weights.append(0.10)

        # --- Momentum ---
        if indicators.get("momentum_10") is not None:
            momentum = indicators["momentum_10"]
            base_price = indicators.get("sma_20", 1) or 1
            mom_pct = (momentum / base_price) * 100 if base_price else 0
            momentum_score = max(-1, min(1, mom_pct / 2))
            components.append(Component(
                type=ComponentType.TECHNICAL, name="Momentum (10)", value=momentum_score,
                description=f"Momentum: {mom_pct:.2f}%",
                confidence=0.6, indicators={"value": momentum, "pct": mom_pct}
            ))
            scores.append(momentum_score)
            weights.append(0.05)

        # --- Candlestick Patterns ---
        cp_data = indicators.get("candlestick_patterns")
        if cp_data and cp_data.get("patterns") and abs(cp_data["net_bias"]) > 0.1:
            pattern_names = ", ".join(p["name"] for p in cp_data["patterns"])
            cp_score = max(-1, min(1, cp_data["net_bias"]))
            components.append(Component(
                type=ComponentType.TECHNICAL, name="Candlestick Patterns", value=cp_score,
                description=f"Patterns: {pattern_names} (bias: {cp_data['net_bias']:.2f})",
                confidence=0.7, indicators={"patterns": [p["name"] for p in cp_data["patterns"]], "net_bias": cp_data["net_bias"]}
            ))
            scores.append(cp_score)
            weights.append(0.15)

        # --- Composite ---
        if scores:
            total_weight = sum(weights)
            technical_score = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0
        else:
            technical_score = 0

        # Agreement bonus/penalty
        if len(scores) >= 3:
            bullish = sum(1 for s in scores if s > 0.1)
            bearish = sum(1 for s in scores if s < -0.1)
            agreement = max(bullish, bearish) / len(scores)
            if agreement > 0.7:
                technical_score *= 1.15
            elif agreement < 0.4:
                technical_score *= 0.7

        technical_score = max(-1, min(1, technical_score))

        # Blend with news + HTF
        effective_news = news_score if abs(news_score) > 0.1 else 0.0
        if effective_news != 0:
            final_score = technical_score * 0.80 + effective_news * 0.10 + htf_bias * 0.10
        elif abs(htf_bias) > 0.1:
            final_score = technical_score * 0.85 + htf_bias * 0.15
        else:
            final_score = technical_score
        final_score = max(-1, min(1, final_score))

        # MTF alignment filter
        if abs(htf_bias) > 0.3:
            if (final_score > 0) != (htf_bias > 0):
                final_score *= 0.5

        # Direction
        min_score = instrument_info.get("min_score", 0.15)
        strong_threshold = max(0.45, min_score + 0.20)
        if final_score > strong_threshold:
            direction = SignalDirection.STRONG_BUY
        elif final_score > min_score:
            direction = SignalDirection.BUY
        elif final_score < -strong_threshold:
            direction = SignalDirection.STRONG_SELL
        elif final_score < -min_score:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        # Minimum indicator agreement filter
        component_vals = [c.value for c in components]
        bullish_c = sum(1 for v in component_vals if v > 0.1)
        bearish_c = sum(1 for v in component_vals if v < -0.1)
        min_agreement = 3 if instrument_info.get("asset_class") == "commodity" else 2
        if direction != SignalDirection.NEUTRAL and max(bullish_c, bearish_c) < min_agreement:
            direction = SignalDirection.NEUTRAL

        # Trend alignment for commodities
        sma_50 = indicators.get("sma_50")
        if instrument_info.get("asset_class") == "commodity" and sma_50 and direction != SignalDirection.NEUTRAL:
            price_above = current_price > sma_50
            is_buy = direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY)
            if is_buy and not price_above:
                direction = SignalDirection.NEUTRAL
            elif not is_buy and price_above:
                direction = SignalDirection.NEUTRAL

        # Confidence
        if component_vals:
            bullish_count = sum(1 for v in component_vals if v > 0.1)
            bearish_count = sum(1 for v in component_vals if v < -0.1)
            total_opinionated = bullish_count + bearish_count
            agreement = max(bullish_count, bearish_count) / max(total_opinionated, 1)
            confidence = min(0.95, abs(final_score) * agreement + 0.1)
        else:
            confidence = 0.1

        # TP/SL
        atr = indicators.get("atr_14", current_price * 0.01)
        adx_trending = adx_data and adx_data["adx"] > 25 if adx_data else False
        use_trailing = instrument_info.get("trailing_stop", False)
        if use_trailing:
            sl_mult, tp_mult = 3.0, (4.0 if adx_trending else 3.5)
        elif adx_trending:
            sl_mult, tp_mult = 1.5, 3.5
        else:
            sl_mult, tp_mult = 1.5, 3.0

        if direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY):
            stop_loss = current_price - (atr * sl_mult)
            take_profit = current_price + (atr * tp_mult)
        else:
            stop_loss = current_price + (atr * sl_mult)
            take_profit = current_price - (atr * tp_mult)

        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr = reward / risk if risk > 0 else 0

        return {
            "score": final_score, "direction": direction, "components": components,
            "confidence": confidence, "take_profit": take_profit, "stop_loss": stop_loss,
            "risk_reward_ratio": rr, "technical_score": technical_score,
        }


# ──────────────────────────────────────────────────────────────────────
# Strategy 2: MMS (Mastermind Mean-Reversion Strategy)
# Based on mastermindzx.pl methodology
# ──────────────────────────────────────────────────────────────────────

# Sequentiality state: per-symbol leverage scaling after losses
# Now persisted to database - survives restarts
_mms_seq_state: Dict[str, Dict] = {}


def _get_seq_state(symbol: str) -> Dict:
    """Get sequentiality state for symbol. Loads from DB if not in memory."""
    global _mms_seq_state
    if symbol not in _mms_seq_state:
        # Try to load from database first
        db_state = db.load_mms_state(symbol)
        if db_state:
            _mms_seq_state[symbol] = db_state
        else:
            # Default state for new symbol
            _mms_seq_state[symbol] = {
                "leverage_level": 3,  # index into LEVERAGE_LADDER
                "consecutive_losses": 0,
                "in_recovery": False,
            }
            # Save default to DB
            db.save_mms_state(symbol, _mms_seq_state[symbol])
    return _mms_seq_state[symbol]


def _save_seq_state(symbol: str, state: Dict):
    """Save sequentiality state to database."""
    db.save_mms_state(symbol, state)


# Leverage ladder: index 0 = minimum, index 5 = maximum
LEVERAGE_LADDER = [0.01, 0.1, 0.25, 0.5, 1.0, 2.0]
LEVERAGE_LABELS = ["x0.01", "x0.1", "x0.25", "x0.5", "x1", "x2"]


def mms_on_trade_result(symbol: str, is_win: bool):
    """Call after a trade closes to update sequentiality state. Persists to DB."""
    state = _get_seq_state(symbol)
    if is_win:
        if state["in_recovery"]:
            # First win after loss series: jump to x0.5
            state["leverage_level"] = 3  # x0.5
            state["in_recovery"] = False
        else:
            # Normal win: step up one level (max x2)
            state["leverage_level"] = min(5, state["leverage_level"] + 1)
        state["consecutive_losses"] = 0
    else:
        state["consecutive_losses"] += 1
        state["in_recovery"] = True
        # Step down: more losses = lower leverage
        if state["consecutive_losses"] >= 4:
            state["leverage_level"] = 0  # x0.01 "scout" mode
        elif state["consecutive_losses"] >= 3:
            state["leverage_level"] = 1  # x0.1
        elif state["consecutive_losses"] >= 2:
            state["leverage_level"] = 2  # x0.25
        else:
            state["leverage_level"] = max(0, state["leverage_level"] - 2)
    
    # Persist to database
    _save_seq_state(symbol, state)


def init_mms_states_from_db():
    """Load all MMS states from database on startup."""
    global _mms_seq_state
    db_states = db.load_all_mms_states()
    for symbol, state in db_states.items():
        _mms_seq_state[symbol] = state


# Initialize on module load
init_mms_states_from_db()


class MMSStrategy(BaseStrategy):
    """
    MMS (Mastermind Mean-Reversion Strategy)

    Core idea: price tends to revert to mean after hitting statistical extremes
    measured by ATR-derivative bands (Bollinger Bands).

    Entry: Price touches upper band → SHORT (wait for reactionary candle).
           Price touches lower band → LONG (wait for reactionary candle).
    Exit:  TP at opposite band (position flip). SL at 2% price move.
    Risk:  Sequentiality system scales leverage after losses.
           Max x2 leverage, max 3% capital risk.
           NO trailing stops (empirically worse for mean reversion).

    Confirmation: Stochastic RSI for entry timing.
    """
    id = "mms"
    display_name = "MMS Mean-Reversion"
    description = "Band-based mean reversion with sequentiality risk management (mastermindzx.pl)"

    def score(self, candles, indicators, symbol, instrument_info, current_price,
              htf_bias=0.0, news_score=0.0):

        components = []
        closes = indicators.get("_closes", [c["close"] for c in candles])

        # ── 1. Bollinger Bands position (primary signal) ──
        bb = indicators.get("bollinger_bands")
        if not bb:
            return self._neutral(symbol, current_price, components)

        bb_upper = bb["upper"]
        bb_lower = bb["lower"]
        bb_middle = bb["middle"]
        bb_range = bb_upper - bb_lower if bb_upper != bb_lower else 1
        bb_position = ((current_price - bb_lower) / bb_range)  # 0..1

        # How far outside the bands (>1 = above upper, <0 = below lower)
        band_score = 0.0
        if bb_position > 0.95:
            # At or above upper band → SELL signal (mean revert down)
            band_score = -min(1.0, (bb_position - 0.5) * 2)
        elif bb_position < 0.05:
            # At or below lower band → BUY signal (mean revert up)
            band_score = min(1.0, (0.5 - bb_position) * 2)
        elif bb_position > 0.75:
            # Approaching upper → mild sell bias
            band_score = -((bb_position - 0.5) * 1.2)
        elif bb_position < 0.25:
            # Approaching lower → mild buy bias
            band_score = (0.5 - bb_position) * 1.2
        else:
            # Middle zone → no signal (wait for extremes)
            band_score = 0.0

        band_score = max(-1, min(1, band_score))
        band_zone = "UPPER" if bb_position > 0.8 else "LOWER" if bb_position < 0.2 else "MIDDLE"

        components.append(Component(
            type=ComponentType.TECHNICAL, name="BB Position (MMS)",
            value=band_score,
            description=f"BB pos: {bb_position:.2f} ({band_zone}) — {'SELL zone' if band_score < -0.3 else 'BUY zone' if band_score > 0.3 else 'WAIT zone'}",
            confidence=0.9 if abs(band_score) > 0.5 else 0.4,
            indicators={"bb_position": bb_position, "zone": band_zone}
        ))

        # ── 2. Reactionary candle confirmation ──
        # After touching band, we need a candle in the opposite direction
        react_score = 0.0
        if len(candles) >= 2:
            last = candles[-1]
            prev = candles[-2]
            last_body = last["close"] - last["open"]
            prev_body = prev["close"] - prev["open"]

            if band_score < -0.3 and last_body < 0:
                # Upper band hit + bearish candle = confirmed SHORT
                react_score = -0.6
            elif band_score > 0.3 and last_body > 0:
                # Lower band hit + bullish candle = confirmed LONG
                react_score = 0.6
            elif band_score < -0.3 and last_body > 0:
                # Upper band but candle still bullish = wait
                react_score = -0.1
            elif band_score > 0.3 and last_body < 0:
                # Lower band but candle still bearish = wait
                react_score = 0.1

        react_score = max(-1, min(1, react_score))
        if abs(react_score) > 0.05:
            components.append(Component(
                type=ComponentType.TECHNICAL, name="Reactionary Candle",
                value=react_score,
                description=f"{'Confirmed' if abs(react_score) > 0.3 else 'Waiting'} — candle {'bearish' if react_score < 0 else 'bullish'}",
                confidence=0.8 if abs(react_score) > 0.3 else 0.3,
                indicators={}
            ))

        # ── 3. Stochastic RSI confirmation ──
        stoch = indicators.get("stoch_rsi")
        stoch_score = 0.0
        if stoch:
            k, d = stoch["k"], stoch["d"]
            if k > 80 and band_score < -0.2:
                stoch_score = -0.5  # Overbought confirms sell
            elif k < 20 and band_score > 0.2:
                stoch_score = 0.5   # Oversold confirms buy
            elif k > 70:
                stoch_score = -0.2
            elif k < 30:
                stoch_score = 0.2

            stoch_score = max(-1, min(1, stoch_score))
            if abs(stoch_score) > 0.1:
                components.append(Component(
                    type=ComponentType.TECHNICAL, name="StochRSI (MMS)",
                    value=stoch_score,
                    description=f"StochRSI K:{k:.0f} D:{d:.0f} — {'overbought' if k > 70 else 'oversold' if k < 30 else 'neutral'}",
                    confidence=0.7 if abs(k - 50) > 25 else 0.4,
                    indicators=stoch
                ))

        # ── 4. Distance from middle band (mean) ──
        # Stronger signal when further from mean
        dist_from_mean = (current_price - bb_middle) / bb_range if bb_range > 0 else 0
        mean_rev_score = -dist_from_mean * 0.8  # Further from mean = stronger reversion signal
        mean_rev_score = max(-1, min(1, mean_rev_score))

        if abs(mean_rev_score) > 0.15:
            components.append(Component(
                type=ComponentType.TECHNICAL, name="Mean Distance",
                value=mean_rev_score,
                description=f"Distance from mean: {dist_from_mean:.2f} BB widths",
                confidence=0.6, indicators={"distance": dist_from_mean}
            ))

        # ── 5. ATR relative to price (volatility check) ──
        atr = indicators.get("atr_14", current_price * 0.01) or current_price * 0.01
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

        # MMS works best in volatile markets — weak signal if ATR too low
        vol_factor = min(1.5, max(0.3, atr_pct / 1.0))  # normalize around 1% ATR

        # ── Composite score ──
        # Weights: BB position (40%), reaction (25%), stoch (15%), mean distance (20%)
        raw_score = (
            band_score * 0.40
            + react_score * 0.25
            + stoch_score * 0.15
            + mean_rev_score * 0.20
        )

        # Apply volatility factor (more volatile = stronger signal)
        raw_score *= vol_factor
        technical_score = max(-1, min(1, raw_score))

        # ── Sequentiality leverage adjustment ──
        seq_state = _get_seq_state(symbol)
        lev_level = seq_state["leverage_level"]
        lev_mult = LEVERAGE_LADDER[lev_level]
        lev_label = LEVERAGE_LABELS[lev_level]

        components.append(Component(
            type=ComponentType.TECHNICAL, name="Sequentiality",
            value=0.0,
            description=f"Leverage: {lev_label} | Losses: {seq_state['consecutive_losses']} | {'Recovery' if seq_state['in_recovery'] else 'Normal'}",
            confidence=1.0, indicators={"leverage": lev_mult, "level": lev_level}
        ))

        # ── Direction thresholds ──
        # MMS uses tighter thresholds — band proximity is the trigger
        min_score = 0.20
        if abs(technical_score) > 0.50:
            direction = SignalDirection.STRONG_BUY if technical_score > 0 else SignalDirection.STRONG_SELL
        elif abs(technical_score) > min_score:
            direction = SignalDirection.BUY if technical_score > 0 else SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        # ── Confidence ──
        component_vals = [c.value for c in components if c.name != "Sequentiality"]
        if component_vals:
            same_dir = sum(1 for v in component_vals if (v > 0.1) == (technical_score > 0) and abs(v) > 0.1)
            confidence = min(0.95, abs(technical_score) * (same_dir / max(len(component_vals), 1)) + 0.1)
        else:
            confidence = 0.1

        # ── TP / SL (MMS-specific) ──
        # TP: opposite band (position flip point)
        # SL: 2% of price (fixed, no trailing)
        sl_pct = 0.02  # 2% stop loss (MMS rule)

        if direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY):
            take_profit = bb_upper  # TP at upper band
            stop_loss = current_price * (1 - sl_pct)
        elif direction in (SignalDirection.SELL, SignalDirection.STRONG_SELL):
            take_profit = bb_lower  # TP at lower band
            stop_loss = current_price * (1 + sl_pct)
        else:
            take_profit = bb_upper
            stop_loss = current_price * (1 - sl_pct)

        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr = reward / risk if risk > 0 else 0

        return {
            "score": technical_score, "direction": direction, "components": components,
            "confidence": confidence, "take_profit": take_profit, "stop_loss": stop_loss,
            "risk_reward_ratio": rr, "technical_score": technical_score,
            "mms_leverage": lev_mult, "mms_leverage_label": lev_label,
        }

    def _neutral(self, symbol, current_price, components):
        return {
            "score": 0.0, "direction": SignalDirection.NEUTRAL, "components": components,
            "confidence": 0.0, "take_profit": 0.0, "stop_loss": 0.0,
            "risk_reward_ratio": 0.0, "technical_score": 0.0,
        }


# ──────────────────────────────────────────────────────────────────────
# Register strategies
# ──────────────────────────────────────────────────────────────────────

_adaptive = AdaptiveRegimeStrategy()
_mms = MMSStrategy()
STRATEGIES[_adaptive.id] = _adaptive
STRATEGIES[_mms.id] = _mms
