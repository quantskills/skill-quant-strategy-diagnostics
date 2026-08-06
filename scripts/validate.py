#!/usr/bin/env python3
"""Small regression checks for the deterministic diagnostic engine."""

import csv
import tempfile
from datetime import date, timedelta
from pathlib import Path

from diagnose import diagnose


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "strategy_return", "benchmark_return", "factor_ic", "turnover", "regime"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = []
    for index in range(120):
        good = index < 60
        rows.append({
            "date": (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
            "strategy_return": 0.002 if good else -0.002,
            "benchmark_return": 0.0005,
            "factor_ic": 0.06 if good else 0.01,
            "turnover": 0.10 if good else 0.20,
            "regime": "trend" if good else "sideways",
        })
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "data.csv"
        write_rows(path, rows)
        report = diagnose(path, 60)
        assert report["status"] == "warning", report
        codes = {item["code"] for item in report["signals"]}
        assert {"return_degradation", "ic_decay", "turnover_increase"} <= codes, codes
        assert "regimes" in report["periods"], report

        short_path = Path(directory) / "short.csv"
        write_rows(short_path, rows[:50])
        short = diagnose(short_path, 30)
        assert short["status"] == "insufficient_data", short
        assert any("matched-window" in warning for warning in short["warnings"]), short
    print("PASS: deterioration, IC decay, turnover, regime, and insufficient-data checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
