from __future__ import annotations

import json
import math
import struct
from pathlib import Path

from .models import CampaignIdentity, Brother, empty_equipment, empty_gear_fatigue

def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def i16(b: bytes, o: int) -> int:
    return struct.unpack_from("<h", b, o)[0]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def i32(b: bytes, o: int) -> int:
    return struct.unpack_from("<i", b, o)[0]


def f32(b: bytes, o: int) -> float:
    return struct.unpack_from("<f", b, o)[0]


def lp_string(b: bytes, o: int, max_len: int = 512):
    if o + 2 > len(b):
        return None
    n = u16(b, o)
    if n > max_len or o + 2 + n > len(b):
        return None
    raw = b[o + 2:o + 2 + n]
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return s, o + 2 + n, n


def printable_ascii(s: str) -> bool:
    return all(32 <= ord(c) <= 126 for c in s)


def _asset_manager_tail_at(b: bytes, campaign_offset: int) -> int | None:
    """Validate the source-defined asset-manager fields after CampaignID."""
    try:
        campaign_id = i32(b, campaign_offset)
        name_rec = lp_string(b, campaign_offset + 4, 128)
        if name_rec is None or not name_rec[0]:
            return None
        banner_rec = lp_string(b, name_rec[1], 32)
        if banner_rec is None:
            return None
        banner, o, _ = banner_rec
        if not banner.startswith("banner_") or not banner[7:].isdigit():
            return None

        settings = b[o:o + 6]
        if len(settings) != 6:
            return None
        banner_id, look, economic, combat, ironman, destruction_disabled = settings
        if banner_id != int(banner[7:]) or look > 32:
            return None
        if economic > 3 or combat > 3:
            return None
        if ironman not in (0, 1) or destruction_disabled not in (0, 1):
            return None
        o += 6

        origin_rec = lp_string(b, o, 128)
        if origin_rec is None or not origin_rec[0].startswith("scenario."):
            return None
        seed_rec = lp_string(b, origin_rec[1], 128)
        if seed_rec is None or not seed_rec[0] or not printable_ascii(seed_rec[0]):
            return None
        o = seed_rec[1]

        resources = struct.unpack_from("<ffffIffHBfBB", b, o)
        floats = (*resources[:4], *resources[5:7], resources[9])
        if not all(math.isfinite(value) for value in floats):
            return None
        if resources[10] not in (0, 1) or resources[11] not in (0, 1):
            return None
        # Preserve a structurally valid negative ID so it can be reported as
        # invalid evidence rather than mistaken for a missing manager block.
        return campaign_id
    except (IndexError, UnicodeDecodeError, ValueError, struct.error):
        return None


def parse_campaign_identity_bytes(b: bytes) -> CampaignIdentity:
    """Parse exact native campaign membership evidence, or fail safely.

    Vanilla writes a variable-size stash before CampaignID. Candidates are
    therefore located from the following banner string and accepted only when
    the complete source-defined post-stash asset-manager layout validates.
    """
    candidates: list[int] = []
    banner_at = b.find(b"banner_")
    while banner_at >= 0:
        for name_len in range(1, 129):
            campaign_offset = banner_at - 2 - name_len - 2 - 4
            if campaign_offset < 0:
                break
            if u16(b, campaign_offset + 4) != name_len:
                continue
            value = _asset_manager_tail_at(b, campaign_offset)
            if value is not None:
                candidates.append(value)
        banner_at = b.find(b"banner_", banner_at + 1)

    if not candidates:
        return CampaignIdentity(None, confidence="unavailable", reason="not_found")
    if len(candidates) != 1:
        return CampaignIdentity(None, confidence="invalid", reason="ambiguous")
    value = candidates[0]
    if value < 0:
        return CampaignIdentity(None, confidence="invalid", reason="negative_value")
    return CampaignIdentity(value, confidence="exact")


def parse_campaign_identity(save_path: Path) -> CampaignIdentity:
    """Path adapter; path metadata is never identity evidence."""
    return parse_campaign_identity_bytes(save_path.read_bytes())

def try_parse_human_header(b: bytes, human_offset: int):
    """
    Find the AP byte + eight serialized attributes after a b'human' marker.

    The status/member section immediately after b'human' is variable-length:
    experienced brothers can have entries such as Nightmare/Charmed/Sleeping,
    while fresh recruits may have only PotionLastUsed. Rather than assuming a
    fixed member count, scan the small header window for a *unique plausible*
    AP + stat line.

    Serialized stat order:
      HP, Resolve, Fatigue, MAtk, RAtk, MDef, RDef, Initiative

    This is intentionally bounded and conservative. Identity + talent parsing
    downstream provides additional validation before a record is accepted.
    """
    candidates = []
    start = human_offset + 10
    stop = min(len(b) - 17, human_offset + 300)

    for ap_off in range(start, stop):
        ap = b[ap_off]
        if ap > 12:
            continue
        try:
            vals = [i16(b, ap_off + 1 + 2 * i) for i in range(8)]
        except struct.error:
            continue

        hp, resolve, fatigue, matk, ratk, mdef, rdef, initiative = vals

        # Broad mercenary sanity ranges. They intentionally allow developed
        # brothers and some modifiers while rejecting ordinary binary noise.
        if not (30 <= hp <= 200):
            continue
        if not (10 <= resolve <= 120):
            continue
        if not (40 <= fatigue <= 200):
            continue
        if not (20 <= matk <= 150):
            continue
        if not (10 <= ratk <= 150):
            continue
        if not (-20 <= mdef <= 100):
            continue
        if not (-20 <= rdef <= 100):
            continue
        if not (30 <= initiative <= 200):
            continue

        candidates.append((ap_off, ap, vals))

    if not candidates:
        return None

    # In observed live records there is one candidate. If several survive,
    # prefer the earliest candidate; later identity/star validation must also
    # succeed for the brother to be accepted.
    ap_off, ap, vals = candidates[0]
    hp, resolve, fatigue, matk, ratk, mdef, rdef, initiative = vals

    return {
        "HeaderCount": None,
        "AP": ap,
        "StatsEnd": ap_off + 17,
        "HP": hp,
        "Resolve": resolve,
        "Fatigue": fatigue,
        "MAtk": matk,
        "RAtk": ratk,
        "MDef": mdef,
        "RDef": rdef,
        "Initiative": initiative,
    }


