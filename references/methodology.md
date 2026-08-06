# Methodology

## Return convention

`strategy_return` and `benchmark_return` are decimal period returns. A value of `0.01` means +1%. The script compounds returns for cumulative performance and uses the observed number of periods for annualization. The default annualization factor is 252 and should be changed in the report context when the data is not daily.

## Matched windows

The most recent `window` observations are compared with the immediately preceding `window` observations. A comparison requires at least `2 * window` valid strategy returns. If there are fewer, the report is `insufficient_data` and does not infer decay.

## Metrics

- cumulative return: `product(1 + r) - 1`
- annualized volatility: sample standard deviation × `sqrt(252)`
- Sharpe: mean / sample standard deviation × `sqrt(252)` with zero risk-free rate
- hit rate: positive-return observations / valid observations
- maximum drawdown: minimum of equity / prior running peak - 1
- excess return: strategy return minus benchmark return per period, compounded separately for the report

IC and turnover changes are descriptive differences between matched windows. The script uses warning thresholds as screening heuristics, not universal market rules:

- Sharpe decline of at least 0.5
- maximum drawdown deterioration of at least 5 percentage points
- mean IC decline of at least 0.02
- turnover increase of at least 50%
- relative cumulative return deterioration of at least 5 percentage points

## Regime analysis

When `regime` is present, rows are grouped by the supplied label. The report shows sample count and cumulative strategy return per regime. Labels are not inferred from prices, so the absence of a regime column is an explicit limitation.

## Interpretation boundary

A signal is evidence that merits investigation, not proof of a cause. Data breaks, universe changes, corporate actions, costs, execution, and regime shifts may produce similar symptoms. Confirm any action with a clean out-of-sample test and the platform's authoritative result definition.
