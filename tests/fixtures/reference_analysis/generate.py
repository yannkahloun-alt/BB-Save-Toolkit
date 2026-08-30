"""Regenerate the public, synthetic reference-analysis JSON fixture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bbtool.app.analysis import analyze_brothers
from bbtool.app.config import load_config
from bbtool.app.output import _decorate_fit_rows, _public_bro_dict
from bbtool.models import Brother, STATS

OUT = Path(__file__).resolve().parent
FILES = {
    "roster": "reference-roster.json",
    "recruits": "reference-recruits.json",
    "role_fit": "reference-role-fit.json",
    "classification": "reference-classification.json",
    "archetypes": "reference-archetypes.json",
    "classification_config": "reference-classification-config.json",
}


def _brother(name: str, offset: int, **values) -> Brother:
    data = {
        "Name": name, "Title": "", "Level": 11, "XP": 15000,
        "PerkPoints": 0, "PerksUsed": 10, "LevelPoints": 0, "AP": 9,
        "HP": 70, "Fatigue": 100, "Resolve": 40, "Initiative": 90,
        "MAtk": 65, "RAtk": 45, "MDef": 10, "RDef": 8,
        "BackgroundID": "SYNTHETIC", "Background": "Synthetic Fixture",
        "PerkIDs": [], "Perks": [], "TraitIDs": [], "Traits": [],
        "Injuries": [], "HumanOffset": offset, "CurrentRolls": {},
        "FutureRolls": {},
    }
    for stat in STATS:
        data[f"{stat}Stars"] = 0
    data.update(values)
    return Brother(**data)


def _payloads() -> dict[str, object]:
    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    bros = [
        _brother("Aldric", 101, HP=105, Fatigue=135, Resolve=55, MAtk=95, MDef=38,
                 Perks=["Nimble", "Berserk"]),
        _brother("Berta", 202, HP=92, Fatigue=123, Resolve=48, MAtk=88, MDef=31),
        _brother("Cem", 303, Level=8, XP=7000, HP=76, Fatigue=104,
                 Resolve=45, MAtk=77, RAtk=68, MDef=20, HPStars=2, MAtkStars=2,
                 MDefStars=2),
        _brother("Elin", 505, Level=10, XP=12000, LevelPoints=1, HP=84, Fatigue=112,
                 Resolve=48, MAtk=84, RAtk=72, MDef=25, CurrentRolls={"HP": 4, "Fatigue": 3, "Resolve": 3,
                                           "Initiative": 4, "MAtk": 3, "RAtk": 3,
                                           "MDef": 3, "RDef": 3}),
        _brother("Daria", 404, HP=54, Fatigue=82, Resolve=30, Initiative=72,
                 MAtk=52, RAtk=42, MDef=1, RDef=1),
    ]
    recruits = [
        {"Settlement": "Reference Hamlet", "Name": "Edda", "Title": "the Quick",
         "Level": 1, "Background": "Farmhand", "Traits": ["Quick"],
         "TryoutDone": True, "HireCost": 320, "DailyWage": 7},
        {"Settlement": "Reference Keep", "Name": "Falk", "Title": "", "Level": 2,
         "Background": "Militia", "Traits": [], "TryoutDone": False,
         "HireCost": 780, "DailyWage": 14},
    ]
    result = analyze_brothers(bros, cfg.roles, cfg.classification)
    _decorate_fit_rows(result.fits)
    raw_archetypes = json.loads((ROOT / "config/archetypes.json").read_text(encoding="utf-8"))
    return {
        "roster": [_public_bro_dict(bro) for bro in bros],
        "recruits": recruits,
        "role_fit": result.fits,
        "classification": result.summaries,
        "archetypes": raw_archetypes,
        "classification_config": cfg.classification,
    }


def _write(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        )


def regenerate() -> None:
    payloads = _payloads()
    for key, filename in FILES.items():
        _write(OUT / filename, payloads[key])
    manifest = {
        "schema": "bbtool.reference_analysis.v1",
        "source": "synthetic Brother and recruit records declared in generate.py",
        "purpose": "versioned public inputs for report demos and contract tests",
        "files": {
            key: {"path": filename, "sha256": hashlib.sha256((OUT / filename).read_bytes()).hexdigest()}
            for key, filename in FILES.items()
        },
    }
    _write(OUT / "manifest.json", manifest)


if __name__ == "__main__":
    regenerate()
