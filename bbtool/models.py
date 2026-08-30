from __future__ import annotations

from dataclasses import dataclass, field

STATS = ("HP", "Fatigue", "Resolve", "Initiative", "MAtk", "RAtk", "MDef", "RDef")
STAR_FIELDS = tuple(f"{s}Stars" for s in STATS)


def empty_equipment() -> dict:
    """Return the stable public shape used for a brother's current loadout."""
    return {
        "MainHand": None,
        "OffHand": None,
        "Body": None,
        "Head": None,
        "Accessory": None,
        "Ammo": None,
        "Bag": [],
    }


def empty_gear_fatigue() -> dict[str, int]:
    return {
        "MainHand": 0,
        "OffHand": 0,
        "Body": 0,
        "Head": 0,
        "Accessory": 0,
        "Ammo": 0,
        "Bag": 0,
        "Total": 0,
    }

@dataclass
class Brother:
    Name: str
    Title: str
    Level: int
    XP: int
    PerkPoints: int
    PerksUsed: int
    LevelPoints: int
    AP: int
    HP: int
    HPStars: int
    Fatigue: int
    FatigueStars: int
    Resolve: int
    ResolveStars: int
    Initiative: int
    InitiativeStars: int
    MAtk: int
    MAtkStars: int
    RAtk: int
    RAtkStars: int
    MDef: int
    MDefStars: int
    RDef: int
    RDefStars: int
    BackgroundID: str
    Background: str
    PerkIDs: list[str]
    Perks: list[str]
    TraitIDs: list[str]
    Traits: list[str]
    Injuries: list[str]
    HumanOffset: int
    CurrentRolls: dict[str, int] = field(default_factory=dict)
    FutureRolls: dict[str, list[int]] = field(default_factory=dict)
    InjuryIDs: list[str] = field(default_factory=list)
    PermanentInjuryIDs: list[str] = field(default_factory=list)
    PermanentInjuries: list[str] = field(default_factory=list)
    TemporaryInjuryIDs: list[str] = field(default_factory=list)
    Equipment: dict = field(default_factory=empty_equipment)
    GearFatigue: dict[str, int] = field(default_factory=empty_gear_fatigue)

    @property
    def BrotherID(self) -> str:
        """Unique company-brother identifier inside one parsed save."""
        return f"human:{int(self.HumanOffset)}"
