# skill-quant-strategy-diagnostics

Diagnose deteriorating quantitative strategies and factors after factor mining or backtesting, using observable changes in returns, IC, drawdown, turnover, benchmarks, and market regimes.

## What it does

When returns deteriorate, drawdown expands, or live performance trails a backtest, this skill separates observable signals: rolling return and Sharpe changes, drawdown expansion, factor IC decay, benchmark-relative deterioration, turnover changes, and regime concentration.

It does not predict the next trade or provide buy/sell advice.

## Quick start

```bash
python3 scripts/validate.py
python3 scripts/diagnose.py \
  --input examples/data/strategy_daily.csv \
  --out examples/output \
  --window 5
```

The minimum input is `date,strategy_return` with decimal returns. Optional columns are `benchmark_return`, `factor_ic`, `turnover`, and `regime`. The command writes `report.json`, `report.txt`, and a self-contained offline `report.html`.

## Runtime entrypoints

- Claude Code / Codex: read the root `SKILL.md` and follow the CSV diagnostic workflow.
- Cursor: read `agents/cursor-rule.mdc`, then use the same `SKILL.md` and deterministic scripts.
- Hermes / OpenClaw: read `agents/portable-loader.md`, load `references/methodology.md` when needed, and run `scripts/diagnose.py`.

All entrypoints use the same offline script and require no account, secret, or network access.

## Use cases

- Rolling IC and out-of-sample stability after factor mining
- First-pass diagnosis of backtest/live divergence
- Checking whether a drawdown is outside the historical range
- Comparing old and new strategy versions by matched windows
- Checking strategy health across market regimes

## Boundaries

The statuses `normal`, `watch`, `warning`, and `insufficient_data` are research workflow signals, not automatic trading instructions. Results are historical diagnostics, not return guarantees or investment advice.

See `references/methodology.md` for formulas and data boundaries.

## Disclaimer

This repository is provided for research methodology only. It is unofficial, unaffiliated with any subject under analysis, does not verify return claims, and does not constitute investment advice.

QuantSkills community project, GPLv3, for research and education.
