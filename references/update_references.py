#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REFERENCE_STATUS_SCHEMA = "bbtool.reference_status.v1"
DOWNLOAD_MAX_ATTEMPTS = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 0.25
_TRANSIENT_HTTP_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
REFERENCE_CACHE_SCHEMAS = {
    "dictionary": "bbtool.enriched_dictionary.v1",
    "backgrounds": "bbtool.backgrounds.v2",
    "perks": "bbtool.perk_effects.v2",
    "traits": "bbtool.trait_effects.v2",
    "permanent_injuries": "bbtool.permanent_injury_effects.v1",
    "perk_audit": "bbtool.perk_audit.v1",
}

# External source upgrades are intentional repository changes. Keep every normal
# reference-generation input here, addressed by a full immutable commit SHA.
BBEDIT_DICTIONARY_REVISION = "bdab5a8216090506a33e8263b8fb112ebf12b361"
BB_SCRIPTS_REVISION = "162f498ac7c49b4c317bbf54718a595ecef6a65a"
REFERENCE_SOURCES = {
    "bbedit_dictionary": {
        "upstream_source": "https://github.com/scarglamour/bb-edit",
        "immutable_revision": BBEDIT_DICTIONARY_REVISION,
        "requested_url": (
            "https://raw.githubusercontent.com/scarglamour/bb-edit/"
            f"{BBEDIT_DICTIONARY_REVISION}/"
            "src/renderer/js/dictionary.json"
        ),
        "generated_references": ("dictionary",),
    },
    "vanilla_scripts": {
        "upstream_source": "https://github.com/ninkjin/Battle-Brothers-Scripts",
        "immutable_revision": BB_SCRIPTS_REVISION,
        "requested_url": (
            "https://codeload.github.com/ninkjin/Battle-Brothers-Scripts/zip/"
            f"{BB_SCRIPTS_REVISION}"
        ),
        "generated_references": (
            "dictionary",
            "backgrounds",
            "perks",
            "traits",
            "permanent_injuries",
            "perk_audit",
        ),
    },
}

