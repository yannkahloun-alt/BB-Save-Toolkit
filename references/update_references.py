#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path
import urllib.error
import urllib.request
import zipfile

BBEDIT_DICTIONARY_URL = (
    "https://raw.githubusercontent.com/scarglamour/bb-edit/"
    "refs/heads/master/src/renderer/js/dictionary.json"
)
BB_SCRIPTS_ZIP_URL = (
    "https://codeload.github.com/ninkjin/"
    "Battle-Brothers-Scripts/zip/refs/heads/main"
)

HERE = Path(__file__).resolve().parent
DICTIONARY_OUT = HERE / "dictionary.json"
BACKGROUNDS_OUT = HERE / "backgrounds.json"
PERK_EFFECTS_OUT = HERE / "perk_effects.json"
TRAIT_EFFECTS_OUT = HERE / "trait_effects.json"
PERMANENT_INJURY_EFFECTS_OUT = HERE / "permanent_injury_effects.json"
PERK_AUDIT_OUT = HERE / "perk_audit.json"
PERK_MODEL_PATH = HERE.parent / "config" / "perk_model.json"
DESCRIPTIONS_OUT = HERE / "descriptions.json"

SERIALIZED_LENGTH_BY_TYPE = {
    "genericWeapon": 21,
    "namedWeapon": 53,
    "genericShield": 19,
    "namedShield": 47,
    "genericArmor": 31,
    "namedArmor": 67,
    "genericHelmet": 23,
    "namedHelmet": 55,
    "auxiliary": 21,
}
ITEM_TYPES = set(SERIALIZED_LENGTH_BY_TYPE)

NAME_RE = re.compile(
    r'(?:this\.)?m\.Name\s*=\s*"((?:\\.|[^"])*)"',
    re.MULTILINE,
)
VALUE_RE = re.compile(
    r'(?:this\.)?m\.Value\s*=\s*(-?\d+(?:\.\d+)?)',
    re.MULTILINE,
)
BACKGROUND_ID_RE = re.compile(
    r'(?:this\.)?m\.ID\s*=\s*"(background\.[^"]+)"',
    re.MULTILINE,
)
HIRING_COST_RE = re.compile(
    r'(?:this\.)?m\.HiringCost\s*=\s*(-?\d+(?:\.\d+)?)',
    re.MULTILINE,
)
DAILY_COST_RE = re.compile(
    r'(?:this\.)?m\.DailyCost\s*=\s*(-?\d+(?:\.\d+)?)',
    re.MULTILINE,
)


INHERIT_RE = re.compile(
    r'this\.inherit\(\s*"([^"]+)"',
    re.MULTILINE,
)
ITEM_ID_RE = re.compile(
    r'(?:this\.)?m\.ID\s*=\s*"([^"]+)"',
    re.MULTILINE,
)

def _fmt_bytes(size: int | None) -> str:
    if size is None:
        return "?"
    units = ("B", "KiB", "MiB", "GiB")
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024.0
    return f"{size}B"


def _cache_file_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "size": 0}
    try:
        return {"exists": True, "size": path.stat().st_size}
    except OSError:
        return {"exists": True, "size": None}


