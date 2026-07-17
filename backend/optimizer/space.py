"""Parameter space: maps Optuna trials onto strategy configs.

The searchable surface is exactly the extended strategies.json schema:
per-timeframe indicator weights, min_score, agreement, and exit percents.
A cardinality cap keeps the optimizer from lighting up every indicator at
once (overfit guard)."""

import copy

# indicators the optimizer may weight per timeframe
CATALOG = ["RSI", "RSI_REVERSION", "MACD", "MOMENTUM", "ADX", "STOCH", "SMA_CROSS", "BB_POSITION", "DIVERGENCE"]
MAX_ACTIVE_INDICATORS = 6  # across all timeframes


def suggest_config(trial, base_config: dict) -> dict:
    """Produce a candidate config by mutating a copy of `base_config`."""
    cfg = copy.deepcopy(base_config)
    cfg.pop("enabled", None)

    tfs = cfg.get("timeframes")
    if not tfs:  # legacy config: normalize first
        from strategy.engine import normalize_strategy_config

        cfg = normalize_strategy_config(cfg)
        tfs = cfg["timeframes"]

    active = 0
    for tf_name, block in tfs.items():
        if block.get("role") == "veto":
            continue
        new_indicators = []
        for ind in CATALOG:
            w = trial.suggest_float(f"w_{tf_name}_{ind}", 0.0, 3.0, step=0.25)
            if w > 0 and active < MAX_ACTIVE_INDICATORS:
                new_indicators.append({"name": ind, "weight": w})
                active += 1
        if new_indicators:
            block["indicators"] = new_indicators
        else:
            # all weights suggested 0: turn the TF off EXPLICITLY - silently
            # keeping the base indicators would teach the sampler a corrupted
            # mapping around the w=0 region
            block["weight"] = 0.0
            block["indicators"] = []

    combine = cfg.setdefault("combine", {})
    combine["min_score"] = trial.suggest_float("min_score", 0.05, 0.5, step=0.05)
    if len([b for b in tfs.values() if b.get("role") != "veto"]) > 1:
        combine["min_agreement"] = trial.suggest_float("min_agreement", 0.4, 1.0, step=0.1)
        combine["conflict_policy"] = trial.suggest_categorical("conflict_policy", ["dampen", "veto"])

    # if every scoring TF ended up empty the config is untradeable - prune the trial
    if not any(b.get("indicators") for b in tfs.values() if b.get("role") != "veto"):
        import optuna

        raise optuna.TrialPruned()

    exits = cfg.setdefault("exits", {})
    exits.setdefault("stop_loss", {})["value"] = trial.suggest_float("sl_pct", -4.0, -0.5, step=0.25)
    tp = trial.suggest_float("tp_pct", 0.5, 8.0, step=0.25)
    exits.setdefault("take_profit", {})["value"] = tp
    # dynamic TP overrides take_profit.value when enabled, making tp_pct a dead
    # parameter - the optimizer explores static TP only
    exits["dynamic_tp"] = {"enabled": False}
    exits.setdefault("take_profit", {})["value"] = tp
    # hold time is part of exit design - 2h..24h in 5m bars, scaled by base TF
    exits["max_hold_bars"] = trial.suggest_int("max_hold_bars", 24, 288, step=24)

    risk = cfg.setdefault("risk", {})
    risk["leverage"] = min(trial.suggest_float("leverage", 1.0, 10.0, step=1.0),
                           10.0)  # optimizer never explores past 10x
    return cfg