def find_identity(b: bytes, start: int, end: int):
    """
    Searches for the identity/meta block after the fixed attribute area.

    Expected block:
      LP name
      LP title
      float light-wound field
      uint32 XP
      six bytes
      level
      perk points
      perks used
      level points
    """
    best = None
    stop = max(start, end - 40)

    for o in range(start, stop):
        a = lp_string(b, o, 40)
        if not a:
            continue
        name, next_o, name_len = a
        if not 2 <= name_len <= 24 or not printable_ascii(name):
            continue
        valid_chars = sum(c.isalpha() or c in " '-_" for c in name)
        if valid_chars / max(1, len(name)) < 0.80:
            continue

        bb = lp_string(b, next_o, 48)
        if not bb:
            continue
        title, q, title_len = bb
        if title_len > 32 or not printable_ascii(title):
            continue
        if q + 22 >= end:
            continue

        try:
            light = f32(b, q)
            xp = u32(b, q + 4)
            level = b[q + 14]
            perk_points = b[q + 15]
            perks_used = b[q + 16]
            level_points = b[q + 17]
        except (struct.error, IndexError):
            continue

        if not math.isfinite(light) or not (-10 <= light <= 10):
            continue
        if xp > 10_000_000 or not 1 <= level <= 33:
            continue
        if perk_points > 20 or perks_used > 20 or level_points > 3:
            continue

        best = {
            "Offset": o,
            "Name": name,
            "Title": title,
            "LightWound": round(light, 4),
            "XP": xp,
            "Level": level,
            "PerkPoints": perk_points,
            "PerksUsed": perks_used,
            "LevelPoints": level_points,
            "MetaEnd": q + 18,
        }
    return best



def find_roster_identity(b: bytes, start: int, end: int):
    """
    Find a company-brother identity inside one structural battleBrother record.

    Unlike the generic identity scanner, roster parsing additionally requires
    the candidate identity to be followed by a valid talent-star block. This
    rejects incidental LP-strings such as the literal word "human" that can
    appear inside a brother payload and otherwise resemble an identity block.

    Strict behavior: exactly one candidate must satisfy both the identity/meta
    layout and the star layout.
    """
    candidates = []
    stop = max(start, end - 40)

    for o in range(start, stop):
        a = lp_string(b, o, 40)
        if not a:
            continue
        name, next_o, name_len = a
        if not 2 <= name_len <= 24 or not printable_ascii(name):
            continue
        valid_chars = sum(c.isalpha() or c in " '-_" for c in name)
        if valid_chars / max(1, len(name)) < 0.80:
            continue

        bb = lp_string(b, next_o, 48)
        if not bb:
            continue
        title, q, title_len = bb
        if title_len > 32 or not printable_ascii(title):
            continue
        if q + 22 >= end:
            continue

        try:
            light = f32(b, q)
            xp = u32(b, q + 4)
            level = b[q + 14]
            perk_points = b[q + 15]
            perks_used = b[q + 16]
            level_points = b[q + 17]
        except (struct.error, IndexError):
            continue

        if not math.isfinite(light) or not (-10 <= light <= 10):
            continue
        if xp > 10_000_000 or not 1 <= level <= 33:
            continue
        if perk_points > 20 or perks_used > 20 or level_points > 3:
            continue

        ident = {
            "Offset": o,
            "Name": name,
            "Title": title,
            "LightWound": round(light, 4),
            "XP": xp,
            "Level": level,
            "PerkPoints": perk_points,
            "PerksUsed": perks_used,
            "LevelPoints": level_points,
            "MetaEnd": q + 18,
        }
        stars = parse_stars(b, ident["MetaEnd"])
        if not stars:
            continue

        # A real serialized battleBrother identity is followed not only by the
        # talent-star block but also by the deterministic level-up roll stream.
        # Requiring both prevents incidental payload strings from masquerading
        # as a second identity candidate inside the same structural record.
        if parse_levelup_roll_sequence(b, ident["MetaEnd"]) is None:
            continue

        candidates.append((ident, stars))

    if len(candidates) != 1:
        return None, None, len(candidates)

    ident, stars = candidates[0]
    return ident, stars, 1


def parse_stars(b: bytes, meta_end: int):
    try:
        o = meta_end
        morale = f32(b, o)
        o += 4
        count = b[o]
        o += 1
        if count > 32:
            return None

        for _ in range(count):
            o += 1
            txt_len = u16(b, o)
            o += 2
            if txt_len > 1024:
                return None
            o += txt_len + 4

        o += 8
        if o + 8 > len(b):
            return None
        s = list(b[o:o + 8])
        if any(x > 3 for x in s):
            return None

        # Save order for talents:
        # HP, Resolve, Fatigue, Initiative, MAtk, RAtk, MDef, RDef
        return {
            "Morale": morale,
            "HPStars": s[0],
            "ResolveStars": s[1],
            "FatigueStars": s[2],
            "InitiativeStars": s[3],
            "MAtkStars": s[4],
            "RAtkStars": s[5],
            "MDefStars": s[6],
            "RDefStars": s[7],
        }
    except (struct.error, IndexError):
        return None



LEVELUP_ROLL_ORDER = (
    "HP", "Resolve", "Fatigue", "Initiative", "MAtk", "RAtk", "MDef", "RDef"
)


def parse_levelup_roll_sequence(b: bytes, meta_end: int) -> dict[str, list[int]] | None:
    """Decode the complete serialized level-up roll sequence through level 11.

    Battle Brothers stores one remaining-roll array per attribute. The first
    entry is the visible pending roll when LevelPoints > 0; subsequent entries
    are the already-generated future rolls. This is parsed for diagnostics only:
    normal recommendations continue to use probabilistic ranges.
    """
    try:
        o = meta_end + 4
        circle_count = b[o]
        o += 1
        if circle_count > 32:
            return None
        for _ in range(circle_count):
            o += 1
            txt_len = u16(b, o)
            o += 2
            if txt_len > 1024:
                return None
            o += txt_len + 4
        o += 8  # metadata before talent stars
        o += 8  # talent stars

        rolls = {}
        lengths = []
        for stat in LEVELUP_ROLL_ORDER:
            count = b[o]
            o += 1
            if count > 32 or o + count > len(b):
                return None
            values = list(b[o:o + count])
            o += count
            if any(v < 1 or v > 6 for v in values):
                return None
            lengths.append(count)
            rolls[stat] = values

        if len(set(lengths)) != 1:
            return None
        return rolls
    except (struct.error, IndexError):
        return None


def load_reference_dictionary(script_dir: Path) -> dict[str, dict]:
    """
    Prefer the complete locally cached BB-Edit dictionary, otherwise use the
    bundled core dictionary. No network access occurs during analysis.
    """
    refdir = script_dir / "references"
    for name in ("dictionary.json", "dictionary_core.json"):
        path = refdir / name
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(raw, dict)
                and raw.get("_meta", {}).get("format")
                == "bbtool.enriched_dictionary.v1"
                and isinstance(raw.get("entries"), dict)
            ):
                raw = raw["entries"]
            if isinstance(raw, list):
                raw = {str(k).upper(): v for k, v in raw}
            return {str(k).upper(): v for k, v in raw.items()}
    return {}


