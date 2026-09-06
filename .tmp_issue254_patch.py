from pathlib import Path

path = Path("bbtool/app/static/recruitment.js")
text = path.read_text(encoding="utf-8")
old = """  function money(value) {\n    const number = Number(value);\n    return Number.isFinite(number) ? `${Math.round(number)}g` : '—';\n  }\n"""
new = """  function money(value) {\n    if (typeof value !== 'number' || !Number.isFinite(value)) return '—';\n    return `${Math.round(value)}g`;\n  }\n"""
if text.count(old) != 1:
    raise SystemExit(f"expected one money() formatter, found {text.count(old)}")
path.write_text(text.replace(old, new), encoding="utf-8")
