# skill-quant-strategy-diagnostics

量化策略健康度与失效诊断：用于因子挖掘和回测之后的表现检查，帮助定位收益恶化、IC 衰减、回撤扩大和换手变化。

## 它解决什么问题

当策略收益下降、连续回撤或实盘弱于回测时，本 Skill 把“策略失效”的模糊判断拆成可核对的信号：收益和 Sharpe 是否恶化、回撤是否扩大、因子 IC 是否衰减、相对基准是否变差、换手是否异常升高，以及表现是否只集中在某种市场状态。

它不预测下一笔交易，也不提供买卖建议。

## 快速开始

```bash
python3 scripts/validate.py
python3 scripts/diagnose.py \
  --input examples/data/strategy_daily.csv \
  --out examples/output \
  --window 5
```

输入至少需要 `date,strategy_return`，收益用小数表示。可选 `benchmark_return,factor_ic,turnover,regime`。输出 `report.json`、`report.txt` 和离线 `report.html`。

## 运行时入口

- Claude Code / Codex：读取根目录 `SKILL.md`，按其中的 CSV 诊断流程执行。
- Cursor：读取 `agents/cursor-rule.mdc`，再使用同一份 `SKILL.md` 和确定性脚本。
- Hermes / OpenClaw：读取 `agents/portable-loader.md`，按需加载 `references/methodology.md`，运行 `scripts/diagnose.py`。

所有入口都使用同一份离线脚本，不需要账号、密钥或网络访问。

## 适用场景

- 因子挖掘后检查滚动 IC 和样本外稳定性
- 回测和实盘差异的第一轮诊断
- 连续回撤是否超过历史范围
- 新旧策略版本的窗口化比较
- 多市场状态下的策略健康检查

## 状态

`normal`、`watch`、`warning` 和 `insufficient_data` 只是研究提示。它们不能替代人工复核，也不代表未来收益或成本保证。

## 免责声明

本仓库仅作研究方法层面的整理，非官方、不隶属任何被研究对象，不验证任何收益声明，不构成任何投资建议。

## 目录

```text
skill-quant-strategy-diagnostics/
├── SKILL.md
├── README.md / README.en.md
├── LICENSE
├── agents/
│   ├── openai.yaml
│   ├── cursor-rule.mdc
│   └── portable-loader.md
├── scripts/
│   ├── diagnose.py
│   └── validate.py
├── references/methodology.md
├── examples/data/strategy_daily.csv
└── evals/
```

QuantSkills 社区项目，GPLv3，供研究和教育使用。