def ref_name(refs: dict, item_id: str) -> str:
    rec = refs.get(item_id.upper(), {})
    return rec.get("name", f"Unknown [{item_id.upper()}]")


EQUIPMENT_SLOT_NAMES = {
    0: "MainHand",
    1: "OffHand",
    2: "Body",
    3: "Head",
    4: "Accessory",
    5: "Ammo",
}


def _number(value: float) -> float | int:
    return int(value) if float(value).is_integer() else round(float(value), 2)


def _finite_number(value: float, label: str) -> float | int:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {label}")
    return _number(value)


def _fatigue_penalty(value) -> int | float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    # Battle Brothers stores item stamina modifiers as negative values.
    return _number(max(0.0, -float(value)))


def _read_item_string(b: bytes, offset: int, end: int) -> tuple[str, int]:
    parsed = lp_string(b, offset, 512)
    if not parsed or parsed[1] > end:
        raise ValueError("invalid serialized item string")
    return parsed[0], parsed[1]


def _parse_generic_item_state(b: bytes, offset: int, end: int) -> tuple[dict, int]:
    # Vanilla 1.5.x serializes the common item state in 14 bytes:
    # repair (1), icon (2), condition (4), quantity marker (4), magic (1),
    # and padding (2). Weapon ammunition follows as a separate uint16.
    if offset + 14 > end:
        raise ValueError("truncated generic item state")
    condition = f32(b, offset + 3)
    if not math.isfinite(condition) or condition < 0:
        raise ValueError("invalid item condition")
    return {"Condition": _number(condition)}, offset + 14


def _parse_armor_attachment(b: bytes, offset: int, end: int) -> tuple[dict, int]:
    if offset + 4 > end:
        raise ValueError("truncated armor attachment")
    attachment_id = b[offset:offset + 4].hex().upper()
    offset += 4
    result = {}
    if attachment_id != "00000000":
        if offset + 32 > end:
            raise ValueError("truncated armor attachment state")
        result["AttachmentID"] = attachment_id
        offset += 32
    return result, offset


def _public_item_type(record: dict, slot: int) -> str:
    if slot == 0:
        return "weapon"
    if slot == 1:
        return "shield"
    if slot == 2:
        return "armor"
    if slot == 3:
        return "helmet"
    if slot == 4:
        return "accessory"
    if slot == 5:
        return "ammo"
    return str(record.get("subType") or record.get("type") or "item")


_SUPPORTED_SERIALIZED_ITEM_TYPES = frozenset({
    "genericWeapon", "genericShield", "genericArmor", "genericHelmet",
    "namedWeapon", "namedShield", "namedArmor", "namedHelmet", "auxiliary",
})


def _parse_equipped_item(
    b: bytes, offset: int, end: int, refs: dict
) -> tuple[int, dict, int]:
    """Parse one BB-Edit-compatible serialized inventory record."""
    if offset + 5 > end:
        raise ValueError("truncated item header")
    slot = b[offset]
    item_id = b[offset + 1:offset + 5].hex().upper()
    record = refs.get(item_id)
    if not record:
        raise KeyError(item_id)

    typ = record.get("type")
    subtype = record.get("subType")
    cursor = offset + 5
    item = {
        "Name": record.get("name") or f"Unknown [{item_id}]",
        "ItemID": item_id,
        "Type": _public_item_type(record, slot),
    }
    serialized_fatigue = None

    if typ == "namedWeapon":
        item["Name"], cursor = _read_item_string(b, cursor, end)
        if cursor + 34 > end:
            raise ValueError("truncated named weapon state")
        item["ConditionMax"] = _finite_number(f32(b, cursor), "maximum condition")
        serialized_fatigue = struct.unpack_from("<b", b, cursor + 4)[0]
        item["DamageMin"] = u16(b, cursor + 5)
        item["DamageMax"] = u16(b, cursor + 7)
        item["ArmorDamagePercent"] = _finite_number(
            f32(b, cursor + 9) * 100, "armor damage"
        )
        item["DirectDamagePercent"] = _finite_number(
            f32(b, cursor + 18) * 100, "direct damage"
        )
        cursor += 34

    elif typ == "namedArmor":
        item["Name"], cursor = _read_item_string(b, cursor, end)
        if cursor + 5 > end:
            raise ValueError("truncated named armor state")
        item["ArmorMax"] = _finite_number(f32(b, cursor), "maximum armor")
        serialized_fatigue = struct.unpack_from("<b", b, cursor + 4)[0]
        cursor += 5

    elif typ == "namedHelmet":
        item["Name"], cursor = _read_item_string(b, cursor, end)
        if cursor + 5 > end:
            raise ValueError("truncated named helmet state")
        item["ArmorMax"] = _finite_number(f32(b, cursor), "maximum armor")
        serialized_fatigue = struct.unpack_from("<b", b, cursor + 4)[0]
        cursor += 5

    elif typ == "namedShield":
        if cursor + 4 > end:
            raise ValueError("truncated named shield state")
        item["ConditionMax"] = _finite_number(f32(b, cursor), "maximum condition")
        cursor += 4

    elif typ not in _SUPPORTED_SERIALIZED_ITEM_TYPES:
        raise ValueError(f"unsupported item type {typ!r}")

    if typ in {"genericArmor", "namedArmor"} and subtype == "nobleArmor":
        cursor += 1
    if typ in {"genericArmor", "namedArmor"} and record.get("slot") == "body":
        attachment, cursor = _parse_armor_attachment(b, cursor, end)
        item.update(attachment)

    generic, cursor = _parse_generic_item_state(b, cursor, end)
    item.update(generic)

    if typ in {"genericWeapon", "namedWeapon"}:
        if cursor + 2 > end:
            raise ValueError("truncated weapon ammo state")
        item["Quantity"] = u16(b, cursor)
        cursor += 2
        if subtype == "masterworkBow":
            _, cursor = _read_item_string(b, cursor, end)
    elif typ == "genericShield" and subtype == "nobleShield":
        cursor += 1
    elif typ in {"genericArmor", "namedArmor", "genericHelmet", "namedHelmet"}:
        if cursor + 4 > end:
            raise ValueError("truncated armor condition")
        armor = f32(b, cursor)
        if not math.isfinite(armor) or armor < 0:
            raise ValueError("invalid armor condition")
        item["Armor"] = _number(armor)
        item["Condition"] = _number(armor)
        cursor += 4
        if record.get("slot") == "body":
            if cursor + 4 > end:
                raise ValueError("truncated body armor fatigue")
            serialized_fatigue = f32(b, cursor)
            cursor += 4
        if subtype == "davkul":
            _, cursor = _read_item_string(b, cursor, end)
    elif typ == "namedShield":
        item["Name"], cursor = _read_item_string(b, cursor, end)
        if cursor + 7 > end:
            raise ValueError("truncated named shield modifiers")
        serialized_fatigue = struct.unpack_from("<b", b, cursor)[0]
        cursor += 7
    elif typ == "auxiliary":
        if subtype == "ammo":
            if cursor + 2 > end:
                raise ValueError("truncated ammunition quantity")
            item["Quantity"] = u16(b, cursor)
            cursor += 2
        elif subtype == "canine":
            item["Name"], cursor = _read_item_string(b, cursor, end)
        elif subtype == "provisions":
            cursor += 10
        elif subtype == "commodity":
            cursor += 2

    fatigue = _fatigue_penalty(
        serialized_fatigue if serialized_fatigue is not None else record.get("fatigue")
    )
    if fatigue is not None:
        item["Fatigue"] = fatigue
    if "ConditionMax" not in item and isinstance(record.get("durability"), (int, float)):
        item["ConditionMax"] = _number(record["durability"])
    if item["Type"] in {"armor", "helmet"} and "ArmorMax" not in item:
        maximum = record.get("durability")
        if isinstance(maximum, (int, float)):
            item["ArmorMax"] = _number(maximum)

    if cursor > end:
        raise ValueError("item extends beyond inventory block")
    return slot, item, cursor