def _archive_stats(archive_bytes: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = archive.infolist()
        nut_files = [
            info for info in members
            if info.filename.replace("\\", "/").endswith(".nut")
        ]
        item_scripts = [
            info for info in nut_files
            if "/scripts/items/" in info.filename.replace("\\", "/")
        ]
        background_scripts = [
            info for info in nut_files
            if "/scripts/skills/backgrounds/" in info.filename.replace("\\", "/")
        ]
        return {
            "archive_bytes": len(archive_bytes),
            "members": len(members),
            "nut_files": len(nut_files),
            "item_scripts": len(item_scripts),
            "background_scripts": len(background_scripts),
        }


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_dictionary(raw) -> dict[str, dict]:
    pairs = raw.items() if isinstance(raw, dict) else raw
    return {str(key).upper(): value for key, value in pairs}


def _slug(value: str) -> str:
    value = value.casefold().replace("–", "-").replace("—", "-")
    value = value.replace("'", "").replace("’", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def battle_brothers_save_hash(script_path: str) -> str:
    """
    Compute the 4-byte ID serialized in Battle Brothers saves.

    Battle Brothers hashes the internal script path (without .nut) using BKDR
    with multiplier 37, then serializes the uint32 little-endian. The save/tool
    representation is therefore the resulting four bytes as uppercase hex.
    """
    h = 0
    for byte in script_path.encode("ascii"):
        h = (h * 37 + byte) & 0xFFFFFFFF
    return h.to_bytes(4, "little").hex().upper()


def _compact_key(value: str) -> str:
    """Language/punctuation-tolerant key: morning_star == Morningstar."""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _stem_slug(path: str) -> str:
    stem = Path(path).stem
    for suffix in ("_background",):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return _slug(stem)


def reference_dictionary_is_present(path: Path = DICTIONARY_OUT) -> bool:
    if not path.is_file():
        return False
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(raw, dict):
        return False
    if raw.get("_meta", {}).get("format") != "bbtool.enriched_dictionary.v1":
        return False
    entries = raw.get("entries")
    if not isinstance(entries, dict) or len(entries) < 900:
        return False
    return all(
        isinstance(k, str) and len(k) == 8 and isinstance(v, dict)
        and "name" in v and "type" in v
        for k, v in entries.items()
    )


def background_dictionary_is_present(
    path: Path = BACKGROUNDS_OUT,
) -> bool:
    if not path.is_file():
        return False
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(raw, dict) or len(raw) < 50:
        return False
    return all(
        isinstance(k, str)
        and isinstance(v, dict)
        and "HiringCostBase" in v
        and "DailyCostBase" in v
        and "Script" in v
        for k, v in raw.items()
    )


def _download_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BB-Save-Toolkit/2.7"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def download_reference_dictionary(
    url: str = BBEDIT_DICTIONARY_URL,
    timeout: int = 20,
) -> dict[str, dict]:
    raw = json.loads(_download_bytes(url, timeout).decode("utf-8"))
    data = _normalize_dictionary(raw)
    if not data:
        raise ValueError("Downloaded reference dictionary is empty.")
    return data


def _unescape_squirrel_string(value: str) -> str:
    return value.replace(r'\"', '"').replace("\\\\", "\\")


def _extract_script_item_values(
    archive_bytes: bytes,
) -> dict:
    """
    Build an inheritance-aware model of vanilla item scripts.

    Important: a script does not have to assign m.Value locally. We resolve
    missing values recursively from its parent script. Multiple lookup indexes
    are returned so BB-Edit names can match filename stems even when spacing or
    punctuation differs (e.g. Morningstar <-> morning_star).
    """
    scripts = {}

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for info in archive.infolist():
            path = info.filename.replace("\\", "/")
            if "/scripts/items/" not in path or not path.endswith(".nut"):
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                continue

            rel = path.split("/", 1)[-1]
            script_path = rel[:-4] if rel.endswith(".nut") else rel
            stem = _slug(Path(path).stem)
            parent_match = INHERIT_RE.search(text)
            id_match = ITEM_ID_RE.search(text)
            name_match = NAME_RE.search(text)
            value_match = VALUE_RE.search(text)

            local_value = None
            if value_match:
                numeric = float(value_match.group(1))
                local_value = int(numeric) if numeric.is_integer() else numeric

            display_name = (
                _unescape_squirrel_string(name_match.group(1)).strip()
                if name_match else None
            )

            scripts[script_path] = {
                "Script": rel,
                "Path": script_path,
                "SaveHash": battle_brothers_save_hash(script_path),
                "Stem": stem,
                "CompactStem": _compact_key(stem),
                "Parent": parent_match.group(1) if parent_match else None,
                "ID": id_match.group(1) if id_match else None,
                "Name": display_name,
                "LocalValue": local_value,
            }

    memo = {}
    resolving = set()

    def resolve_value(path: str):
        if path in memo:
            return memo[path]
        if path in resolving:
            return None
        rec = scripts.get(path)
        if not rec:
            return None
        resolving.add(path)
        value = rec["LocalValue"]
        source = path if value is not None else None
        inherited = False
        if value is None and rec["Parent"]:
            parent_res = resolve_value(rec["Parent"])
            if parent_res is not None:
                value, source, _parent_inherited = parent_res
                inherited = True
        resolving.discard(path)
        memo[path] = None if value is None else (value, source, inherited)
        return memo[path]

    by_name = {}
    by_stem = {}
    by_compact_stem = {}
    by_id = {}
    by_save_hash = {}
    resolved = 0
    inherited = 0
    local = 0

    for path, rec in scripts.items():
        resolved_value = resolve_value(path)
        value = None
        value_script = None
        inherited_value = False
        if resolved_value:
            value, value_script, inherited_value = resolved_value
            resolved += 1
            if inherited_value:
                inherited += 1
            else:
                local += 1

        enriched = {
            "Name": rec["Name"],
            "Value": value,
            "Source": rec["Script"],
            "ValueScript": (
                scripts[value_script]["Script"]
                if value_script in scripts else value_script
            ),
            "Stem": rec["Stem"],
            "CompactStem": rec["CompactStem"],
            "ID": rec["ID"],
            "Parent": rec["Parent"],
            "InheritedValue": inherited_value,
        }

        by_stem.setdefault(rec["Stem"], []).append(enriched)
        by_compact_stem.setdefault(rec["CompactStem"], []).append(enriched)
        if rec["Name"]:
            by_name.setdefault(_slug(rec["Name"]), []).append(enriched)
        if rec["ID"]:
            by_id.setdefault(rec["ID"].casefold(), []).append(enriched)
        by_save_hash.setdefault(rec["SaveHash"], []).append(enriched)

    return {
        "scripts": scripts,
        "by_name": by_name,
        "by_stem": by_stem,
        "by_compact_stem": by_compact_stem,
        "by_id": by_id,
        "by_save_hash": by_save_hash,
        "script_count": len(scripts),
        "resolved_value_scripts": resolved,
        "local_value_scripts": local,
        "inherited_value_scripts": inherited,
        "unresolved_value_scripts": len(scripts) - resolved,
    }


def _unique_value(candidates: list[dict]) -> dict | None:
    resolved = [c for c in candidates if c.get("Value") is not None]
    if not resolved:
        return None
    values = {c["Value"] for c in resolved}
    if len(values) != 1:
        return None
    return resolved[0]


def build_reference_dictionary(
    output_path: Path = DICTIONARY_OUT,
    bbedit_dictionary: dict | None = None,
    scripts_archive: bytes | None = None,
    timeout: int = 45,
) -> dict:
    started = time.perf_counter()
    if bbedit_dictionary is None:
        bbedit_dictionary = download_reference_dictionary(timeout=min(timeout, 20))
    else:
        bbedit_dictionary = _normalize_dictionary(bbedit_dictionary)

    if scripts_archive is None:
        scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, timeout)

    archive_stats = _archive_stats(scripts_archive)
    t = time.perf_counter()
    source_model = _extract_script_item_values(scripts_archive)
    source_parse_seconds = time.perf_counter() - t
    by_save_hash = source_model["by_save_hash"]

    entries = {}
    exact_hash_matches = 0
    exact_hash_with_value = 0
    inherited_value_matches = 0
    equipment_like = 0
    with_value = 0
    unresolved = 0
    unresolved_ids = []
    type_stats = {}

    t = time.perf_counter()
    for ref_id, rec in bbedit_dictionary.items():
        typ = rec.get("type")
        name = str(rec.get("name", "") or "").strip()

        entry = {
            "name": name,
            "type": typ,
            "slot": rec.get("slot"),
            "subType": rec.get("subType"),
        }

        ts = type_stats.setdefault(str(typ), {"ids": 0, "with_value": 0, "unresolved": 0})
        ts["ids"] += 1

        if typ in ITEM_TYPES:
            equipment_like += 1
            entry.update({
                "Value": None,
                "SerializedLength": SERIALIZED_LENGTH_BY_TYPE[typ],
                "ValueSource": None,
                "Script": None,
            })

            candidates = by_save_hash.get(ref_id, [])
            chosen = _unique_value(candidates)

            if candidates:
                exact_hash_matches += 1

            if chosen and chosen.get("Value") is not None:
                entry["Value"] = chosen["Value"]
                entry["ValueSource"] = "vanilla-script-save-hash"
                entry["Script"] = chosen["Source"]
                entry["ValueScript"] = chosen.get("ValueScript")
                entry["InheritedValue"] = bool(chosen.get("InheritedValue"))
                exact_hash_with_value += 1
                if entry["InheritedValue"]:
                    inherited_value_matches += 1

            if entry["Value"] is None:
                unresolved += 1
                ts["unresolved"] += 1
                unresolved_ids.append(ref_id)
            else:
                with_value += 1
                ts["with_value"] += 1

        entries[ref_id] = entry

    join_seconds = time.perf_counter() - t
    payload = {
        "_meta": {
            "format": "bbtool.enriched_dictionary.v1",
            "ids": len(entries),
            "equipment_like": equipment_like,
            "equipment_with_value": with_value,
            "equipment_unresolved": unresolved,
            "equipment_coverage_pct": round(100.0 * with_value / equipment_like, 2) if equipment_like else 0.0,
        },
        "entries": entries,
    }

    t = time.perf_counter()
    _write_json(output_path, payload)
    write_seconds = time.perf_counter() - t

    return {
        "dictionary_ids": len(entries),
        "equipment_like": equipment_like,
        "with_value": with_value,
        "unresolved": unresolved,
        "coverage_pct": payload["_meta"]["equipment_coverage_pct"],
        "exact_hash_matches": exact_hash_matches,
        "exact_hash_with_value": exact_hash_with_value,
        "inherited_value_matches": inherited_value_matches,
        "source_scripts": source_model["script_count"],
        "source_value_resolved": source_model["resolved_value_scripts"],
        "source_value_local": source_model["local_value_scripts"],
        "source_value_inherited": source_model["inherited_value_scripts"],
        "source_value_unresolved": source_model["unresolved_value_scripts"],
        "archive": archive_stats,
        "source_parse_seconds": source_parse_seconds,
        "join_seconds": join_seconds,
        "write_seconds": write_seconds,
        "total_seconds": time.perf_counter() - started,
        "output_bytes": output_path.stat().st_size,
        "unresolved_sample": unresolved_ids[:20],
        "type_stats": type_stats,
    }



