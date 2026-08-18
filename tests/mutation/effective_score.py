from __future__ import annotations
import json
import re
import sys
from pathlib import Path

OUTCOME_RE = re.compile(
    r"^(?P<module>.+?) (?P<operator>core/\S+ \d+)\r?\n"
    r"worker outcome: WorkerOutcome\.\w+, test outcome: TestOutcome\.(?P<outcome>\w+)",
    re.MULTILINE,
)

def parse_report(text: str) -> tuple[int, int]:
    total = re.search(r"^total jobs:\s*(\d+)\s*$", text, re.MULTILINE)
    survived = re.search(r"^surviving mutants:\s*(\d+)", text, re.MULTILINE)
    if not total or not survived:
        raise ValueError("Could not parse Cosmic Ray text report summary.")
    return int(total.group(1)), int(survived.group(1))

def outcome_rows(text: str):
    return [m.groupdict() for m in OUTCOME_RE.finditer(text)]

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: effective_score.py <profile> <report.txt>", file=sys.stderr)
        return 2
    profile = sys.argv[1]
    report_path = Path(sys.argv[2])
    text = report_path.read_text(encoding="utf-8", errors="replace")
    total, survivors = parse_report(text)
    rows = outcome_rows(text)
    counts = {}
    for row in rows:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    print(
        "Mutation outcomes: "
        f"KILLED={counts.get('KILLED', 0)} | "
        f"SURVIVED={counts.get('SURVIVED', 0)} | "
        f"INCOMPETENT={counts.get('INCOMPETENT', 0)} | "
        f"TOTAL={total}"
    )
    incompetents = [r for r in rows if r["outcome"] == "INCOMPETENT"]
    if incompetents:
        print("INCOMPETENT mutants:")
        for row in incompetents:
            print(f"  {row['module']} {row['operator']}")
    registry_path = Path("tests/mutation/equivalent_mutants.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    equivalent = len(registry.get(profile, []))
    if equivalent:
        meaningful = max(0, survivors - equivalent)
        score = ((total - meaningful) / total * 100.0) if total else 100.0
        print(
            f"Effective mutation score: {score:.2f}% "
            f"({equivalent} reviewed equivalent, {meaningful} meaningful survivors)"
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