def _find_known_item_tail(
    b: bytes,
    start: int,
    end: int,
    refs: dict,
    count: int,
) -> int | None:
    """Find a provable known-item tail after one unresolvable item.

    Unknown item payloads have no safe generic length. Recovery is therefore
    accepted only when every remaining declared record decodes consecutively
    and the final record lands exactly on the circle-section boundary.
    """
    if count <= 0:
        return end
    memo: dict[tuple[int, int], bool] = {}

    def completes(offset: int, remaining: int) -> bool:
        key = (offset, remaining)
        if key in memo:
            return memo[key]
        try:
            _, _, next_offset = _parse_equipped_item(b, offset, end, refs)
        except (KeyError, ValueError, struct.error, IndexError):
            memo[key] = False
            return False
        result = (
            next_offset == end
            if remaining == 1
            else completes(next_offset, remaining - 1)
        )
        memo[key] = result
        return result

    last_start = end - 5
    for candidate in range(start, last_start + 1):
        if b[candidate] <= 6 and completes(candidate, count):
            return candidate
    return None


def parse_brother_equipment(
    b: bytes,
    stats_end: int,
    circle_offset: int,
    refs: dict,
    *,
    diagnostics: dict | None = None,
    brother_name: str = "",
) -> tuple[dict, dict]:
    """Decode equipped slots and bags without making roster parsing fragile."""
    equipment = empty_equipment()
    fatigue = empty_gear_fatigue()
    cursor = stats_end + 6
    if cursor + 2 > circle_offset or cursor + 2 > len(b):
        return equipment, fatigue
    item_count = b[cursor + 1]
    cursor += 2

    for item_index in range(item_count):
        item_start = cursor
        try:
            slot, item, cursor = _parse_equipped_item(b, cursor, circle_offset, refs)
        except (KeyError, ValueError, struct.error, IndexError) as exc:
            item_id = (
                b[item_start + 1:item_start + 5].hex().upper()
                if item_start + 5 <= circle_offset else ""
            )
            if item_start < circle_offset:
                slot = b[item_start]
                unknown = {
                    "Name": ref_name(refs, item_id) if item_id else "Unknown Item",
                    "ItemID": item_id,
                    "Type": _public_item_type(refs.get(item_id, {}), slot),
                }
                key = EQUIPMENT_SLOT_NAMES.get(slot)
                if slot == 6:
                    unknown["Slot"] = len(equipment["Bag"]) + 1
                    equipment["Bag"].append(unknown)
                elif key:
                    equipment[key] = unknown
            if diagnostics is not None:
                diagnostics.setdefault("recoverable_failures", []).append({
                    "scope": "roster",
                    "kind": "equipment_item_unresolved",
                    "name": brother_name,
                    "item_index": item_index,
                    "item_id": item_id,
                    "reason": str(exc),
                })
            remaining = item_count - item_index - 1
            recovery = _find_known_item_tail(
                b, item_start + 5, circle_offset, refs, remaining
            )
            if recovery is None or remaining == 0:
                break
            cursor = recovery
            continue

        key = EQUIPMENT_SLOT_NAMES.get(slot)
        if slot == 6:
            item["Slot"] = len(equipment["Bag"]) + 1
            equipment["Bag"].append(item)
            key = "Bag"
        elif key:
            equipment[key] = item
        else:
            continue
        penalty = item.get("Fatigue", 0)
        if isinstance(penalty, (int, float)):
            fatigue[key] += penalty

    fatigue["Total"] = _number(sum(fatigue[key] for key in fatigue if key != "Total"))
    return equipment, fatigue


def _parse_tail_entries(
    b: bytes,
    o: int,
    count: int,
    identity_offset: int,
    refs: dict,
    memo: dict,
):
    """
    Parse trait/injury-like circle entries until identity_offset.

    Known IDs use their exact BB-Edit serialization length. Unknown IDs are
    backtracked across the few known event payload lengths, allowing the parser
    to remain useful with mods or a stale core dictionary.
    """
    key = (o, count)
    if key in memo:
        return memo[key]
    if count == 0:
        return [] if o == identity_offset else None
    if o + 4 > identity_offset:
        return None

    item_id = b[o:o+4].hex().upper()
    rec = refs.get(item_id, {})
    typ = rec.get("type", "unknown")

    if typ == "injury":
        extras = [14]
    elif typ == "training":
        extras = [1 + 37]
    elif typ == "knowledge":
        extras = [1 + 12]
    elif typ == "learning":
        extras = [1 + 2]
    elif typ in ("trait", "perk", "internal", "potion-effect", "permanentInjury"):
        extras = [1]
    else:
        # Unknown entries: normal circle first, then known event variants.
        extras = [1, 14, 38, 13, 3]

    seen = set()
    for extra in extras:
        if extra in seen:
            continue
        seen.add(extra)
        nxt = o + 4 + extra
        if nxt > identity_offset:
            continue
        rest = _parse_tail_entries(b, nxt, count - 1, identity_offset, refs, memo)
        if rest is not None:
            result = [{"id": item_id, "type": typ, "extra": extra}] + rest
            memo[key] = result
            return result

    memo[key] = None
    return None