PERK_NAME_RE = re.compile(
    r'(?:this\.)?m\.Name\s*=\s*"((?:\\.|[^"])*)"',
    re.MULTILINE,
)
PERK_CONST_NAME_RE = re.compile(
    r'(?:this\.)?m\.Name\s*=\s*this\.Const\.Strings\.PerkName\.([A-Za-z_]\w*)',
    re.MULTILINE,
)
PERK_ID_RE = re.compile(
    r'(?:this\.)?m\.ID\s*=\s*"(perk\.[^"]+)"',
    re.MULTILINE,
)
TRAIT_ID_RE = re.compile(
    r'(?:this\.)?m\.ID\s*=\s*"(trait\.[^"]+)"',
    re.MULTILINE,
)
ONUPDATE_RE = re.compile(
    r'function\s+onUpdate\s*\(([^)]*)\)\s*\{',
    re.MULTILINE,
)

PERK_STAT_FIELDS = {
    "Hitpoints": "HP",
    "HitpointsMult": "HP",
    "Stamina": "Fatigue",
    "StaminaMult": "Fatigue",
    "Bravery": "Resolve",
    "BraveryMult": "Resolve",
    "Initiative": "Initiative",
    "InitiativeMult": "Initiative",
    "MeleeSkill": "MAtk",
    "MeleeSkillMult": "MAtk",
    "RangedSkill": "RAtk",
    "RangedSkillMult": "RAtk",
    "MeleeDefense": "MDef",
    "MeleeDefenseMult": "MDef",
    "RangedDefense": "RDef",
    "RangedDefenseMult": "RDef",
}


def perk_effect_dictionary_is_present(path: Path = PERK_EFFECTS_OUT) -> bool:
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(raw, dict)
        and raw.get("_meta", {}).get("format") == "bbtool.perk_effects.v2"
        and isinstance(raw.get("perks"), dict)
        and len(raw["perks"]) > 0
    )


