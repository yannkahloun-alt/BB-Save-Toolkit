"""Deterministic current-state perk/gear facts, separate from projection."""

from __future__ import annotations

import math

_WEAPON_DEPENDENT = {
    "Axe Mastery",
    "Bow Mastery",
    "Cleaver Mastery",
    "Crossbow Mastery",
    "Dagger Mastery",
    "Flail Mastery",
    "Hammer Mastery",
    "Mace Mastery",
    "Polearm Mastery",
    "Spear Mastery",
    "Sword Mastery",
    "Throwing Mastery",
}


def _fact(perk: str, state: str, basis: str, **values) -> dict:
    return {"Perk": perk, "State": state, "Basis": basis, **values}


def _slot_penalty(equipment: dict, slot: str) -> int | float | None:
    item = equipment.get(slot)
    if item is None:
        return 0
    value = item.get("Fatigue") if isinstance(item, dict) else None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value


def _armor_value(equipment: dict, slot: str) -> int | float | None:
    item = equipment.get(slot)
    if item is None:
        return 0
    value = item.get("Armor") if isinstance(item, dict) else None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value


def _nimble(equipment: dict) -> dict:
    body = _slot_penalty(equipment, "Body")
    head = _slot_penalty(equipment, "Head")
    if body is None or head is None:
        return _fact("Nimble", "unknown", "armor_fatigue_unavailable")
    total = body + head
    excess = max(0.0, total - 15.0)
    multiplier = min(1.0, 0.4 + excess**1.23 * 0.01)
    return _fact(
        "Nimble",
        "active" if multiplier < 1.0 else "no_current_reduction",
        "body_and_head_fatigue",
        ArmorFatiguePenalty=total,
        HitpointDamageMultiplier=round(multiplier, 6),
        HitpointDamageReductionPct=round((1.0 - multiplier) * 100.0, 4),
    )


def _battle_forged(equipment: dict) -> dict:
    body = _armor_value(equipment, "Body")
    head = _armor_value(equipment, "Head")
    if body is None or head is None:
        return _fact("Battle Forged", "unknown", "current_armor_unavailable")
    total = body + head
    multiplier = 1.0 - total * 0.0005
    return _fact(
        "Battle Forged",
        "active" if total > 0 else "no_current_reduction",
        "current_body_and_head_armor",
        CurrentArmor=total,
        ArmorDamageMultiplier=round(multiplier, 6),
        ArmorDamageReductionPct=round(total * 0.05, 4),
    )


def _brawny(equipment: dict) -> dict:
    body = _slot_penalty(equipment, "Body")
    head = _slot_penalty(equipment, "Head")
    if body is None or head is None:
        return _fact("Brawny", "unknown", "armor_fatigue_unavailable")
    # Vanilla rounds body and head separately because their item update methods
    # use floor and ceil respectively on the stored negative stamina modifier.
    body_after = math.ceil(body * 0.7)
    head_after = math.floor(head * 0.7)
    before = body + head
    after = body_after + head_after
    return _fact(
        "Brawny",
        "active" if after < before else "no_current_reduction",
        "body_and_head_fatigue",
        ArmorFatiguePenaltyBefore=before,
        ArmorFatiguePenaltyAfter=after,
        FatigueCapacityBenefit=before - after,
        BodyPenaltyAfter=body_after,
        HeadPenaltyAfter=head_after,
    )


def perk_gear_facts(bro) -> list[dict]:
    """Return facts only for relevant perks currently owned by ``bro``.

    Unknown is a first-class result: it means the current public parser cannot
    prove the required item/combat state, never that the perk is inactive.
    """
    perks = set(getattr(bro, "Perks", ()) or ())
    equipment = getattr(bro, "Equipment", {}) or {}
    facts = []
    for perk in sorted(perks):
        if perk == "Nimble":
            facts.append(_nimble(equipment))
        elif perk == "Battle Forged":
            facts.append(_battle_forged(equipment))
        elif perk == "Brawny":
            facts.append(_brawny(equipment))
        elif perk == "Shield Expert":
            offhand = equipment.get("OffHand")
            if offhand is None:
                facts.append(_fact(perk, "inactive", "offhand_empty"))
            elif isinstance(offhand, dict) and "Condition" in offhand:
                if offhand.get("Type") == "shield":
                    facts.append(_fact(perk, "active", "shield_equipped"))
                else:
                    facts.append(_fact(perk, "inactive", "offhand_not_shield"))
            else:
                facts.append(_fact(perk, "unknown", "offhand_type_unresolved"))
        elif perk in _WEAPON_DEPENDENT:
            facts.append(_fact(perk, "unknown", "weapon_mastery_metadata_unavailable"))
        elif perk in {"Duelist", "Reach Advantage"}:
            facts.append(
                _fact(perk, "unknown", "weapon_handedness_and_class_unavailable")
            )
        elif perk == "Dodge":
            facts.append(_fact(perk, "unknown", "live_initiative_unavailable"))
    return facts
