from types import SimpleNamespace

from bbtool.app import publication_signatures as publication
from bbtool.models import CampaignIdentity


class _Catalog:
    def __init__(self, roles):
        self.roles = roles

    def analyzer_config(self, classification):
        return SimpleNamespace(roles=self.roles, classification=classification)


class _AssignedBuilds:
    def __init__(self):
        self.campaigns = {
            11: {
                "campaign:11/entity:1": {
                    "status": "current",
                    "build_identity": "reach_dps",
                    "assigned_definition_hash": "sha256:def",
                    "current_definition_hash": "sha256:def",
                    "display_name": "Reach DPS",
                }
            },
            22: {},
        }

    def read_campaign(self, campaign):
        return {"revision": 999, "assignments": self.campaigns[campaign.value]}


def _roles(name="Reach DPS"):
    return [{
        "id": "reach_dps",
        "name": name,
        "stats": {"MAtk": {"weight": 1}},
    }]


def _exact_campaign(monkeypatch, value=11):
    monkeypatch.setattr(
        publication,
        "parse_campaign_identity_bytes",
        lambda _content: CampaignIdentity(value, confidence="exact"),
    )


def test_desired_dependency_signatures_are_populated_and_exclude_display_names(monkeypatch):
    _exact_campaign(monkeypatch)
    assigned = _AssignedBuilds()
    first = publication.build_desired_dependency_signatures(
        b"save", _roles("Reach DPS"), {"invest": 70}, assigned
    )
    renamed = publication.build_desired_dependency_signatures(
        b"save", _roles("Renamed display only"), {"invest": 70}, assigned
    )

    assert first == renamed
    assert first["inputs"]
    assert "Reach DPS" not in repr(first)
    assert "Renamed display only" not in repr(first)


def test_selected_campaign_intent_change_fails_currentness(monkeypatch):
    _exact_campaign(monkeypatch)
    assigned = _AssignedBuilds()
    catalog = _Catalog(_roles())
    snapshot = publication.build_desired_dependency_signatures(
        b"save", catalog.roles, {"invest": 70}, assigned
    )
    assert publication.dependency_signatures_are_current(
        snapshot, catalog=catalog, classification={"invest": 70}, assigned_builds=assigned
    )

    assigned.campaigns[11]["campaign:11/entity:1"]["build_identity"] = "banner"
    assert not publication.dependency_signatures_are_current(
        snapshot, catalog=catalog, classification={"invest": 70}, assigned_builds=assigned
    )


def test_unrelated_campaign_mutation_does_not_change_currentness(monkeypatch):
    _exact_campaign(monkeypatch)
    assigned = _AssignedBuilds()
    catalog = _Catalog(_roles())
    snapshot = publication.build_desired_dependency_signatures(
        b"save", catalog.roles, {"invest": 70}, assigned
    )
    assigned.campaigns[22]["campaign:22/entity:9"] = {
        "status": "current",
        "build_identity": "banner",
        "assigned_definition_hash": "sha256:other",
        "current_definition_hash": "sha256:other",
        "display_name": "Banner",
    }

    assert publication.dependency_signatures_are_current(
        snapshot, catalog=catalog, classification={"invest": 70}, assigned_builds=assigned
    )


def test_classification_change_invalidates_desired_snapshot_without_role_display_identity(monkeypatch):
    _exact_campaign(monkeypatch)
    assigned = _AssignedBuilds()
    catalog = _Catalog(_roles())
    snapshot = publication.build_desired_dependency_signatures(
        b"save", catalog.roles, {"invest": 70}, assigned
    )

    assert not publication.dependency_signatures_are_current(
        snapshot, catalog=catalog, classification={"invest": 71}, assigned_builds=assigned
    )