def _brace_body(text: str, brace_pos: int) -> tuple[str, int] | None:
    if brace_pos >= len(text) or text[brace_pos] != "{":
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(brace_pos, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace_pos + 1:i], i + 1
    return None



def _display_name_from_stem(stem: str) -> str:
    words = stem.removeprefix("perk_").split("_")
    return " ".join(w.capitalize() for w in words if w)


def _numeric_property_effects(body: str, variable: str) -> list[dict]:
    """
    Parse both readable Squirrel and the repository's decompiled opcode form.

    Readable:
        _properties.HitpointsMult *= 1.25;

    Decompiled:
        _properties.HitpointsMult = _properties.HitpointsMult op42 1.25;

    In the Battle-Brothers-Scripts decompiler output, op42 is multiplication.
    """
    effects = []

    readable_re = re.compile(
        rf'\b{re.escape(variable)}\.([A-Za-z_]\w*)\s*([+\-*/])=\s*'
        r'(-?\d+(?:\.\d+)?)\s*;',
        re.MULTILINE,
    )
    decompiled_re = re.compile(
        rf'\b{re.escape(variable)}\.([A-Za-z_]\w*)\s*=\s*'
        rf'{re.escape(variable)}\.\1\s+op(\d+)\s+'
        r'(-?\d+(?:\.\d+)?)\s*;',
        re.MULTILINE,
    )

    conditional = bool(
        re.search(r'\b(if|switch|for|foreach|while)\s*\(', body)
    )

    for m in readable_re.finditer(body):
        field = m.group(1)
        stat = PERK_STAT_FIELDS.get(field)
        if stat is None:
            continue
        value = float(m.group(3))
        if value.is_integer():
            value = int(value)
        effects.append({
            "stat": stat,
            "property": field,
            "op": m.group(2) + "=",
            "value": value,
            "conditional": conditional,
            "exact": not conditional,
            "source_form": "readable",
        })

    # Known decompiler arithmetic opcode used by vanilla stat multipliers.
    OPCODE_TO_ASSIGNMENT = {
        "42": "*=",
    }
    for m in decompiled_re.finditer(body):
        field = m.group(1)
        stat = PERK_STAT_FIELDS.get(field)
        op = OPCODE_TO_ASSIGNMENT.get(m.group(2))
        if stat is None or op is None:
            continue
        value = float(m.group(3))
        if value.is_integer():
            value = int(value)
        effects.append({
            "stat": stat,
            "property": field,
            "op": op,
            "value": value,
            "conditional": conditional,
            "exact": not conditional,
            "source_form": "decompiled",
        })

    return effects


def build_perk_effect_dictionary(
    output_path: Path = PERK_EFFECTS_OUT,
    scripts_archive: bytes | None = None,
    scripts_url: str = BB_SCRIPTS_ZIP_URL,
    timeout: int = 45,
) -> dict:
    started = time.perf_counter()
    download_seconds = 0.0

    if scripts_archive is None:
        t = time.perf_counter()
        scripts_archive = _download_bytes(scripts_url, timeout)
        download_seconds = time.perf_counter() - t

    perks = {}
    scanned = 0
    decode_failures = 0
    stat_modifying = 0
    exact_stat_modifying = 0
    conditional_stat_modifying = 0

    t = time.perf_counter()
    with zipfile.ZipFile(io.BytesIO(scripts_archive)) as archive:
        for info in archive.infolist():
            path = info.filename.replace("\\", "/")
            if "/scripts/skills/perks/" not in path or not path.endswith(".nut"):
                continue

            scanned += 1
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                decode_failures += 1
                continue

            rel = path.split("/", 1)[-1]
            stem = Path(path).stem
            name_match = PERK_NAME_RE.search(text)
            const_name_match = PERK_CONST_NAME_RE.search(text)
            id_match = PERK_ID_RE.search(text)
            if name_match:
                name = _unescape_squirrel_string(name_match.group(1)).strip()
            elif const_name_match:
                name = _display_name_from_stem(stem)
            else:
                name = _display_name_from_stem(stem)
            perk_id = id_match.group(1) if id_match else None

            effects = []
            for fn in ONUPDATE_RE.finditer(text):
                params = [p.strip() for p in fn.group(1).split(",") if p.strip()]
                if not params:
                    continue
                variable = params[-1]
                body_rec = _brace_body(text, fn.end() - 1)
                if not body_rec:
                    continue
                body, _end = body_rec
                effects.extend(_numeric_property_effects(body, variable))

            exact = [x for x in effects if x["exact"]]
            conditional = [x for x in effects if x["conditional"]]
            if effects:
                stat_modifying += 1
            if exact:
                exact_stat_modifying += 1
            if conditional:
                conditional_stat_modifying += 1

            key = perk_id or name or stem
            perks[key] = {
                "ID": perk_id,
                "Name": name,
                "Script": rel,
                "Stem": stem,
                "ModifiesCoreStats": bool(effects),
                "HasExactCoreStatModifiers": bool(exact),
                "HasConditionalCoreStatModifiers": bool(conditional),
                "Effects": effects,
            }

    parse_seconds = time.perf_counter() - t
    if not perks:
        raise ValueError("Generated perk effect dictionary is empty.")

    payload = {
        "_meta": {
            "format": "bbtool.perk_effects.v2",
            "perk_scripts": scanned,
            "perks": len(perks),
            "stat_modifying": stat_modifying,
            "exact_stat_modifying": exact_stat_modifying,
            "conditional_stat_modifying": conditional_stat_modifying,
        },
        "perks": perks,
    }

    tw = time.perf_counter()
    _write_json(output_path, payload)
    write_seconds = time.perf_counter() - tw

    return {
        "perks": len(perks),
        "scanned_perk_scripts": scanned,
        "decode_failures": decode_failures,
        "stat_modifying": stat_modifying,
        "exact_stat_modifying": exact_stat_modifying,
        "conditional_stat_modifying": conditional_stat_modifying,
        "download_seconds": download_seconds,
        "parse_seconds": parse_seconds,
        "write_seconds": write_seconds,
        "total_seconds": time.perf_counter() - started,
        "output_bytes": output_path.stat().st_size,
    }