BBEDIT_DICTIONARY_URL = REFERENCE_SOURCES["bbedit_dictionary"]["requested_url"]
BB_SCRIPTS_ZIP_URL = REFERENCE_SOURCES["vanilla_scripts"]["requested_url"]

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
CONDITION_MAX_RE = re.compile(
    r'(?:this\.)?m\.ConditionMax\s*=\s*(-?\d+(?:\.\d+)?)',
    re.MULTILINE,
)
STAMINA_MODIFIER_RE = re.compile(
    r'(?:this\.)?m\.StaminaModifier\s*=\s*(-?\d+(?:\.\d+)?)',
    re.MULTILINE,
)
ITEM_TYPE_EXPRESSION_RE = re.compile(
    r'(?:this\.)?m\.ItemType\s*=\s*(.*?);',
    re.MULTILINE,
)
SLOT_TYPE_EXPRESSION_RE = re.compile(
    r'(?:this\.)?m\.SlotType\s*=\s*(.*?);',
    re.MULTILINE,
)
CREATE_ITEM_PARENT_RE = re.compile(
    r'\bthis\.([a-z0-9_]+)\.create\s*\(\s*\)\s*;',
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

BACKGROUND_STAT_PROPERTIES = {
    "Hitpoints": "HP", "Stamina": "Fatigue", "Bravery": "Resolve",
    "Initiative": "Initiative", "MeleeSkill": "MAtk",
    "RangedSkill": "RAtk", "MeleeDefense": "MDef", "RangedDefense": "RDef",
}
BACKGROUND_STAT_RANGE_RE = re.compile(
    r"\b(" + "|".join(BACKGROUND_STAT_PROPERTIES) + r")\s*=\s*\[\s*"
    r"(-?\d+)\s*,\s*(-?\d+)\s*\]",
    re.MULTILINE,
)
EXCLUDED_TALENTS_RE = re.compile(
    r"(?:this\.)?m\.ExcludedTalents\s*=\s*\[(.*?)\]", re.DOTALL,
)
EXCLUDED_TALENT_ENTRY_RE = re.compile(
    r"this\.Const\.Attributes\.([A-Za-z]+)"
)
UNTALENTED_RE = re.compile(r"(?:this\.)?m\.IsUntalented\s*=\s*true\b")
TALENT_MUTATION_RE = re.compile(r"(?:getTalents\s*\(|\bm\.Talents\b)")
CREATE_BACKGROUND_PARENT_RE = re.compile(
    r"function\s+create\s*\([^)]*\)\s*\{\s*"
    r"this\.([a-z0-9_]+_background)\.create\s*\(\s*\)\s*;",
    re.DOTALL,
)
CHANGE_ATTRIBUTES_RE = re.compile(r"function\s+onChangeAttributes\s*\(")


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
        stem = stem.removesuffix(suffix)
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
    if not isinstance(raw, dict):
        return False
    if raw.get("_meta", {}).get("format") != "bbtool.backgrounds.v2":
        return False
    entries = raw.get("backgrounds")
    if not isinstance(entries, dict) or len(entries) < 50:
        return False
    return all(
        isinstance(k, str)
        and isinstance(v, dict)
        and "HiringCostBase" in v
        and "DailyCostBase" in v
        and "Script" in v
        for k, v in entries.items()
    )


def _download_once(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BB-Save-Toolkit/2.7"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _is_transient_download_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _TRANSIENT_HTTP_STATUS_CODES
    return isinstance(
        exc,
        (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            socket.timeout,
            ssl.SSLError,
        ),
    )


def _download_bytes(url: str, timeout: int = 30) -> bytes:
    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        try:
            payload = _download_once(url, timeout)
        except Exception as exc:
            if (
                attempt == DOWNLOAD_MAX_ATTEMPTS
                or not _is_transient_download_error(exc)
            ):
                raise
            delay = DOWNLOAD_RETRY_BACKOFF_SECONDS * attempt
            print(
                "Reference download failed "
                f"(attempt {attempt}/{DOWNLOAD_MAX_ATTEMPTS}): {exc}"
            )
            print(f"Retrying in {delay:g}s...")
            time.sleep(delay)
        else:
            if attempt > 1:
                print(
                    "Reference download succeeded "
                    f"(attempt {attempt}/{DOWNLOAD_MAX_ATTEMPTS})"
                )
            return payload
    raise AssertionError("unreachable")


def _download_with_provenance(
    url: str,
    timeout: int,
    *,
    selected_revision: str,
) -> tuple[bytes, dict]:
    started = time.perf_counter()
    payload = _download_bytes(url, timeout)
    return payload, {
        "source": "network",
        "url": url,
        "selected_revision": selected_revision,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "seconds": time.perf_counter() - started,
    }


def _configured_source_provenance(source_name: str) -> dict:
    source = REFERENCE_SOURCES[source_name]
    generated_references = source["generated_references"]
    return {
        "source_name": source_name,
        "upstream_source": source["upstream_source"],
        "immutable_revision": source["immutable_revision"],
        "requested_url": source["requested_url"],
        "generated_reference_schemas": {
            name: REFERENCE_CACHE_SCHEMAS[name] for name in generated_references
        },
    }


def _download_reference_source(source_name: str, timeout: int) -> tuple[bytes, dict]:
    configured = _configured_source_provenance(source_name)
    try:
        payload, download = _download_with_provenance(
            configured["requested_url"],
            timeout,
            selected_revision=configured["immutable_revision"],
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download external reference source {source_name!r} "
            f"at immutable revision {configured['immutable_revision']} "
            f"from {configured['requested_url']}."
        ) from exc
    return payload, {**download, **configured}


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
            script_path = rel.removesuffix(".nut")
            stem = _slug(Path(path).stem)
            parent_match = INHERIT_RE.search(text)
            id_match = ITEM_ID_RE.search(text)
            name_match = NAME_RE.search(text)
            value_match = VALUE_RE.search(text)
            condition_max_match = CONDITION_MAX_RE.search(text)
            stamina_modifier_match = STAMINA_MODIFIER_RE.search(text)
            item_type_match = ITEM_TYPE_EXPRESSION_RE.search(text)
            slot_type_match = SLOT_TYPE_EXPRESSION_RE.search(text)
            create_parent_match = CREATE_ITEM_PARENT_RE.search(text)

            def local_number(match):
                if match is None:
                    return None
                numeric = float(match.group(1))
                return int(numeric) if numeric.is_integer() else numeric

            local_value = local_number(value_match)
            local_condition_max = local_number(condition_max_match)
            local_stamina_modifier = local_number(stamina_modifier_match)

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
                "LocalConditionMax": local_condition_max,
                "LocalStaminaModifier": local_stamina_modifier,
                "ItemTypeExpression": (
                    item_type_match.group(1).strip() if item_type_match else None
                ),
                "SlotTypeExpression": (
                    slot_type_match.group(1).strip() if slot_type_match else None
                ),
                "CreateParent": (
                    create_parent_match.group(1) if create_parent_match else None
                ),
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
            "ConditionMax": rec["LocalConditionMax"],
            "StaminaModifier": rec["LocalStaminaModifier"],
            "ItemTypeExpression": rec["ItemTypeExpression"],
            "SlotTypeExpression": rec["SlotTypeExpression"],
            "CreateParent": rec["CreateParent"],
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


def _source_only_generic_weapon_entry(
    ref_id: str, candidates: list[dict]
) -> dict | None:
    """Build a source-only generic weapon only when pinned semantics prove it."""
    if len(candidates) != 1:
        return None
    source = candidates[0]
    expression = source.get("ItemTypeExpression") or ""
    if (
        source.get("CreateParent") != "weapon"
        or "this.Const.Items.ItemType.Weapon" not in expression
        or "this.Const.Items.ItemType.Tool" in expression
    ):
        return None
    if not isinstance(source.get("Name"), str) or not source["Name"].strip():
        return None
    if not isinstance(source.get("ID"), str) or not source["ID"].strip():
        return None
    if not isinstance(source.get("Value"), (int, float)):
        return None
    if not isinstance(source.get("ConditionMax"), (int, float)):
        return None
    if not isinstance(source.get("StaminaModifier"), (int, float)):
        return None

    slot_expression = source.get("SlotTypeExpression") or ""
    slot = (
        "mainhand" if "Const.ItemSlot.Mainhand" in slot_expression
        else "offhand" if "Const.ItemSlot.Offhand" in slot_expression
        else None
    )
    return {
        "name": source["Name"].strip(),
        "type": "genericWeapon",
        "slot": slot,
        "subType": None,
        "durability": source["ConditionMax"],
        "fatigue": source["StaminaModifier"],
        "Value": source["Value"],
        "SerializedLength": SERIALIZED_LENGTH_BY_TYPE["genericWeapon"],
        "ValueSource": "vanilla-script-save-hash",
        "Script": source["Source"],
        "ValueScript": source.get("ValueScript"),
        "InheritedValue": bool(source.get("InheritedValue")),
        "TechnicalID": source["ID"],
        "ReferenceSource": "vanilla-script-source-only",
        "SaveHash": ref_id,
    }


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
    source_only_added = 0

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
        # Runtime roster equipment parsing needs the immutable vanilla maximum
        # condition and stamina modifier for generic items. Avoid expanding the
        # generated cache with null fields for non-item dictionary records.
        for field in ("durability", "fatigue"):
            if isinstance(rec.get(field), (int, float)):
                entry[field] = rec[field]

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

    # BB-Edit is not a complete vanilla key index. Admit only source-only generic
    # weapons whose pinned script semantics prove their serialized type and all
    # parser-required static metadata. Ambiguous/base/tool scripts stay excluded.
    for ref_id in sorted(set(by_save_hash) - set(bbedit_dictionary)):
        entry = _source_only_generic_weapon_entry(ref_id, by_save_hash[ref_id])
        if entry is None:
            continue
        entries[ref_id] = entry
        source_only_added += 1
        equipment_like += 1
        with_value += 1
        exact_hash_matches += 1
        exact_hash_with_value += 1
        ts = type_stats.setdefault(
            "genericWeapon", {"ids": 0, "with_value": 0, "unresolved": 0}
        )
        ts["ids"] += 1
        ts["with_value"] += 1

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
        "source_only_added": source_only_added,
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
            script_path = rel.removesuffix(".nut")
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
            script_path = rel.removesuffix(".nut")
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
    Build versioned background economy and intrinsic-potential refs.

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
    base_attribute_ranges = None
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
            script_path = rel.removesuffix(".nut")
            parent_match = INHERIT_RE.search(text)
            create_parent_match = CREATE_BACKGROUND_PARENT_RE.search(text)
            id_match = BACKGROUND_ID_RE.search(text)
            hiring_match = HIRING_COST_RE.search(text)
            daily_match = DAILY_COST_RE.search(text)

            def num(match):
                if not match:
                    return None
                val = float(match.group(1))
                return int(val) if val.is_integer() else val

            range_matches = BACKGROUND_STAT_RANGE_RE.findall(text)
            ranges = {
                BACKGROUND_STAT_PROPERTIES[prop]: [int(lo), int(hi)]
                for prop, lo, hi in range_matches
            }
            if _stem_slug(path) == "character":
                first_ranges = {}
                for prop, lo, hi in range_matches:
                    first_ranges.setdefault(
                        BACKGROUND_STAT_PROPERTIES[prop], [int(lo), int(hi)]
                    )
                if set(first_ranges) == set(BACKGROUND_STAT_PROPERTIES.values()):
                    base_attribute_ranges = first_ranges
            excluded_match = EXCLUDED_TALENTS_RE.search(text)
            excluded = [] if excluded_match is None else [
                BACKGROUND_STAT_PROPERTIES[prop]
                for prop in EXCLUDED_TALENT_ENTRY_RE.findall(excluded_match.group(1))
                if prop in BACKGROUND_STAT_PROPERTIES
            ]
            scripts[script_path] = {
                "Script": rel,
                "ScriptPath": script_path,
                "SaveHash": battle_brothers_save_hash(script_path),
                "Parent": (
                    parent_match.group(1) if parent_match else
                    "scripts/skills/backgrounds/" + create_parent_match.group(1)
                    if create_parent_match else None
                ),
                "BackgroundID": id_match.group(1) if id_match else None,
                "HiringCostBase": num(hiring_match),
                "DailyCostBase": num(daily_match),
                "Key": _stem_slug(path),
                "AttributeOffsets": ranges,
                "ExcludedTalents": sorted(set(excluded)),
                "Untalented": bool(UNTALENTED_RE.search(text)),
                "DefinesExcludedTalents": excluded_match is not None,
                "DefinesUntalented": bool(UNTALENTED_RE.search(text)),
                "HasTalentMutation": bool(TALENT_MUTATION_RE.search(text)),
                "DefinesAttributeOffsets": bool(CHANGE_ATTRIBUTES_RE.search(text)),
            }

    parse_seconds = time.perf_counter() - t
    inheritance_memo = {}
    checking_inheritance = set()

    def inheritance_resolves(path: str) -> bool:
        if path in inheritance_memo:
            return inheritance_memo[path]
        if path in checking_inheritance:
            return False

        rec = scripts.get(path)
        if rec is None:
            return False
        parent_path = rec["Parent"]
        if parent_path is None:
            inheritance_memo[path] = True
            return True
        if not parent_path.startswith("scripts/skills/backgrounds/"):
            # The background root inherits from the generic skill hierarchy.
            # That external parent has no economy fields and is a valid
            # inheritance boundary, not a missing background script.
            inheritance_memo[path] = True
            return True

        checking_inheritance.add(path)
        valid = inheritance_resolves(parent_path)
        checking_inheritance.discard(path)
        inheritance_memo[path] = valid
        return valid

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
        offsets = rec["AttributeOffsets"]
        excluded = rec["ExcludedTalents"]
        untalented = rec["Untalented"]
        has_talent_mutation = rec["HasTalentMutation"]

        if hiring is None and parent is not None:
            hiring = parent["HiringCostBase"]
            inherited_hiring = hiring is not None
        if daily is None and parent is not None:
            daily = parent["DailyCostBase"]
            inherited_daily = daily is not None
        if not rec["DefinesAttributeOffsets"] and parent is not None:
            offsets = parent["AttributeOffsets"]
        if not rec["DefinesExcludedTalents"] and parent is not None:
            excluded = parent["ExcludedTalents"]
        if not rec["DefinesUntalented"] and parent is not None:
            untalented = parent["Untalented"]
        if parent is not None:
            has_talent_mutation = (
                has_talent_mutation or parent["HasTalentMutation"]
            )

        resolving.discard(path)
        resolved = {
            **rec,
            "HiringCostBase": hiring,
            "DailyCostBase": daily,
            "InheritedHiringCost": inherited_hiring,
            "InheritedDailyCost": inherited_daily,
            "AttributeOffsets": offsets,
            "ExcludedTalents": excluded,
            "Untalented": untalented,
            "HasTalentMutation": has_talent_mutation,
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
        if not inheritance_resolves(path):
            resolution_failures += 1
            continue
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

        if rec["HiringCostBase"] is not None and rec["DailyCostBase"] is not None:
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
        offsets = rec["AttributeOffsets"]
        if rec["HasTalentMutation"]:
            out[rec["SaveHash"]]["PotentialUnsupportedReason"] = "talent_mutation"
        elif set(offsets) == set(BACKGROUND_STAT_PROPERTIES.values()):
            base = base_attribute_ranges
            if base is None:
                raise ValueError("character background base attribute ranges are unresolved")
            out[rec["SaveHash"]]["PotentialProfile"] = {
                "level": 1,
                "stat_ranges": {
                    stat: [base[stat][0] + offsets[stat][0],
                           base[stat][1] + offsets[stat][1]]
                    for stat in base
                },
                "excluded_talents": rec["ExcludedTalents"],
                "untalented": rec["Untalented"],
            }
        else:
            out[rec["SaveHash"]]["PotentialUnsupportedReason"] = (
                "non_static_attribute_offsets"
            )

    if not out:
        raise ValueError("Generated background dictionary is empty.")

    t = time.perf_counter()
    payload = {
        "_meta": {
            "format": "bbtool.backgrounds.v2",
            "source_revision": BB_SCRIPTS_REVISION,
            "potential_model_inputs": "vanilla_level_1_ranges_and_talent_eligibility",
        },
        "backgrounds": out,
    }
    _write_json(output_path, payload)
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
    download_sources = {}

    scripts_archive = None

    if not dictionary_ok:
        bbedit_bytes, bbedit_source = _download_reference_source(
            "bbedit_dictionary", 20
        )
        try:
            bbedit_dictionary = _normalize_dictionary(
                json.loads(bbedit_bytes.decode("utf-8"))
            )
        except Exception as exc:
            raise RuntimeError(
                "Downloaded BB-Edit dictionary from immutable revision "
                f"{bbedit_source['immutable_revision']} is invalid."
            ) from exc
        download_sources["bbedit_dictionary"] = bbedit_source
        bbedit_seconds = bbedit_source["seconds"]

        scripts_archive, scripts_source = _download_reference_source(
            "vanilla_scripts", 45
        )
        download_sources["vanilla_scripts"] = scripts_source
        scripts_download_stats = _archive_stats(scripts_archive)
        scripts_download_stats.update(scripts_source)

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
            scripts_archive, scripts_source = _download_reference_source(
                "vanilla_scripts", 45
            )
            download_sources["vanilla_scripts"] = scripts_source
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats.update(scripts_source)

        background_stats = build_background_dictionary(
            scripts_archive=scripts_archive,
        )
        backgrounds_ok = background_dictionary_is_present()
        generated_backgrounds = True
        if not backgrounds_ok:
            raise RuntimeError("Generated backgrounds.json failed validation.")

    if not perks_ok:
        if scripts_archive is None:
            scripts_archive, scripts_source = _download_reference_source(
                "vanilla_scripts", 45
            )
            download_sources["vanilla_scripts"] = scripts_source
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats.update(scripts_source)

        perk_stats = build_perk_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        perks_ok = perk_effect_dictionary_is_present()
        generated_perks = True
        if not perks_ok:
            raise RuntimeError("Generated perk_effects.json failed validation.")

    if not traits_ok:
        if scripts_archive is None:
            scripts_archive, scripts_source = _download_reference_source(
                "vanilla_scripts", 45
            )
            download_sources["vanilla_scripts"] = scripts_source
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats.update(scripts_source)

        trait_stats = build_trait_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        traits_ok = trait_effect_dictionary_is_present()
        generated_traits = True
        if not traits_ok:
            raise RuntimeError("Generated trait_effects.json failed validation.")

    if not permanent_injuries_ok:
        if scripts_archive is None:
            scripts_archive, scripts_source = _download_reference_source(
                "vanilla_scripts", 45
            )
            download_sources["vanilla_scripts"] = scripts_source
            scripts_download_stats = _archive_stats(scripts_archive)
            scripts_download_stats.update(scripts_source)

        permanent_injury_stats = build_permanent_injury_effect_dictionary(
            scripts_archive=scripts_archive,
        )
        permanent_injuries_ok = permanent_injury_effect_dictionary_is_present()
        generated_permanent_injuries = True
        if not permanent_injuries_ok:
            raise RuntimeError("Generated permanent_injury_effects.json failed validation.")

    perk_audit = build_perk_audit() if perks_ok else None
    audit_ok = perk_audit_is_present()

    generated = {
        "dictionary": generated_dictionary,
        "backgrounds": generated_backgrounds,
        "perks": generated_perks,
        "traits": generated_traits,
        "permanent_injuries": generated_permanent_injuries,
        "perk_audit": bool(perk_audit),
    }
    valid = {
        "dictionary": dictionary_ok,
        "backgrounds": backgrounds_ok,
        "perks": perks_ok,
        "traits": traits_ok,
        "permanent_injuries": permanent_injuries_ok,
        "perk_audit": audit_ok,
    }
    paths = {
        "dictionary": DICTIONARY_OUT,
        "backgrounds": BACKGROUNDS_OUT,
        "perks": PERK_EFFECTS_OUT,
        "traits": TRAIT_EFFECTS_OUT,
        "permanent_injuries": PERMANENT_INJURY_EFFECTS_OUT,
        "perk_audit": PERK_AUDIT_OUT,
    }
    final_cache = {
        name: {
            "path": str(path.resolve()),
            **_cache_file_info(path),
            "valid": valid[name],
            "source": (
                ("network-derived" if generated_perks else "cache-derived")
                if name == "perk_audit"
                else "network-generated"
                if generated[name]
                else "cache"
            ),
        }
        for name, path in paths.items()
    }

    return {
        "schema": REFERENCE_STATUS_SCHEMA,
        "reference_schemas": dict(REFERENCE_CACHE_SCHEMAS),
        "cache_directory": str(HERE.resolve()),
        "configured_sources": {
            name: _configured_source_provenance(name)
            for name in REFERENCE_SOURCES
        },
        "download_sources": download_sources,
        "fallback_used": False,
        "final_cache": final_cache,
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
