#!/usr/bin/env python3
"""Deterministic, offline health diagnostics for periodic strategy results."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any


OPTIONAL = ("benchmark_return", "factor_ic", "turnover", "regime")
THRESHOLDS = {
    "sharpe_drop": 0.5,
    "drawdown_widening": 0.05,
    "ic_drop": 0.02,
    "turnover_ratio": 1.5,
    "relative_return_drop": 0.05,
}


def number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_date(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d")


def metric_stats(values: list[float], periods_per_year: int = 252) -> dict[str, float | int | None]:
    if not values:
        return {"observations": 0, "cumulative_return": None, "annualized_volatility": None, "sharpe": None, "hit_rate": None, "max_drawdown": None}
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    volatility = stdev(values) * math.sqrt(periods_per_year) if len(values) > 1 else None
    sharpe = mean(values) / stdev(values) * math.sqrt(periods_per_year) if len(values) > 1 and stdev(values) > 0 else None
    return {
        "observations": len(values),
        "cumulative_return": equity - 1.0,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "hit_rate": sum(value > 0 for value in values) / len(values),
        "max_drawdown": max_drawdown,
    }


def mean_or_none(values: list[float]) -> float | None:
    return mean(values) if values else None


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        required = {"date", "strategy_return"}
        missing = sorted(required - set(fields))
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")
        rows: list[dict[str, Any]] = []
        for line_no, raw in enumerate(reader, start=2):
            try:
                date = parse_date(raw.get("date", ""))
            except ValueError:
                warnings.append(f"line {line_no}: invalid date skipped")
                continue
            strategy_return = number(raw.get("strategy_return"))
            if strategy_return is None:
                warnings.append(f"line {line_no}: invalid strategy_return skipped")
                continue
            row: dict[str, Any] = {"date": date.isoformat(), "strategy_return": strategy_return}
            for column in OPTIONAL:
                if column == "regime":
                    label = (raw.get(column) or "").strip()
                    row[column] = label or None
                else:
                    row[column] = number(raw.get(column))
            rows.append(row)
    rows.sort(key=lambda item: item["date"])
    dates = [item["date"] for item in rows]
    duplicate_count = len(dates) - len(set(dates))
    if duplicate_count:
        warnings.append(f"duplicate dates detected: {duplicate_count}")
    if any(abs(item["strategy_return"]) > 1 for item in rows):
        warnings.append("some strategy_return values exceed 100%; confirm the input is decimal returns, not percentages")
    if len(rows) < 2:
        warnings.append("fewer than two valid observations")
    return rows, warnings


def optional_values(rows: list[dict[str, Any]], column: str) -> list[float]:
    return [row[column] for row in rows if row.get(column) is not None]


def compare(rows: list[dict[str, Any]], window: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    recent = rows[-window:]
    prior = rows[-2 * window : -window] if len(rows) >= 2 * window else []
    recent_stats = metric_stats([row["strategy_return"] for row in recent])
    prior_stats = metric_stats([row["strategy_return"] for row in prior])
    periods: dict[str, Any] = {
        "window": window,
        "recent": {"start": recent[0]["date"] if recent else None, "end": recent[-1]["date"] if recent else None, "stats": recent_stats},
        "prior": {"start": prior[0]["date"] if prior else None, "end": prior[-1]["date"] if prior else None, "stats": prior_stats},
    }
    signals: list[dict[str, Any]] = []
    if not prior:
        warnings.append(f"need at least {2 * window} valid observations for a matched-window comparison")
        if not optional_values(rows, "benchmark_return"):
            warnings.append("benchmark_return is unavailable; benchmark-relative diagnosis is unavailable")
        if not optional_values(rows, "factor_ic"):
            warnings.append("factor_ic is unavailable; IC-decay diagnosis is unavailable")
        if not optional_values(rows, "turnover"):
            warnings.append("turnover is unavailable; turnover-change diagnosis is unavailable")
        if not any(row.get("regime") for row in rows):
            warnings.append("regime is unavailable; regime concentration was not tested")
        return periods, signals, warnings

    recent_sharpe = recent_stats["sharpe"]
    prior_sharpe = prior_stats["sharpe"]
    prior_return = prior_stats["cumulative_return"]
    recent_return = recent_stats["cumulative_return"]
    sharpe_drop = prior_sharpe - recent_sharpe if recent_sharpe is not None and prior_sharpe is not None else None
    return_drop = prior_return - recent_return if recent_return is not None and prior_return is not None else None
    if (sharpe_drop is not None and sharpe_drop >= THRESHOLDS["sharpe_drop"]) or (return_drop is not None and return_drop >= THRESHOLDS["relative_return_drop"]):
        signals.append({"code": "return_degradation", "evidence": {"prior_sharpe": prior_sharpe, "recent_sharpe": recent_sharpe, "sharpe_drop": sharpe_drop, "prior_cumulative_return": prior_return, "recent_cumulative_return": recent_return, "cumulative_return_drop": return_drop}})
    recent_dd = recent_stats["max_drawdown"]
    prior_dd = prior_stats["max_drawdown"]
    if recent_dd is not None and prior_dd is not None and prior_dd - recent_dd >= THRESHOLDS["drawdown_widening"]:
        signals.append({"code": "drawdown_expansion", "evidence": {"prior_max_drawdown": prior_dd, "recent_max_drawdown": recent_dd, "widening": prior_dd - recent_dd}})

    for column, code, threshold in (("factor_ic", "ic_decay", THRESHOLDS["ic_drop"]), ("turnover", "turnover_increase", None)):
        recent_values = optional_values(recent, column)
        prior_values = optional_values(prior, column)
        if not recent_values or not prior_values:
            if column == "factor_ic":
                warnings.append("factor_ic is unavailable in one or both comparison windows")
            continue
        recent_mean = mean(recent_values)
        prior_mean = mean(prior_values)
        if code == "ic_decay" and prior_mean - recent_mean >= threshold:
            signals.append({"code": code, "evidence": {"prior_mean_ic": prior_mean, "recent_mean_ic": recent_mean, "drop": prior_mean - recent_mean}})
        if code == "turnover_increase" and prior_mean > 0 and recent_mean / prior_mean >= THRESHOLDS["turnover_ratio"]:
            signals.append({"code": code, "evidence": {"prior_mean_turnover": prior_mean, "recent_mean_turnover": recent_mean, "ratio": recent_mean / prior_mean}})

    recent_benchmark = optional_values(recent, "benchmark_return")
    prior_benchmark = optional_values(prior, "benchmark_return")
    if len(recent_benchmark) == len(recent) and len(prior_benchmark) == len(prior):
        recent_excess = metric_stats([a - b for a, b in zip([r["strategy_return"] for r in recent], recent_benchmark)])["cumulative_return"]
        prior_excess = metric_stats([a - b for a, b in zip([r["strategy_return"] for r in prior], prior_benchmark)])["cumulative_return"]
        periods["benchmark_relative"] = {"recent_excess_return": recent_excess, "prior_excess_return": prior_excess}
        if recent_excess is not None and prior_excess is not None and prior_excess - recent_excess >= THRESHOLDS["relative_return_drop"]:
            signals.append({"code": "relative_performance_degradation", "evidence": {"prior_excess_return": prior_excess, "recent_excess_return": recent_excess, "drop": prior_excess - recent_excess}})
    else:
        warnings.append("benchmark_return is incomplete; benchmark-relative diagnosis is unavailable")

    regimes: dict[str, Any] = {}
    for label in sorted({row["regime"] for row in rows if row.get("regime")}):
        values = [row["strategy_return"] for row in rows if row.get("regime") == label]
        regimes[label] = metric_stats(values)
    if regimes:
        periods["regimes"] = regimes
        if len(regimes) > 1 and max(item["observations"] for item in regimes.values()) / len(rows) >= 0.7:
            signals.append({"code": "regime_concentration", "evidence": {"largest_regime_share": max(item["observations"] for item in regimes.values()) / len(rows), "regimes": list(regimes)}})
    else:
        warnings.append("regime is unavailable; regime concentration was not tested")
    return periods, signals, warnings


def diagnose(input_path: Path, window: int) -> dict[str, Any]:
    rows, warnings = load_rows(input_path)
    periods, signals, comparison_warnings = compare(rows, window)
    warnings.extend(comparison_warnings)
    status = "insufficient_data" if len(rows) < 2 * window else ("warning" if len(signals) >= 2 else "watch" if signals else "normal")
    return {
        "skill": "quant-strategy-diagnostics",
        "status": status,
        "input": {"path": str(input_path), "observations": len(rows), "start": rows[0]["date"] if rows else None, "end": rows[-1]["date"] if rows else None, "columns": ["date", "strategy_return"] + [column for column in OPTIONAL if any(row.get(column) is not None for row in rows)]},
        "periods": periods,
        "signals": signals,
        "warnings": warnings,
        "limits": ["Historical diagnostics do not prove causality or future performance.", "No buy/sell direction, target price, or investment advice is produced.", "Thresholds are screening heuristics and require market-specific review."],
    }


def render_text(report: dict[str, Any]) -> str:
    recent = report["periods"]["recent"]["stats"]
    prior = report["periods"]["prior"]["stats"]
    lines = ["# Quantitative Strategy Health Diagnostic", "", f"Status: {report['status']}", f"Observations: {report['input']['observations']}", f"Window: {report['periods']['window']}", "", "## Matched-window metrics"]
    for label, stats in (("Recent", recent), ("Prior", prior)):
        lines.append(f"- {label}: n={stats['observations']}, cumulative={stats['cumulative_return']}, sharpe={stats['sharpe']}, max_drawdown={stats['max_drawdown']}, hit_rate={stats['hit_rate']}")
    lines.extend(["", "## Signals"])
    if report["signals"]:
        lines.extend(f"- {signal['code']}: {json.dumps(signal['evidence'], ensure_ascii=False, sort_keys=True)}" for signal in report["signals"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings"])
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- none")
    lines.extend(["", "Historical diagnostics do not prove causality or future performance; this is not investment advice."])
    return "\n".join(lines) + "\n"


def format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


STATUS_LABELS = {
    "normal": "正常",
    "watch": "观察",
    "warning": "预警",
    "insufficient_data": "数据不足",
}
SIGNAL_LABELS = {
    "return_degradation": "收益恶化",
    "drawdown_expansion": "回撤扩大",
    "ic_decay": "IC 衰减",
    "relative_performance_degradation": "相对基准表现恶化",
    "turnover_increase": "换手率升高",
    "regime_concentration": "市场状态集中",
}
EVIDENCE_LABELS = {
    "prior_sharpe": "历史 Sharpe",
    "recent_sharpe": "近期 Sharpe",
    "sharpe_drop": "Sharpe 降幅",
    "prior_cumulative_return": "历史累计收益",
    "recent_cumulative_return": "近期累计收益",
    "cumulative_return_drop": "累计收益差",
    "prior_max_drawdown": "历史最大回撤",
    "recent_max_drawdown": "近期最大回撤",
    "widening": "回撤扩大幅度",
    "prior_mean_ic": "历史平均 IC",
    "recent_mean_ic": "近期平均 IC",
    "drop": "下降幅度",
    "prior_mean_turnover": "历史平均换手率",
    "recent_mean_turnover": "近期平均换手率",
    "ratio": "换手率倍数",
    "prior_excess_return": "历史超额收益",
    "recent_excess_return": "近期超额收益",
    "largest_regime_share": "最大状态占比",
    "regimes": "市场状态",
}


def warning_label(message: str) -> str:
    exact = {
        "benchmark_return is incomplete; benchmark-relative diagnosis is unavailable": "benchmark_return 不完整，无法完成相对基准诊断。",
        "benchmark_return is unavailable; benchmark-relative diagnosis is unavailable": "缺少 benchmark_return，无法完成相对基准诊断。",
        "factor_ic is unavailable in one or both comparison windows": "一个或两个对比窗口缺少 factor_ic，无法完整判断 IC 衰减。",
        "factor_ic is unavailable; IC-decay diagnosis is unavailable": "缺少 factor_ic，无法完成 IC 衰减诊断。",
        "turnover is unavailable; turnover-change diagnosis is unavailable": "缺少 turnover，无法完成换手率变化诊断。",
        "regime is unavailable; regime concentration was not tested": "缺少 regime，未进行市场状态集中度检查。",
    }
    if message in exact:
        return exact[message]
    if message.startswith("need at least "):
        return f"匹配窗口至少需要 {message.split()[3]} 条有效观测，当前无法进行近期与历史对比。"
    if message.startswith("duplicate dates detected:"):
        return message.replace("duplicate dates detected:", "发现重复日期：")
    return message


def render_evidence(evidence: dict[str, Any]) -> str:
    return "；".join(f"{EVIDENCE_LABELS.get(key, key)}：{format_value(value)}" for key, value in evidence.items())


def render_html(report: dict[str, Any]) -> str:
    status = report["status"]
    status_label = STATUS_LABELS.get(status, status)
    recent = report["periods"]["recent"]["stats"]
    prior = report["periods"]["prior"]["stats"]
    signal_rows = "".join(
        f"<tr><td><span class='signal'>{html.escape(SIGNAL_LABELS.get(item['code'], item['code']))}</span></td><td><code>{html.escape(render_evidence(item['evidence']))}</code></td></tr>"
        for item in report["signals"]
    ) or "<tr><td colspan='2' class='muted'>当前对比窗口没有检测到明显恶化信号。</td></tr>"
    warning_rows = "".join(f"<li>{html.escape(warning_label(item))}</li>" for item in report["warnings"]) or "<li class='muted'>没有数据警告。</li>"
    metric_rows = "".join(
        f"<tr><th>{label}</th><td>{format_value(recent[key])}</td><td>{format_value(prior[key])}</td></tr>"
        for label, key in (("观测数量", "observations"), ("累计收益", "cumulative_return"), ("年化波动率", "annualized_volatility"), ("Sharpe", "sharpe"), ("胜率", "hit_rate"), ("最大回撤", "max_drawdown"))
    )
    regimes = report["periods"].get("regimes", {})
    regime_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{stats['observations']}</td><td>{format_value(stats['cumulative_return'])}</td><td>{format_value(stats['max_drawdown'])}</td></tr>"
        for label, stats in regimes.items()
    )
    regime_section = ""
    if regimes:
        regime_section = f"""
        <section>
          <h2>市场状态视图</h2>
          <table><thead><tr><th>市场状态</th><th>观测数量</th><th>累计收益</th><th>最大回撤</th></tr></thead>
          <tbody>{regime_rows}</tbody></table>
        </section>
        """
    return f"""<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>量化策略健康度诊断</title>
  <style>
    :root {{ color-scheme: light; --ink:#17212b; --muted:#617080; --line:#d9e0e7; --paper:#f6f8fa; --accent:#1769aa; --warning:#a15c00; --warning-bg:#fff4df; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1040px; margin:0 auto; padding:32px 20px 48px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; border-bottom:1px solid var(--line); padding-bottom:22px; }}
    h1 {{ font-size:28px; line-height:1.2; margin:0 0 8px; letter-spacing:0; }}
    h2 {{ font-size:18px; margin:0 0 14px; letter-spacing:0; }}
    p {{ margin:4px 0; }}
    .subtitle,.muted {{ color:var(--muted); }}
    .status {{ border:1px solid #d6a24c; background:var(--warning-bg); color:var(--warning); padding:8px 14px; border-radius:6px; font-weight:700; text-transform:uppercase; white-space:nowrap; }}
    .status.normal {{ border-color:#79a987; background:#edf8f0; color:#25643a; }}
    .status.insufficient_data {{ border-color:#9aa5b1; background:#eef1f4; color:#4d5965; }}
    .cards {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:22px 0; }}
    .card {{ background:white; border:1px solid var(--line); border-radius:6px; padding:16px; }}
    .card-label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:0; }}
    .card-value {{ font-size:22px; font-weight:700; margin-top:4px; }}
    section {{ background:white; border:1px solid var(--line); border-radius:6px; padding:20px; margin-top:16px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:top; }}
    th {{ color:var(--muted); font-weight:600; font-size:13px; }}
    tr:last-child th,tr:last-child td {{ border-bottom:0; }}
    code {{ white-space:pre-wrap; word-break:break-word; color:#334e68; }}
    .signal {{ display:inline-block; padding:3px 8px; border-radius:4px; background:var(--warning-bg); color:var(--warning); font-weight:600; }}
    ul {{ margin:0; padding-left:20px; }}
    .footnote {{ color:var(--muted); font-size:13px; margin-top:22px; }}
    @media (max-width:700px) {{ main {{ padding:22px 14px 36px; }} header {{ display:block; }} .status {{ display:inline-block; margin-top:14px; }} .cards {{ grid-template-columns:1fr; }} section {{ padding:15px; overflow-x:auto; }} table {{ min-width:560px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>量化策略健康度诊断</h1><p class='subtitle'>{html.escape(report['input']['start'] or '无')} 至 {html.escape(report['input']['end'] or '无')} · {report['input']['observations']} 条有效观测</p></div>
      <div class='status {html.escape(status)}'>{html.escape(status_label)}</div>
    </header>
    <div class='cards'>
      <div class='card'><div class='card-label'>对比窗口</div><div class='card-value'>{report['periods']['window']}</div><div class='muted'>近期窗口 vs 历史窗口</div></div>
      <div class='card'><div class='card-label'>诊断信号</div><div class='card-value'>{len(report['signals'])}</div><div class='muted'>有证据支持的提示</div></div>
      <div class='card'><div class='card-label'>输入字段</div><div class='card-value'>{len(report['input']['columns'])}</div><div class='muted'>{html.escape(', '.join(report['input']['columns']))}</div></div>
    </div>
    <section><h2>近期窗口与历史窗口对比</h2><table><thead><tr><th>指标</th><th>近期</th><th>历史</th></tr></thead><tbody>{metric_rows}</tbody></table></section>
    <section><h2>诊断信号</h2><table><thead><tr><th>信号</th><th>证据</th></tr></thead><tbody>{signal_rows}</tbody></table></section>
    {regime_section}
    <section><h2>警告与数据缺口</h2><ul>{warning_rows}</ul></section>
    <p class='footnote'>历史诊断不能证明因果关系或未来表现。本报告不提供买卖方向，也不构成投资建议。</p>
  </main>
</body>
</html>
"""


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    text = render_text(report)
    (out_dir / "report.txt").write_text(text, encoding="utf-8")
    (out_dir / "report.html").write_text(render_html(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose rolling health of a quantitative strategy")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--window", type=int, default=60)
    args = parser.parse_args()
    if args.window < 2:
        parser.error("--window must be at least 2")
    try:
        report = diagnose(args.input, args.window)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    write_outputs(report, args.out)
    print(json.dumps({"status": report["status"], "observations": report["input"]["observations"], "signals": [item["code"] for item in report["signals"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