def trait_effect_dictionary_is_present(path: Path = TRAIT_EFFECTS_OUT) -> bool:
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(raw, dict)
        and raw.get("_meta", {}).get("format") == "bbtool.trait_effects.v2"
        and isinstance(raw.get("traits"), dict)
        and len(raw["traits"]) > 0
    )


def _trait_display_name(stem: str) -> str:
    words = stem.removesuffix("_trait").split("_")
    return " ".join(w.capitalize() for w in words if w)


def build_trait_effect_dictionary(
    output_path: Path = TRAIT_EFFECTS_OUT,
    scripts_archive: bytes | None = None,
    scripts_url: str = BB_SCRIPTS_ZIP_URL,
    timeout: int = 45,
) -> dict:
    """Extract permanent exact core-stat effects from vanilla trait scripts."""
    started = time.perf_counter()
    download_seconds = 0.0
    if scripts_archive is None:
        t0 = time.perf_counter()
        scripts_archive = _download_bytes(scripts_url, timeout)
        download_seconds = time.perf_counter() - t0

    traits = {}
    scanned = decode_failures = 0
    stat_modifying = exact_stat_modifying = conditional_stat_modifying = 0

    t0 = time.perf_counter()
    with zipfile.ZipFile(io.BytesIO(scripts_archive)) as archive:
        for info in archive.infolist():
            path = info.filename.replace("\\", "/")
            if "/scripts/skills/traits/" not in path or not path.endswith("_trait.nut"):
                continue
            scanned += 1
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                decode_failures += 1
                continue

            rel = path.split("/", 1)[-1]
            script_path = rel[:-4] if rel.endswith(".nut") else rel
            save_hash = battle_brothers_save_hash(script_path)
            stem = Path(path).stem
            id_match = TRAIT_ID_RE.search(text)
            trait_id = id_match.group(1) if id_match else None
            name = _trait_display_name(stem)

            effects = []
            for fn in ONUPDATE_RE.finditer(text):
                params = [p.strip() for p in fn.group(1).split(",") if p.strip()]
                if not params:
                    continue
                variable = params[-1]
                body_rec = _brace_body(text, fn.end() - 1)
                if not body_rec:
                    continue
                body, _end = body_rec
                effects.extend(_numeric_property_effects(body, variable))

            exact = [x for x in effects if x["exact"]]
            conditional = [x for x in effects if x["conditional"]]
            if effects:
                stat_modifying += 1
            if exact:
                exact_stat_modifying += 1
            if conditional:
                conditional_stat_modifying += 1

            key = save_hash
            traits[key] = {
                "SaveHash": save_hash,
                "ID": trait_id,
                "Name": name,
                "Script": rel,
                "Stem": stem,
                "ModifiesCoreStats": bool(effects),
                "HasExactCoreStatModifiers": bool(exact),
                "HasConditionalCoreStatModifiers": bool(conditional),
                "Effects": effects,
            }

    parse_seconds = time.perf_counter() - t0
    if not traits:
        raise ValueError("Generated trait effect dictionary is empty.")

    payload = {
        "_meta": {
            "format": "bbtool.trait_effects.v2",
            "trait_scripts": scanned,
            "traits": len(traits),
            "stat_modifying": stat_modifying,
            "exact_stat_modifying": exact_stat_modifying,
            "conditional_stat_modifying": conditional_stat_modifying,
        },
        "traits": traits,
    }
    tw = time.perf_counter()
    _write_json(output_path, payload)
    write_seconds = time.perf_counter() - tw
    return {
        "traits": len(traits),
        "scanned_trait_scripts": scanned,
        "decode_failures": decode_failures,
        "stat_modifying": stat_modifying,
        "exact_stat_modifying": exact_stat_modifying,
        "conditional_stat_modifying": conditional_stat_modifying,
        "download_seconds": download_seconds,
        "parse_seconds": parse_seconds,
        "write_seconds": write_seconds,
        "total_seconds": time.perf_counter() - started,
        "output_bytes": output_path.stat().st_size,
    }



def permanent_injury_effect_dictionary_is_present(
    path: Path = PERMANENT_INJURY_EFFECTS_OUT,
) -> bool:
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(raw, dict)
        and raw.get("_meta", {}).get("format") == "bbtool.permanent_injury_effects.v1"
        and isinstance(raw.get("injuries"), dict)
    )


def _reference_entries_for_effect_build() -> dict:
    for path in (DICTIONARY_OUT, HERE / "dictionary_core.json"):
        try:
            raw = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
            return raw["entries"]
        if isinstance(raw, dict):
            return raw
    return {}


