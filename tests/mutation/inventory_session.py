from __future__ import annotations

import json
import re
import sqlite3
import sys

_PATH_RE = re.compile(r"(bbtool(?:/[A-Za-z0-9_]+)+\.py)")


def _searchable_text(value: object) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
    else:
        text = str(value)
    # Handle plain Windows paths and JSON-escaped Windows paths.
    return text.replace("\\\\", "/").replace("\\", "/")


def module_counts(db_path: str) -> dict[str, int]:
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
            return {}

        info = list(cur.execute("PRAGMA table_info(work_items)"))
        columns = [row[1] for row in info]
        lowered = {name.lower(): name for name in columns}

        direct = next(
            (
                lowered[name]
                for name in ("module_path", "module-path", "path", "module")
                if name in lowered
            ),
            None,
        )

        counts: dict[str, int] = {}
        if direct is not None:
            query = f'SELECT "{direct}", COUNT(*) FROM work_items GROUP BY "{direct}"'
            for raw, count in cur.execute(query):
                if raw is None:
                    continue
                text = _searchable_text(raw)
                match = _PATH_RE.search(text)
                if match:
                    path = match.group(1)
                    counts[path] = counts.get(path, 0) + int(count)
            if counts:
                return counts

        # Schema-tolerant fallback for Cosmic Ray releases that serialize the
        # module path inside a generic payload/work-item field.
        for row in cur.execute("SELECT * FROM work_items"):
            module_path = None
            for value in row:
                if value is None:
                    continue
                match = _PATH_RE.search(_searchable_text(value))
                if match:
                    module_path = match.group(1)
                    break
            if module_path:
                counts[module_path] = counts.get(module_path, 0) + 1

        return counts
    finally:
        con.close()


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    print(json.dumps({"modules": module_counts(sys.argv[1])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
