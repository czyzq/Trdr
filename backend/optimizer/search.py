"""Optuna TPE walk-forward search for one (strategy, symbol)."""

import json
import hashlib
from typing import Dict, Optional

import optuna

from backtest.costs import CostModel
from backtest.engine import run_backtest
from optimizer import guards, space
from optimizer.walkforward import make_folds

optuna.logging.set_verbosity(optuna.logging.WARNING)

SEED = 42
N_TRIALS = 75


def _config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _run_folds(cfg: dict, folds, which: str) -> list:
    metrics = []
    cm = CostModel(cfg.get("symbol", "?"))
    for fold in folds:
        data = fold.train if which == "train" else fold.validate
        try:
            report = run_backtest(cfg, data, cost_model=cm)
            metrics.append(report.metrics)
        except ValueError:
            metrics.append({"trades": 0, "net_pnl_usd": 0.0, "sharpe": 0.0, "max_dd_pct": 0.0,
                            "max_dd_usd": 0.0})
    return metrics


def optimize_strategy(base_config: dict, candles_by_tf: Dict[str, list],
                      n_trials: int = N_TRIALS, champion_config: Optional[dict] = None,
                      progress_cb=None) -> dict:
    """Walk-forward TPE search. Selection = mean VALIDATION net PnL across folds.
    Returns {best_config, guard_report, passed, study_summary}."""
    from strategy.engine import normalize_strategy_config

    base_tf = normalize_strategy_config(dict(base_config))["base_timeframe"]
    folds = make_folds(candles_by_tf, base_tf)
    if not folds:
        return {"passed": False, "error": "not enough history for a single fold"}

    trial_log = []

    def objective(trial):
        cfg = space.suggest_config(trial, base_config)
        val_metrics = _run_folds(cfg, folds, "validate")
        val_pnl = sum(m.get("net_pnl_usd", 0) for m in val_metrics)
        # sample-size prior: too few trades scores poorly
        if any(m.get("trades", 0) < guards.MIN_VAL_TRADES for m in val_metrics):
            val_pnl -= abs(val_pnl) * 0.5 + 100
        trial_log.append({"number": trial.number, "value": round(val_pnl, 2),
                          "config_hash": _config_hash(cfg)})
        if progress_cb:
            progress_cb(trial.number, n_trials, val_pnl)
        trial.set_user_attr("config", cfg)
        return val_pnl

    sampler = optuna.samplers.TPESampler(seed=SEED)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_cfg = study.best_trial.user_attrs["config"]

    # final evaluation of the winner: train metrics + validation metrics + guards
    train_metrics = _run_folds(best_cfg, folds, "train")
    val_metrics = _run_folds(best_cfg, folds, "validate")
    champion_val_pnl = None
    if champion_config is not None:
        champ_val = _run_folds(champion_config, folds, "validate")
        champion_val_pnl = sum(m.get("net_pnl_usd", 0) for m in champ_val)

    passed, guard_report = guards.check(train_metrics, val_metrics, champion_val_pnl)
    return {
        "passed": passed,
        "best_config": best_cfg,
        "config_hash": _config_hash(best_cfg),
        "guard_report": guard_report,
        "champion_val_pnl": champion_val_pnl,
        "best_value": round(study.best_value, 2),
        "n_trials": n_trials,
        "trials": trial_log[-20:],
    }