def find_circle_metadata(
    b: bytes,
    stats_end: int,
    identity_offset: int,
    refs: dict,
):
    """
    Locate the perks/background/traits block without needing to decode equipped
    items first.

    BB-Edit serialization writes:
      uint16 total_circle_count
      perk IDs (+1 isNew byte each)
      background ID (+1 isNew byte)
      description string
      description-template string
      2 unknown bytes
      salary multiplier float
      optional tattoo byte for Wildman/Barbarian
      remaining traits/injuries
      identity block

    Candidate sections are accepted only if they land exactly on the already
    validated identity offset.
    """
    background_ids = {
        k for k, v in refs.items() if v.get("type") == "background"
    }
    if not background_ids:
        return None

    # Inventory/circle data begins after core stats; scan conservatively.
    scan_start = max(stats_end, identity_offset - 5000)
    scan_end = identity_offset - 8

    candidates = []
    for start in range(scan_start, scan_end):
        try:
            total = u16(b, start)
        except struct.error:
            continue
        if not 1 <= total <= 64:
            continue

        o = start + 2
        pre = []
        bg = None

        # Entries before and including background are fixed 5-byte records:
        # 4-byte circle ID + one serialized isNew byte.
        for idx in range(total):
            if o + 5 > identity_offset:
                break
            item_id = b[o:o+4].hex().upper()
            if item_id in background_ids:
                bg = (idx, item_id)
                o += 5
                break
            pre.append(item_id)
            o += 5

        if bg is None:
            continue

        bg_index, bg_id = bg
        remaining = total - bg_index - 1

        desc = lp_string(b, o, 4096)
        if not desc:
            continue
        _, o, _ = desc
        templ = lp_string(b, o, 4096)
        if not templ:
            continue
        _, o, _ = templ

        if o + 6 > identity_offset:
            continue
        background_level = b[o]
        background_is_new = b[o + 1]
        o += 2
        try:
            salary = f32(b, o)
        except struct.error:
            continue
        if not math.isfinite(salary) or not -10 <= salary <= 20:
            continue
        o += 4

        if bg_id in ("6DF381C6", "CB90AA90"):
            o += 1

        tail = _parse_tail_entries(b, o, remaining, identity_offset, refs, {})
        if tail is None:
            continue

        # Every known entry before the background must be a perk. Merely
        # lowering confidence lets a longer inventory-byte coincidence beat
        # the real circle block (observed when an item hash appears in `pre`).
        # Unknown entries remain eligible so stale/modded perk dictionaries
        # continue to degrade explicitly rather than abort parsing.
        bad_pre = sum(
            1 for x in pre
            if refs.get(x, {}).get("type") not in ("perk", None)
        )
        if bad_pre:
            continue
        known_perks = sum(
            1 for x in pre if refs.get(x, {}).get("type") == "perk"
        )
        unknown_pre = len(pre) - known_perks
        score = (known_perks, -unknown_pre, -abs(identity_offset - start))
        candidates.append((score, {
            "CircleOffset": start,
            "Count": total,
            "BackgroundID": bg_id,
            "Background": ref_name(refs, bg_id),
            "PerkIDs": pre,
            "Perks": [ref_name(refs, x) for x in pre],
            "Tail": tail,
            "BackgroundLevel": background_level,
            "BackgroundIsNew": bool(background_is_new),
            "DailyCostMult": salary,
        }))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]

    trait_ids, traits = [], []
    injury_ids, injuries = [], []
    permanent_injury_ids, permanent_injuries = [], []
    temporary_injury_ids = []
    # BB-Edit reclassifies any perk appearing after background back into perks.
    for ent in best["Tail"]:
        item_id = ent["id"]
        rec = refs.get(item_id, {})
        typ = rec.get("type", ent.get("type", "unknown"))
        name = ref_name(refs, item_id)
        if typ == "perk":
            best["PerkIDs"].append(item_id)
            best["Perks"].append(name)
        elif typ == "injury":
            injury_ids.append(item_id)
            temporary_injury_ids.append(item_id)
            injuries.append(name)
        elif typ == "permanentInjury":
            injury_ids.append(item_id)
            permanent_injury_ids.append(item_id)
            injuries.append(name)
            permanent_injuries.append(name)
        elif typ == "internal":
            # Needed for byte-accurate parsing but not a player-facing trait.
            continue
        else:
            trait_ids.append(item_id)
            traits.append(name)

    best["TraitIDs"] = trait_ids
    best["Traits"] = traits
    best["InjuryIDs"] = injury_ids
    best["Injuries"] = injuries
    best["PermanentInjuryIDs"] = permanent_injury_ids
    best["PermanentInjuries"] = permanent_injuries
    best["TemporaryInjuryIDs"] = temporary_injury_ids
    return best

BROTHER_SIGNATURE = bytes.fromhex(
    "000000000000007D2C10000000000000D4C4A7E9000100000102000000"
)


def find_company_brother_human_offsets(b: bytes) -> tuple[list[int], dict]:
    """
    Locate the company roster from the save's serialized brother block.

    Battle Brothers serializes a distinctive battleBrother signature. The
    byte 19 bytes before the first signature stores the company brother count.
    This is the same roster-boundary mechanism used by current BB-Edit.

    We then map each of the first N company battleBrother records to its
    structural 'human' header marker so the existing low-level parser can
    decode the record.

    This deliberately does NOT scan all 'human' records in the save, because
    settlement recruitment candidates use the same character serialization.
    """
    sig_offsets = _find_brother_signature_offsets(b)

    if not sig_offsets:
        raise RuntimeError("Brother signature was not found in the save.")

    first = sig_offsets[0]
    if first < 19:
        raise RuntimeError("Brother signature found too early to read roster count.")

    roster_count = b[first - 19]
    if roster_count <= 0:
        raise RuntimeError(f"Invalid company roster count: {roster_count}")
    if len(sig_offsets) < roster_count:
        raise RuntimeError(
            f"Save declares {roster_count} company brothers, "
            f"but only {len(sig_offsets)} brother signatures were found."
        )

    company_sigs = sig_offsets[:roster_count]
    human_offsets = []

    for i, sig in enumerate(company_sigs):
        # BB-Edit starts battleBrother parsing 29 bytes after the signature.
        entity_start = sig + 29

        # The structural "human" member occurs later in the serialized header.
        # Search only inside this battleBrother's own record window.
        next_sig = sig_offsets[i + 1] if i + 1 < len(sig_offsets) else min(len(b), sig + 12_000)
        search_end = min(next_sig, entity_start + 6_000)
        human = b.find(b"human", entity_start, search_end)

        if human < 0:
            raise RuntimeError(
                f"Could not locate structural human marker for company brother {i + 1}/"
                f"{roster_count} near byte offset {sig}."
            )

        # Validate that the marker actually leads to a plausible BB human header.
        if not try_parse_human_header(b, human):
            raise RuntimeError(
                f"Invalid human header for company brother {i + 1}/{roster_count} "
                f"at byte offset {human}."
            )

        human_offsets.append(human)

    debug = {
        "RosterCount": roster_count,
        "TotalBrotherSignatures": len(sig_offsets),
        "CompanySignatureOffsets": company_sigs,
        "CompanyHumanOffsets": human_offsets,
    }
    return human_offsets, debug


