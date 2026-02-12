from __future__ import annotations

import argparse
import json
from pathlib import Path


METRICS = ("precision_at_10", "recall_at_100", "map", "task_success_rate_pct")


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 8 no-regression quality gate for selected hybrid config.")
    parser.add_argument("--selected-json", required=True, help="Path to milestone8_selected_hybrid.json")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    selected = _read_json(Path(args.selected_json))
    baseline = selected.get("baseline_metrics") or {}

    regressions: list[str] = []
    rows: list[str] = []
    for metric in METRICS:
        candidate_val = float(selected.get(metric, 0.0) or 0.0)
        baseline_val = float(baseline.get(metric, 0.0) or 0.0)
        ok = candidate_val >= baseline_val
        if not ok:
            regressions.append(metric)
        rows.append(
            f"| {metric} | {candidate_val:.4f} | {baseline_val:.4f} | {'PASS' if ok else 'FAIL'} |"
        )

    passed = not regressions
    out_payload = {
        "passed": passed,
        "selected_config": selected.get("config"),
        "baseline_config": selected.get("baseline_config"),
        "regressions": regressions,
        "candidate_metrics": {m: float(selected.get(m, 0.0) or 0.0) for m in METRICS},
        "baseline_metrics": {m: float(baseline.get(m, 0.0) or 0.0) for m in METRICS},
    }

    out_json_path = Path(args.out_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Milestone 8 Quality Gate",
        "",
        f"- Selected config: `{selected.get('config')}`",
        f"- Baseline config: `{selected.get('baseline_config')}`",
        f"- Status: `{'PASS' if passed else 'FAIL'}`",
        "",
        "| Metric | Candidate | Baseline | Result |",
        "|---|---:|---:|---|",
        *rows,
    ]
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"wrote {out_json_path}")
    print(f"wrote {args.out_md}")

    if not passed:
        raise SystemExit(f"Quality gate failed; regressed metrics: {', '.join(regressions)}")


if __name__ == "__main__":
    main()
