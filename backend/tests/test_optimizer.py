"""Tests for the self-improvement loop: guards, param space, promotion state machine."""

from unittest.mock import MagicMock, patch

import pytest

from optimizer import guards
from optimizer.walkforward import make_folds


def _m(trades=40, pnl=100.0, sharpe=1.0, dd=10.0):
    return {"trades": trades, "net_pnl_usd": pnl, "sharpe": sharpe, "max_dd_pct": dd, "max_dd_usd": dd}


def test_guards_pass_healthy_candidate():
    ok, report = guards.check([_m()] * 3, [_m(trades=15, pnl=50, sharpe=0.8)] * 3, champion_val_pnl=100.0)
    assert ok, report


def test_guards_reject_few_validation_trades():
    ok, report = guards.check([_m()] * 3, [_m(trades=3)] * 3)
    assert not ok and not report["checks"]["val_trades"]


def test_guards_reject_negative_folds():
    vals = [_m(pnl=50), _m(pnl=-30), _m(pnl=-20)]
    ok, report = guards.check([_m()] * 3, vals)
    assert not ok and not report["checks"]["positive_folds"]


def test_guards_reject_sharpe_collapse():
    ok, report = guards.check([_m(sharpe=2.0)] * 3, [_m(sharpe=0.5)] * 3)
    assert not ok and not report["checks"]["sharpe_retention"]


def test_guards_reject_not_beating_champion():
    ok, report = guards.check([_m()] * 3, [_m(pnl=100)] * 3, champion_val_pnl=1000.0)
    assert not ok and not report["checks"]["beats_champion"]


def test_guards_reject_deep_drawdown():
    ok, report = guards.check([_m()] * 3, [_m(dd=40.0)] * 3)
    assert not ok and not report["checks"]["max_dd"]


def test_walkforward_no_overlap_train_validate():
    candles = [{"i": i} for i in range(30000)]
    folds = make_folds({"5m": candles}, "5m")
    assert len(folds) == 3
    for f in folds:
        train_is = {c["i"] for c in f.train["5m"]}
        val_is = {c["i"] for c in f.validate["5m"]}
        assert not train_is & val_is
        # embargo: gap between max(train) and min(validate)
        assert min(val_is) - max(train_is) >= 288


def test_space_cardinality_cap():
    import optuna

    from optimizer import space

    base = {"id": "t", "symbol": "BTC", "base_timeframe": "5m",
            "timeframes": {"5m": {"weight": 0.5, "indicators": [{"name": "RSI", "weight": 1}]},
                           "1h": {"weight": 0.5, "indicators": [{"name": "RSI", "weight": 1}]}},
            "combine": {"min_score": 0.1}}
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=1))
    counts = []
    def obj(trial):
        cfg = space.suggest_config(trial, base)
        n = sum(len(b.get("indicators", [])) for b in cfg["timeframes"].values()
                if b.get("role") != "veto")
        counts.append(n)
        from strategy.engine import SignalEngine
        SignalEngine(cfg)  # must stay valid
        return 0.0
    study.optimize(obj, n_trials=20)
    assert max(counts) <= space.MAX_ACTIVE_INDICATORS + 2  # base fallback blocks allowed


def test_promote_blocked_when_disabled():
    from optimizer import promote as promo

    with patch.object(promo, "auto_promote_enabled", return_value=False), \
         patch.object(promo, "_audit") as audit:
        out = promo.promote("sid", {"id": "sid"}, {"passed": True})
    assert out is None
    audit.assert_called_once()


def test_promote_writes_version_and_json(tmp_path):
    from optimizer import promote as promo

    fake_json = tmp_path / "strategies.json"
    fake_json.write_text('{"strategies": [{"id": "sid", "symbol": "BTC"}]}')
    mongo = MagicMock()
    mongo.strategy_versions.find_one.return_value = {"version": 3}
    with patch.object(promo, "STRATEGIES_JSON", fake_json), \
         patch.object(promo, "_mongo", return_value=mongo), \
         patch.object(promo, "auto_promote_enabled", return_value=True):
        doc = promo.promote("sid", {"symbol": "BTC", "combine": {"min_score": 0.3}}, {"ok": 1})
    assert doc["version"] == 4 and doc["status"] == "active"
    mongo.strategy_versions.update_many.assert_called_once()  # retired previous active
    import json

    data = json.loads(fake_json.read_text())
    assert data["strategies"][0]["combine"]["min_score"] == 0.3
    mongo.config_audit.insert_one.assert_called_once()


def test_rollback_restores_previous(tmp_path):
    from optimizer import promote as promo

    fake_json = tmp_path / "strategies.json"
    fake_json.write_text('{"strategies": []}')
    mongo = MagicMock()
    mongo.strategy_versions.find_one.side_effect = [
        {"_id": 1, "strategy_id": "sid", "version": 4, "status": "active"},
        {"_id": 2, "strategy_id": "sid", "version": 3, "status": "retired",
         "config": {"symbol": "BTC", "combine": {"min_score": 0.2}}},
    ]
    with patch.object(promo, "STRATEGIES_JSON", fake_json), \
         patch.object(promo, "_mongo", return_value=mongo):
        prev = promo.rollback("sid")
    assert prev["version"] == 3
    import json

    assert json.loads(fake_json.read_text())["strategies"][0]["combine"]["min_score"] == 0.2