class DuplicateBrotherNameError(RuntimeError):
    """Raised when two company brothers share the same visible name."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Duplicate company brother name: {name}")


def parse_roster_bytes(b: bytes, *, diagnostics: dict | None = None) -> list[Brother]:
    """Parse company brothers from supplied save content."""
    refs = load_reference_dictionary(Path(__file__).resolve().parent.parent)

    human_offsets, roster_debug = find_company_brother_human_offsets(b)

    parsed: list[Brother] = []

    # Identity parsing must be bounded by the serialized battleBrother record,
    # NOT by the next raw occurrence of the ASCII word "human". A brother's
    # payload can legitimately contain another "human" string before the
    # identity block (observed in the wild with Asbjorn).
    company_sigs = roster_debug["CompanySignatureOffsets"]
    all_sigs = _find_brother_signature_offsets(b)

    for i, p in enumerate(human_offsets):
        header = try_parse_human_header(b, p)
        if not header:
            raise RuntimeError(f"Failed to parse company human header at {p}.")

        sig = company_sigs[i]
        try:
            sig_index = all_sigs.index(sig)
        except ValueError as exc:
            raise RuntimeError(
                f"Company brother signature at {sig} disappeared during parsing."
            ) from exc

        end = min(
            all_sigs[sig_index + 1] if sig_index + 1 < len(all_sigs) else len(b),
            p + 20_000,
        )
        ident, stars, identity_candidates = find_roster_identity(
            b, header["StatsEnd"], end
        )
        if not ident:
            raise RuntimeError(
                f"Failed to identify company brother at human offset {p}: "
                f"{identity_candidates} identity+stars candidates found."
            )
        future_rolls = parse_levelup_roll_sequence(b, ident["MetaEnd"])
        if future_rolls is None:
            raise RuntimeError(
                f"Failed to parse serialized level-up roll sequence for {ident['Name']}."
            )
        current_rolls = (
            {stat: values[0] for stat, values in future_rolls.items() if values}
            if ident["LevelPoints"] > 0 else {}
        )
        if ident["LevelPoints"] > 0 and current_rolls is None:
            raise RuntimeError(
                f"Failed to parse current level-up rolls for {ident['Name']}."
            )

        circles = find_circle_metadata(
            b, header["StatsEnd"], ident["Offset"], refs
        )
        if circles is None:
            if diagnostics is not None:
                diagnostics.setdefault("recoverable_failures", []).append({
                    "scope": "roster",
                    "kind": "circle_metadata_unresolved",
                    "human_offset": p,
                    "name": ident["Name"],
                })
            circles = {
                "BackgroundID": "",
                "Background": "Unknown",
                "PerkIDs": [],
                "Perks": [],
                "TraitIDs": [],
                "Traits": [],
                "InjuryIDs": [],
                "Injuries": [],
                "PermanentInjuryIDs": [],
                "PermanentInjuries": [],
                "TemporaryInjuryIDs": [],
            }

        equipment, gear_fatigue = parse_brother_equipment(
            b,
            header["StatsEnd"],
            circles.get("CircleOffset", ident["Offset"]),
            refs,
            diagnostics=diagnostics,
            brother_name=ident["Name"],
        )

        bro = Brother(
            Name=ident["Name"],
            Title=ident["Title"],
            Level=ident["Level"],
            XP=ident["XP"],
            PerkPoints=ident["PerkPoints"],
            PerksUsed=ident["PerksUsed"],
            LevelPoints=ident["LevelPoints"],
            AP=header["AP"],
            HP=header["HP"], HPStars=stars["HPStars"],
            Fatigue=header["Fatigue"], FatigueStars=stars["FatigueStars"],
            Resolve=header["Resolve"], ResolveStars=stars["ResolveStars"],
            Initiative=header["Initiative"], InitiativeStars=stars["InitiativeStars"],
            MAtk=header["MAtk"], MAtkStars=stars["MAtkStars"],
            RAtk=header["RAtk"], RAtkStars=stars["RAtkStars"],
            MDef=header["MDef"], MDefStars=stars["MDefStars"],
            RDef=header["RDef"], RDefStars=stars["RDefStars"],
            BackgroundID=circles["BackgroundID"],
            Background=circles["Background"],
            PerkIDs=circles["PerkIDs"],
            Perks=circles["Perks"],
            TraitIDs=circles["TraitIDs"],
            Traits=circles["Traits"],
            Injuries=circles["Injuries"],
            HumanOffset=p,
            InjuryIDs=circles.get("InjuryIDs", []),
            PermanentInjuryIDs=circles.get("PermanentInjuryIDs", []),
            PermanentInjuries=circles.get("PermanentInjuries", []),
            TemporaryInjuryIDs=circles.get("TemporaryInjuryIDs", []),
            CurrentRolls=current_rolls or {},
            FutureRolls=future_rolls,
            Equipment=equipment,
            GearFatigue=gear_fatigue,
        )

        parsed.append(bro)

    if len(parsed) != roster_debug["RosterCount"]:
        raise RuntimeError(
            f"Roster parser expected {roster_debug['RosterCount']} company brothers "
            f"but decoded {len(parsed)}."
        )

    return parsed


def parse_roster(save_path: Path, *, diagnostics: dict | None = None) -> list[Brother]:
    """Path adapter for :func:`parse_roster_bytes`."""
    return parse_roster_bytes(save_path.read_bytes(), diagnostics=diagnostics)


def _all_valid_human_offsets(b: bytes) -> list[int]:
    offsets = []
    pos = 0
    while True:
        p = b.find(b"human", pos)
        if p < 0:
            break
        if try_parse_human_header(b, p):
            offsets.append(p)
        pos = p + 5
    return offsets


def _parse_tryout_done(
    b: bytes,
    sig: int,
    search_end: int,
    identity_offset: int,
) -> bool | None:
    """
    Decode the recruitment tryout flag.

    Controlled before/after saves show the serialized candidate tail as:
      FF + 28 zero bytes + tryout_done byte

    The byte changed 00 -> 01, and only that byte changed inside the tested
    Swordmaster candidate record after paying for Tryout.

    Search from the validated identity block toward the end of this candidate,
    and use the last matching tail marker to avoid unrelated FF padding.
    """
    start = max(identity_offset, sig)
    stop = min(search_end, len(b))

    matches = []
    pos = start
    prefix = b"\xff" + (b"\x00" * 28)
    while True:
        p = b.find(prefix, pos, stop)
        if p < 0:
            break
        flag_pos = p + len(prefix)
        if flag_pos < stop and b[flag_pos] in (0, 1):
            matches.append(flag_pos)
        pos = p + 1

    if not matches:
        return None

    return bool(b[matches[-1]])


def _find_brother_signature_offsets(b: bytes) -> list[int]:
    offsets = []
    pos = 0
    while True:
        p = b.find(BROTHER_SIGNATURE, pos)
        if p < 0:
            break
        offsets.append(p)
        pos = p + 1
    return offsets


def _resolve_settlement_reference(
    b: bytes,
    settlement_ref: int,
) -> str | None:
    """
    Resolve a serialized settlement reference through the settlement registry.

    A valid registry occurrence is:
      uint32 settlement_ref
      LP-string settlement name
      LP-string human-readable description

    Requiring both strings avoids accepting unrelated occurrences of the same
    integer elsewhere in the save.
    """
    ref_bytes = struct.pack("<I", settlement_ref)
    matches = []
    pos = 0

    while True:
        p = b.find(ref_bytes, pos)
        if p < 0:
            break
        pos = p + 1

        name_rec = lp_string(b, p + 4, 64)
        if not name_rec:
            continue
        name, after_name, name_len = name_rec
        if not (2 <= name_len <= 40 and printable_ascii(name)):
            continue

        desc_rec = lp_string(b, after_name, 2048)
        if not desc_rec:
            continue
        description, _, desc_len = desc_rec
        if not (10 <= desc_len <= 1500 and printable_ascii(description)):
            continue

        matches.append(name)

    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def _find_recruitment_rosters(b: bytes) -> tuple[list[dict], list[int]]:
    """
    Locate every serialized settlement hiring roster.

    The save may retain recruitment pools for multiple settlements at once.
    Each hiring-roster block begins at its first battleBrother signature and
    stores immediately before that signature:
      uint32 settlement_ref  at -23
      uint16 candidate_count at -19

    The following `candidate_count` battleBrother signatures belong to that
    settlement. This is the same count-prefixed structure observed for the
    company roster, but with a settlement reference identifying the owner.

    Returns:
      (roster descriptors, all battleBrother signature offsets)
    """
    sig_offsets = _find_brother_signature_offsets(b)
    if not sig_offsets:
        return [], []

    company_count = b[sig_offsets[0] - 19]
    idx = company_count
    rosters = []

    while idx < len(sig_offsets):
        sig = sig_offsets[idx]
        if sig < 23:
            idx += 1
            continue

        try:
            settlement_ref = u32(b, sig - 23)
            candidate_count = u16(b, sig - 19)
        except struct.error:
            idx += 1
            continue

        if not 1 <= candidate_count <= 64:
            idx += 1
            continue
        if idx + candidate_count > len(sig_offsets):
            idx += 1
            continue

        settlement = _resolve_settlement_reference(b, settlement_ref)
        if settlement is None:
            idx += 1
            continue

        rosters.append({
            "Settlement": settlement,
            "SettlementRef": settlement_ref,
            "Count": candidate_count,
            "StartIndex": idx,
            "EndIndex": idx + candidate_count,
        })
        idx += candidate_count

    return rosters, sig_offsets


def _candidate_records(b: bytes, refs: dict) -> list[dict]:
    """
    Decode all settlement recruitment candidates, preserving roster ownership.

    Recruitment candidates use the same battleBrother/human serialization as
    company brothers. The parser first identifies each count-prefixed hiring
    roster and then decodes only the signatures belonging to that roster.

    Only public recruitment-screen fields are ultimately exposed by
    `parse_recruits`; hidden stats/talents never leave this parser.
    """
    recruitment_rosters, sig_offsets = _find_recruitment_rosters(b)
    all_humans = _all_valid_human_offsets(b)
    candidates = []

    for roster in recruitment_rosters:
        settlement = roster["Settlement"]

        for idx in range(roster["StartIndex"], roster["EndIndex"]):
            sig = sig_offsets[idx]
            entity_start = sig + 29
            next_sig = (
                sig_offsets[idx + 1]
                if idx + 1 < len(sig_offsets)
                else min(len(b), sig + 12_000)
            )

            human = b.find(
                b"human",
                entity_start,
                min(next_sig, entity_start + 6_000),
            )
            if human < 0:
                continue

            header = try_parse_human_header(b, human)
            if not header:
                continue

            end = next(
                (h for h in all_humans if h > human),
                min(len(b), human + 20_000),
            )
            ident = find_identity(b, header["StatsEnd"], end)
            if not ident:
                continue

            circles = find_circle_metadata(
                b,
                header["StatsEnd"],
                ident["Offset"],
                refs,
            )
            if not circles:
                continue

            trait_tail = [
                ent
                for ent in circles["Tail"]
                if refs.get(ent.get("id", ""), {}).get(
                    "type",
                    ent.get("type", "unknown"),
                )
                not in ("perk", "internal")
            ]
            public_traits = [
                name
                for ent, name in zip(trait_tail, circles["Traits"], strict=True)
                if refs.get(ent.get("id", ""), {}).get(
                    "type",
                    ent.get("type", "unknown"),
                )
                not in ("injury", "permanentInjury")
            ]

            # The next battleBrother signature is a safe upper bound even when
            # this is the final candidate of one roster and the next signature
            # starts another settlement roster.
            tryout_search_end = (
                next_sig
                if idx + 1 < len(sig_offsets)
                else min(len(b), ident["Offset"] + 8_000)
            )
            tryout_done = _parse_tryout_done(
                b,
                sig,
                tryout_search_end,
                ident["Offset"],
            )

            candidates.append({
                "_SignatureOffset": sig,
                "_HumanOffset": human,
                "_Header": header,
                "_CircleOffset": circles["CircleOffset"],
                "Settlement": settlement,
                "Name": ident["Name"],
                "Title": ident["Title"],
                "Background": circles["Background"],
                "_BackgroundID": circles["BackgroundID"],
                "Level": ident["Level"],
                "_BackgroundLevel": int(
                    circles.get("BackgroundLevel", ident["Level"])
                ),
                "TryoutDone": tryout_done,
                "_ParsedTraits": public_traits,
                "_DailyCostMult": float(
                    circles.get("DailyCostMult", 1.0)
                ),
            })

    return candidates


def _load_item_economy(script_dir: Path) -> dict:
    path = script_dir / "references" / "dictionary.json"
    if not path.is_file():
        raise RuntimeError("references/dictionary.json is missing.")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("_meta", {}).get("format")
        != "bbtool.enriched_dictionary.v1"
        or not isinstance(raw.get("entries"), dict)
    ):
        raise RuntimeError("references/dictionary.json is not enriched.")

    out = {}
    for ref_id, rec in raw["entries"].items():
        if (
            rec.get("Value") is None
            or rec.get("type") not in _SUPPORTED_SERIALIZED_ITEM_TYPES
        ):
            continue
        # Keep the parsing metadata needed by the same item decoder used for
        # roster equipment. Named-item strings make static lengths unsafe.
        out[str(ref_id).upper()] = {**rec, "Value": rec["Value"]}
    return out


def _parse_recruit_equipment_value(
    b: bytes,
    header: dict,
    circle_offset: int,
    item_economy: dict,
    diagnostics: list[dict] | None = None,
) -> int | None:
    """
    Sum vanilla getValue() for recruit equipment.

    Inventory starts after the eight core stats, followed by the six
    greed/gluttony bytes, pouch count, and item count. Each item is decoded
    through a conservative hash registry. If an item is unknown or its
    serialized length does not land exactly on the already-validated circle
    metadata offset, return None rather than estimate a hire cost.
    """
    p = header["StatsEnd"] + 6
    if p + 2 > len(b):
        return None

    count = b[p + 1]
    p += 2

    total_value = 0
    for _ in range(count):
        if p + 5 > circle_offset:
            return None

        item_hash = b[p + 1:p + 5].hex().upper()
        meta = item_economy.get(item_hash)
        if not meta:
            if diagnostics is not None:
                diagnostics.append({
                    "scope": "recruits",
                    "kind": "unresolved_recruit_equipment",
                    "reference_hash": item_hash,
                })
            return None

        try:
            _, _, next_offset = _parse_equipped_item(
                b, p, circle_offset, item_economy
            )
        except (ValueError, struct.error, IndexError) as exc:
            if diagnostics is not None:
                diagnostics.append({
                    "scope": "recruits",
                    "kind": "recruit_equipment_parse_failure",
                    "reference_hash": item_hash,
                    "reason": str(exc),
                })
            return None

        total_value += int(meta["Value"])
        p = next_offset

    if p != circle_offset:
        return None

    return total_value


def _compute_hire_cost(
    background_id: str,
    background_level: int,
    equipment_value: int | None,
    economy: dict,
) -> int | None:
    """
    Reproduce character_background.adjustHiringCostBasedOnEquipment().

    base = floor(background HiringCost + 500 * (Level - 1)^1.5)
    equipment contribution = 125% of item getValue() total
    final cost is rounded up to the next 10 crowns.
    """
    cfg = _background_economy_entry(background_id, economy)
    if not cfg or equipment_value is None:
        return None

    base = math.floor(
        float(cfg["HiringCostBase"])
        + 500.0 * math.pow(max(0, int(background_level) - 1), 1.5)
    )
    value = base + float(equipment_value) * 1.25
    return int(math.ceil(value * 0.1) * 10)


def _load_background_economy(script_dir: Path) -> dict:
    """Load generated background economy keyed by exact save hash."""
    path = script_dir / "references" / "backgrounds.json"
    if not path.is_file():
        raise RuntimeError("references/backgrounds.json is missing.")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("references/backgrounds.json is invalid.")

    out = {}
    for save_hash, rec in raw.items():
        out[str(save_hash).upper()] = {
            "HiringCostBase": rec["HiringCostBase"],
            "DailyCostBase": rec["DailyCostBase"],
            "Script": rec.get("Script"),
        }
    return out


def _background_economy_entry(
    background_id: str,
    economy: dict,
) -> dict | None:
    return economy.get(str(background_id).upper())


def _squirrel_round(value: float) -> int:
    # Squirrel Math.round for non-negative wage values.
    return int(math.floor(value + 0.5))


def _compute_daily_wage(
    background_id: str,
    level: int,
    daily_cost_mult: float,
    parsed_traits: list[str],
    economy: dict,
) -> int | None:
    cfg = _background_economy_entry(background_id, economy)
    if not cfg:
        return None

    daily_cost = float(cfg["DailyCostBase"])

    # character_background.onAdded() increments any positive DailyCost by 1.
    if daily_cost > 0:
        daily_cost += 1.0

    wage = _squirrel_round(daily_cost * float(daily_cost_mult))

    # Vanilla character_background.onUpdate():
    # +10% compounded per level through 11, +3% compounded thereafter.
    value = wage * math.pow(1.1, min(10, max(0, int(level) - 1)))
    if level > 11:
        previous = wage * math.pow(1.1, 10)
        value += previous * math.pow(1.03, int(level) - 11) - previous

    # Starting Greedy modifies CurrentProperties.DailyWageMult.
    if "Greedy" in parsed_traits:
        value *= 1.15

    # Recruitment UI displays the integer crown amount.
    return max(0, int(math.floor(value + 1e-9)))


def parse_recruits_bytes(
    b: bytes,
    diagnostics: dict | None = None,
) -> list[dict]:
    """
    Return settlement recruitment candidates using public information only.

    Intentionally NOT exported: base stats, talents/stars, hidden traits,
    projections, Fit or any other post-hire information.

    Settlement association is resolved through the recruitment roster's
    serialized settlement reference. Daily wage and hire cost are reconstructed
    from vanilla background logic; hire cost uses the recruit's serialized
    equipment and exact vanilla item values. Unknown equipment yields null rather
    than an estimate.
    """
    script_dir = Path(__file__).resolve().parent.parent
    refs = load_reference_dictionary(script_dir)
    economy = _load_background_economy(script_dir)
    item_economy = _load_item_economy(script_dir)
    recoverable_failures = (
        diagnostics.setdefault("recoverable_failures", [])
        if diagnostics is not None
        else None
    )

    recruits = []
    for rec in _candidate_records(b, refs):
        tryout_done = rec.get("TryoutDone")
        daily_wage = _compute_daily_wage(
            rec["_BackgroundID"],
            rec["Level"],
            rec["_DailyCostMult"],
            rec["_ParsedTraits"],
            economy,
        )
        equipment_value = _parse_recruit_equipment_value(
            b,
            rec["_Header"],
            rec["_CircleOffset"],
            item_economy,
            recoverable_failures,
        )
        hire_cost = _compute_hire_cost(
            rec["_BackgroundID"],
            rec["_BackgroundLevel"],
            equipment_value,
            economy,
        )

        recruits.append({
            "Settlement": rec["Settlement"],
            "Name": rec["Name"],
            "Title": rec["Title"],
            "Background": rec["Background"],
            "Level": rec["Level"],
            "TryoutDone": tryout_done,
            "Traits": rec["_ParsedTraits"] if tryout_done is True else [],
            "HireCost": hire_cost,
            "DailyWage": daily_wage,
        })
    return recruits


def parse_recruits(
    save_path: Path,
    diagnostics: dict | None = None,
) -> list[dict]:
    """Path adapter for :func:`parse_recruits_bytes`."""
    return parse_recruits_bytes(save_path.read_bytes(), diagnostics=diagnostics)