def build_permanent_injury_effect_dictionary(
    output_path: Path = PERMANENT_INJURY_EFFECTS_OUT,
    scripts_archive: bytes | None = None,
    reference_entries: dict | None = None,
    scripts_url: str = BB_SCRIPTS_ZIP_URL,
    timeout: int = 45,
) -> dict:
    """Extract exact unconditional core-stat effects of vanilla permanent injuries.

    Script membership is resolved by the same save-hash used by the parser,
    avoiding assumptions about the repository's injury directory layout.
    """
    started = time.perf_counter()
    download_seconds = 0.0
    if scripts_archive is None:
        t0 = time.perf_counter()
        scripts_archive = _download_bytes(scripts_url, timeout)
        download_seconds = time.perf_counter() - t0
    entries = reference_entries if reference_entries is not None else _reference_entries_for_effect_build()

    injuries = {}
    scanned = decode_failures = stat_modifying = exact_stat_modifying = conditional_stat_modifying = 0
    t0 = time.perf_counter()
    with zipfile.ZipFile(io.BytesIO(scripts_archive)) as archive:
        for info in archive.infolist():
            path = info.filename.replace("\\", "/")
            if "/scripts/skills/" not in path or not path.endswith(".nut"):
                continue
            rel = path.split("/", 1)[-1]
            script_path = rel[:-4] if rel.endswith(".nut") else rel
            save_hash = battle_brothers_save_hash(script_path)
            ref = entries.get(save_hash, {})
            if ref.get("type") != "permanentInjury":
                continue
            scanned += 1
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                decode_failures += 1
                continue

            effects = []
            for fn in ONUPDATE_RE.finditer(text):
                params = [p.strip() for p in fn.group(1).split(",") if p.strip()]
                if not params:
                    continue
                variable = params[-1]
                body_rec = _brace_body(text, fn.end() - 1)
                if not body_rec:
                    continue
                body, _end = body_rec
                effects.extend(_numeric_property_effects(body, variable))

            exact = [x for x in effects if x["exact"]]
            conditional = [x for x in effects if x["conditional"]]
            if effects:
                stat_modifying += 1
            if exact:
                exact_stat_modifying += 1
            if conditional:
                conditional_stat_modifying += 1

            injuries[save_hash] = {
                "SaveHash": save_hash,
                "Name": ref.get("name", Path(path).stem),
                "Script": rel,
                "ModifiesCoreStats": bool(effects),
                "HasExactCoreStatModifiers": bool(exact),
                "HasConditionalCoreStatModifiers": bool(conditional),
                "Effects": effects,
            }

    parse_seconds = time.perf_counter() - t0
    payload = {
        "_meta": {
            "format": "bbtool.permanent_injury_effects.v1",
            "injury_scripts": scanned,
            "injuries": len(injuries),
            "stat_modifying": stat_modifying,
            "exact_stat_modifying": exact_stat_modifying,
            "conditional_stat_modifying": conditional_stat_modifying,
        },
        "injuries": injuries,
    }
    tw = time.perf_counter()
    _write_json(output_path, payload)
    write_seconds = time.perf_counter() - tw
    return {
        "injuries": len(injuries),
        "scanned_injury_scripts": scanned,
        "decode_failures": decode_failures,
        "stat_modifying": stat_modifying,
        "exact_stat_modifying": exact_stat_modifying,
        "conditional_stat_modifying": conditional_stat_modifying,
        "download_seconds": download_seconds,
        "parse_seconds": parse_seconds,
        "write_seconds": write_seconds,
        "total_seconds": time.perf_counter() - started,
        "output_bytes": output_path.stat().st_size,
    }


