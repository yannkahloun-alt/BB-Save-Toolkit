from __future__ import annotations

import json
import sqlite3
import sys


def session_stats(db_path: str) -> dict[str, int]:
    con = sqlite3.connect(db_path, timeout=5)
    try:
        cur = con.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if "work_items" not in tables:
            return {"total": 0, "complete": 0}

        total = cur.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]

        # Cosmic Ray 8.7 stores completed outcomes in work_results, one row
        # per completed job. work_items itself only contains job IDs.
        if "work_results" in tables:
            complete = cur.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
        else:
            complete = 0

        return {"total": int(total), "complete": int(complete)}
    finally:
        con.close()


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    print(json.dumps(session_stats(sys.argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
