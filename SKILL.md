---
name: quant-strategy-diagnostics
description: 诊断量化策略或因子的近期表现是否恶化，并列出可验证的原因。用户提供因子/策略的周期收益，以及可选的 IC、基准收益、换手率或市场状态数据，要求检查滚动收益、回撤、IC 衰减、相对基准表现、换手变化、样本外稳定性或新旧版本差异时使用。适用于 PandaAI/Pandadata 的因子挖掘和回测结果；数据不足时只报告可计算部分和缺失字段，不给买卖建议。
license: GPL-3.0-only
compatibility: Python 3.10+ standard library; no network, database, market account, or credentials required.
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-quant-strategy-diagnostics
  repository_url: https://github.com/quantskills/skill-quant-strategy-diagnostics
  project_type: skill
  collection: quantitative-research
  category: strategy-health
  tags:
    - strategy-diagnostics
    - factor-decay
    - drawdown
    - rolling-ic
    - backtest-validation
    - regime-analysis
  platforms:
    - claude-code
    - codex
    - cursor
    - hermes
    - openclaw
  language: zh-en
  status: draft
  validation_level: runnable
  maintainer_type: community
  requires: []
  summary_zh: 检查策略或因子近期是否恶化，列出收益、IC、回撤、换手率和市场状态方面的证据。
  summary_en: Check recent strategy or factor deterioration using returns, IC, drawdown, turnover, benchmarks, and market regimes.
---

# 量化策略健康度与失效诊断

用途：在因子挖掘和回测之后，比较近期与历史或样本外窗口，定位收益恶化、因子衰减、回撤扩大和换手变化。
它提供证据和下一轮验证项，不预测下一笔交易，也不替用户决定是否停用策略。
支持 Claude Code、Codex、Cursor、Hermes 和 OpenClaw。

## 适用人群

- 在 PandaAI/Pandadata 上挖因子并做回测的研究员
- 发现实盘表现低于回测的个人量化交易者
- 需要定期检查多套策略、决定继续观察、降权或暂停的策略管理者

## 何时使用

- “这个因子过去有效，最近半年是不是衰减了？”
- “策略连续回撤，是市场风格切换还是策略真的失效？”
- “新旧回测版本哪个更稳，改善是否只是过拟合？”
- “实盘比回测差，先帮我区分信号、市场状态、数据和交易约束。”
- “每周/月给这套策略做一次健康检查。”

## 输入合同

标准 CSV 至少包含：

```text
date,strategy_return
2025-01-02,0.003
2025-01-03,-0.001
```

收益使用小数表示（0.01 = 1%），按日或其他等间隔周期排列。可选列：

- `benchmark_return`：同周期基准收益，用于超额表现
- `factor_ic`：因子或策略每期 IC
- `turnover`：周期换手率
- `regime`：用户提供的市场状态标签，如 bull、bear、sideways

如果平台导出的列名不同，先做字段映射并在报告中记录；不要默默猜测收益单位或周期。

## 工作流

1. 确认收益单位、频率、时区、样本内/样本外边界和基准定义。
2. 检查日期排序、重复日期、缺失值、收益是否可解析，以及可选指标覆盖率。
3. 运行 `python scripts/diagnose.py --input data.csv --out report/ --window 60`。
4. 对最近窗口和等长历史窗口计算累计收益、年化波动、Sharpe（无风险利率默认为 0）、胜率和最大回撤。
5. 有 `factor_ic`、`turnover`、`benchmark_return` 或 `regime` 时，补充 IC 衰减、换手变化、基准相对表现和分状态统计。
6. 把结果分为事实、诊断信号、待验证假设和数据限制。结论必须说明样本量和窗口。

## 状态定义

- `insufficient_data`：不足两个等长窗口，不能判断近期相对历史的变化。
- `normal`：在当前阈值和数据范围内没有明显恶化信号。
- `watch`：出现一个需要继续观察的信号。
- `warning`：出现两个或更多恶化信号，建议进入人工复核或降级验证。

状态是研究工作流提示，不是自动停用或交易指令。阈值是诊断起点，不能当作跨市场通用规则。

## 诊断信号

脚本会报告但不会擅自归因：

- `return_degradation`：近期累计收益或 Sharpe 低于历史窗口
- `drawdown_expansion`：近期最大回撤明显扩大
- `ic_decay`：近期平均 IC 相对历史下降（需要 `factor_ic`）
- `relative_performance_degradation`：相对基准表现变差（需要 `benchmark_return`）
- `turnover_increase`：近期换手显著升高（需要 `turnover`）
- `regime_concentration`：表现集中在少数市场状态（需要 `regime`）

每个信号都必须附带计算值、比较窗口和证据，不要把相关性写成因果关系。

## 报告结构

输出 `report.json`（事实源）、`report.txt`（阅读摘要）和 `report.html`（无外部依赖）并包含：

1. 结论先行：状态、窗口、样本量
2. 数据质量与输入口径
3. 近期窗口 vs 历史窗口指标表
4. 诊断信号及证据
5. 分基准/因子 IC/换手/市场状态结果
6. 待验证假设与下一轮数据需求
7. 限制与不构成投资建议声明

## 决策边界

- 不因一次回撤或单个 IC 数字直接宣布策略失效。
- 不把样本内结果当作样本外证据，不把总收益当作稳健性证明。
- 没有真实成交数据时，不把执行损耗归因给策略；执行问题交给执行质量分析。
- 没有市场状态标签时，不声称已完成 regime 分析。
- 不输出具体买卖方向、目标价、收益承诺或个性化投资建议。

详细公式、阈值解释和输入边界见 `references/methodology.md`。真实示例见 `examples/data/strategy_daily.csv`。