def build_background_dictionary(
    output_path: Path = BACKGROUNDS_OUT,
    scripts_archive: bytes | None = None,
    scripts_url: str = BB_SCRIPTS_ZIP_URL,
    timeout: int = 45,
) -> dict:
    """
    Build background economy refs with inheritance.

    Child scripts inherit HiringCost/DailyCost from their parent when they do
    not override them. Missing IDs are inferred from the script stem solely as
    metadata; parser lookup itself is keyed by that stem.
    """
    started = time.perf_counter()
    download_seconds = 0.0

    if scripts_archive is None:
        t = time.perf_counter()
        scripts_archive = _download_bytes(scripts_url, timeout)
        download_seconds = time.perf_counter() - t

    archive_stats = _archive_stats(scripts_archive)
    scripts = {}
    scanned_scripts = 0
    decode_failures = 0

    t = time.perf_counter()
    with zipfile.ZipFile(io.BytesIO(scripts_archive)) as archive:
        for info in archive.infolist():
            path = info.filename.replace("\\", "/")
            if "/scripts/skills/backgrounds/" not in path:
                continue
            if not path.endswith("_background.nut"):
                continue

            scanned_scripts += 1
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                decode_failures += 1
                continue

            rel = path.split("/", 1)[-1]
            script_path = rel[:-4] if rel.endswith(".nut") else rel
            parent_match = INHERIT_RE.search(text)
            id_match = BACKGROUND_ID_RE.search(text)
            hiring_match = HIRING_COST_RE.search(text)
            daily_match = DAILY_COST_RE.search(text)

            def num(match):
                if not match:
                    return None
                val = float(match.group(1))
                return int(val) if val.is_integer() else val

            scripts[script_path] = {
                "Script": rel,
                "ScriptPath": script_path,
                "SaveHash": battle_brothers_save_hash(script_path),
                "Parent": parent_match.group(1) if parent_match else None,
                "BackgroundID": id_match.group(1) if id_match else None,
                "HiringCostBase": num(hiring_match),
                "DailyCostBase": num(daily_match),
                "Key": _stem_slug(path),
            }

    parse_seconds = time.perf_counter() - t
    memo = {}
    resolving = set()

    def resolve(path: str):
        if path in memo:
            return memo[path]
        if path in resolving:
            return None
        rec = scripts.get(path)
        if not rec:
            return None

        resolving.add(path)
        parent = resolve(rec["Parent"]) if rec["Parent"] else None
        hiring = rec["HiringCostBase"]
        daily = rec["DailyCostBase"]
        inherited_hiring = False
        inherited_daily = False

        if hiring is None and parent is not None:
            hiring = parent["HiringCostBase"]
            inherited_hiring = hiring is not None
        if daily is None and parent is not None:
            daily = parent["DailyCostBase"]
            inherited_daily = daily is not None

        resolving.discard(path)
        resolved = {
            **rec,
            "HiringCostBase": hiring,
            "DailyCostBase": daily,
            "InheritedHiringCost": inherited_hiring,
            "InheritedDailyCost": inherited_daily,
        }
        memo[path] = resolved
        return resolved

    out = {}
    economy_fields = {
        "hiring_cost": {"local": 0, "inherited": 0, "unresolved": 0},
        "daily_cost": {"local": 0, "inherited": 0, "unresolved": 0},
    }
    identifiers = {"explicit": 0, "inferred": 0}
    resolution_failures = 0
    usable_background_scripts = 0

    for path in scripts:
        rec = resolve(path)
        if rec is None:
            resolution_failures += 1
            continue

        background_id = rec["BackgroundID"]
        if background_id is None:
            background_id = f"background.{rec['Key']}"
            identifiers["inferred"] += 1
        else:
            identifiers["explicit"] += 1

        for field_name, value_key, inherited_key in (
            ("hiring_cost", "HiringCostBase", "InheritedHiringCost"),
            ("daily_cost", "DailyCostBase", "InheritedDailyCost"),
        ):
            if rec[value_key] is None:
                origin = "unresolved"
            elif rec[inherited_key]:
                origin = "inherited"
            else:
                origin = "local"
            economy_fields[field_name][origin] += 1

        # Keep only entries with both economic fields; unresolved scripts are
        # tracked but not allowed to masquerade as usable economy refs.
        if rec["HiringCostBase"] is None or rec["DailyCostBase"] is None:
            continue

        usable_background_scripts += 1
        out[rec["SaveHash"]] = {
            "BackgroundID": background_id,
            "Key": rec["Key"],
            "HiringCostBase": rec["HiringCostBase"],
            "DailyCostBase": rec["DailyCostBase"],
            "Script": rec["Script"],
            "ScriptPath": rec["ScriptPath"],
            "Parent": rec["Parent"],
            "InheritedHiringCost": rec["InheritedHiringCost"],
            "InheritedDailyCost": rec["InheritedDailyCost"],
        }

    if not out:
        raise ValueError("Generated background dictionary is empty.")

    t = time.perf_counter()
    _write_json(output_path, out)
    write_seconds = time.perf_counter() - t

    return {
        "backgrounds": len(out),
        "usable_background_scripts": usable_background_scripts,
        "unusable_background_scripts": (
            len(scripts) - resolution_failures - usable_background_scripts
        ),
        "scripts": {
            "scanned": scanned_scripts,
            "decoded": len(scripts),
            "decode_failed": decode_failures,
            "resolution_failed": resolution_failures,
        },
        "economy_fields": economy_fields,
        "identifiers": identifiers,
        "archive": archive_stats,
        "download_seconds": download_seconds,
        "parse_seconds": parse_seconds,
        "write_seconds": write_seconds,
        "total_seconds": time.perf_counter() - started,
        "output_bytes": output_path.stat().st_size if output_path.exists() else None,
    }



def build_perk_audit(
    perk_effects_path: Path = PERK_EFFECTS_OUT,
    model_path: Path = PERK_MODEL_PATH,
    output_path: Path = PERK_AUDIT_OUT,
) -> dict:
    """
    Reconcile every perk script found in vanilla source against our persistent
    BestRole model.

    perk_effects.json is a generated source cache. perk_audit.json is a generated
    review report. Neither needs to ship in the release archive.
    """
    effects = _read_json(perk_effects_path)
    model = _read_json(model_path)

    excluded = set(model.get("excluded", {}))

    rows = []
    unreviewed = []
    for rec in effects.get("perks", {}).values():
        name = rec.get("Name") or rec.get("Stem") or rec.get("ID") or "Unknown"
        if name in excluded:
            status = "excluded"
        else:
            status = "unreviewed"
            unreviewed.append(name)

        rows.append({
            "Name": name,
            "ID": rec.get("ID"),
            "Script": rec.get("Script"),
            "Status": status,
            "ModifiesCoreStats": bool(rec.get("ModifiesCoreStats")),
            "HasExactCoreStatModifiers": bool(rec.get("HasExactCoreStatModifiers")),
            "HasConditionalCoreStatModifiers": bool(rec.get("HasConditionalCoreStatModifiers")),
            "Effects": rec.get("Effects", []),
        })

    rows.sort(key=lambda row: (row["Status"], row["Name"]))
    unreviewed = sorted(set(unreviewed))

    payload = {
        "_meta": {
            "format": "bbtool.perk_audit.v1",
            "source_perks": len(rows),
            "excluded": sum(row["Status"] == "excluded" for row in rows),
            "unreviewed": len(unreviewed),
        },
        "unreviewed": unreviewed,
        "perks": rows,
    }
    _write_json(output_path, payload)
    return payload


def perk_audit_is_present(path: Path = PERK_AUDIT_OUT) -> bool:
    if not path.is_file():
        return False
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(raw, dict)
        and raw.get("_meta", {}).get("format") == "bbtool.perk_audit.v1"
        and isinstance(raw.get("perks"), list)
        and isinstance(raw.get("unreviewed"), list)
    )

def ensure_references(verbose: bool = True) -> dict:
    started = time.perf_counter()
    initial_cache = {
        "dictionary": {
            **_cache_file_info(DICTIONARY_OUT),
            "valid": reference_dictionary_is_present(),
        },
        "backgrounds": {
            **_cache_file_info(BACKGROUNDS_OUT),
            "valid": background_dictionary_is_present(),
        },
        "perks": {
            **_cache_file_info(PERK_EFFECTS_OUT),
            "valid": perk_effect_dictionary_is_present(),
        },
        "traits": {
            **_cache_file_info(TRAIT_EFFECTS_OUT),
            "valid": trait_effect_dictionary_is_present(),
        },
        "permanent_injuries": {
            **_cache_file_info(PERMANENT_INJURY_EFFECTS_OUT),
            "valid": permanent_injury_effect_dictionary_is_present(),
        },
    }

    dictionary_ok = initial_cache["dictionary"]["valid"]
    backgrounds_ok = initial_cache["backgrounds"]["valid"]
    perks_ok = initial_cache["perks"]["valid"]
    traits_ok = initial_cache["traits"]["valid"]
    permanent_injuries_ok = initial_cache["permanent_injuries"]["valid"]
    generated_dictionary = False
    generated_backgrounds = False
    generated_perks = False
    generated_traits = False
    generated_permanent_injuries = False
    dictionary_stats = None
    background_stats = None
    perk_stats = None
    trait_stats = None
    permanent_injury_stats = None
    scripts_download_stats = None

    scripts_archive = None

    if not dictionary_ok:
        t = time.perf_counter()
        try:
            bbedit_dictionary = download_reference_dictionary()
        except Exception as exc:
            raise RuntimeError("Failed to download BB-Edit dictionary.") from exc
        bbedit_seconds = time.perf_counter() - t

        t = time.perf_counter()
        try:
            scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, 45)
        except Exception as exc:
            raise RuntimeError("Failed to download vanilla scripts.") from exc
        scripts_download_stats = _archive_stats(scripts_archive)
        scripts_download_stats["seconds"] = time.perf_counter() - t

        dictionary_stats = build_reference_dictionary(
            bbedit_dictionary=bbedit_dictionary,
            scripts_archive=scripts_archive,
        )
        dictionary_stats["bbedit_download_seconds"] = bbedit_seconds
        dictionary_ok = reference_dictionary_is_present()
        generated_dictionary = True
        if not dictionary_ok:
            raise RuntimeError("Generated dictionary.json failed validation.")

    if not backgrounds_ok:
        if scripts_archive is None:
            t = time.perf_counter()
            scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, 45)
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats["seconds"] = time.perf_counter() - t

        background_stats = build_background_dictionary(
            scripts_archive=scripts_archive,
        )
        backgrounds_ok = background_dictionary_is_present()
        generated_backgrounds = True
        if not backgrounds_ok:
            raise RuntimeError("Generated backgrounds.json failed validation.")

    if not perks_ok:
        if scripts_archive is None:
            t = time.perf_counter()
            scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, 45)
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats["seconds"] = time.perf_counter() - t

        perk_stats = build_perk_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        perks_ok = perk_effect_dictionary_is_present()
        generated_perks = True
        if not perks_ok:
            raise RuntimeError("Generated perk_effects.json failed validation.")

    if not traits_ok:
        if scripts_archive is None:
            t = time.perf_counter()
            scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, 45)
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats["seconds"] = time.perf_counter() - t

        trait_stats = build_trait_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        traits_ok = trait_effect_dictionary_is_present()
        generated_traits = True
        if not traits_ok:
            raise RuntimeError("Generated trait_effects.json failed validation.")

    if not permanent_injuries_ok:
        if scripts_archive is None:
            t = time.perf_counter()
            scripts_archive = _download_bytes(BB_SCRIPTS_ZIP_URL, 45)
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats["seconds"] = time.perf_counter() - t

        permanent_injury_stats = build_permanent_injury_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        permanent_injuries_ok = permanent_injury_effect_dictionary_is_present()
        generated_permanent_injuries = True
        if not permanent_injuries_ok:
            raise RuntimeError("Generated permanent_injury_effects.json failed validation.")

    perk_audit = build_perk_audit() if perks_ok else None
    audit_ok = perk_audit_is_present()

    return {
        "general_ok": dictionary_ok,
        "backgrounds_ok": backgrounds_ok,
        "perks_ok": perks_ok,
        "traits_ok": traits_ok,
        "permanent_injuries_ok": permanent_injuries_ok,
        "perk_audit_ok": audit_ok,
        "perk_audit": perk_audit,
        "generated_dictionary": generated_dictionary,
        "generated_backgrounds": generated_backgrounds,
        "generated_perks": generated_perks,
        "generated_traits": generated_traits,
        "generated_permanent_injuries": generated_permanent_injuries,
        "initial_cache": initial_cache,
        "dictionary_stats": dictionary_stats,
        "background_stats": background_stats,
        "perk_stats": perk_stats,
        "trait_stats": trait_stats,
        "permanent_injury_stats": permanent_injury_stats,
        "scripts_download_stats": scripts_download_stats,
        "total_seconds": time.perf_counter() - started,
    }


def main() -> int:
    status = ensure_references(verbose=True)
    return 0 if all(status[k] for k in ("general_ok", "backgrounds_ok", "perks_ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
