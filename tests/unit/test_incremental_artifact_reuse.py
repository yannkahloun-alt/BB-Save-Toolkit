from bbtool.incremental.cache import IncrementalCache
from bbtool.app import analysis as analysis_module
from bbtool.incremental.fingerprint import (
    ADVISOR_ENGINE_VERSION,
    BROTHER_SUMMARY_ENGINE_VERSION,
    advisor_fingerprint,
    brother_projection_fingerprint,
    brother_summary_fingerprint,
    role_fingerprint,
)


def test_cosmetic_build_rename_reuses_all_intrinsic_artifacts_and_matches_full(
    bro_factory,simple_role,cfg
):
    bro=bro_factory(Level=11)
    original={**simple_role(("HP","MAtk","MDef")),"id":"test_build"}
    renamed={**original,"name":"Current Display Name"}
    classification=cfg.classification

    cold_cache=IncrementalCache(None)
    analysis_module.analyze_brothers([bro],[original],classification,cold_cache)
    manifest=cold_cache.manifest_payload(generated_at="cold",source_save="same.sav")
    warm_cache=IncrementalCache(manifest)
    warm=analysis_module.analyze_brothers([bro],[renamed],classification,warm_cache)
    full=analysis_module.analyze_brothers([bro],[renamed],classification,None)

    assert warm==full
    assert warm.fits[0]["Role"]=="Current Display Name"
    assert warm.summaries[0]["BestRole"]=="Current Display Name"
    assert warm_cache.stats.role_reused==1
    assert warm_cache.stats.summary_reused==1
    assert warm_cache.stats.advisor_reused==1
    assert warm_cache.get_validation_oracle(bro,renamed) is not None


def test_cosmetic_rename_refreshes_reused_advisor_role_labels(
    bro_factory,simple_role
):
    bro=bro_factory()
    original={**simple_role(("HP","MAtk","MDef")),"id":"test_build"}
    renamed={**original,"name":"Renamed"}
    cache=IncrementalCache(None)
    cache.store_advisor(bro,[original],{
        "AnchorRole":original["name"],
        "BestFit":{"Role":original["name"]},
        "Recommended":{"RoleBefore":original["name"],"RoleAfter":original["name"]},
    })
    warm=IncrementalCache(cache.manifest_payload(generated_at="x",source_save="x"))

    result=warm.get_advisor(bro,[renamed])

    assert result["AnchorRole"]=="Renamed"
    assert result["BestFit"]["Role"]=="Renamed"
    assert result["Recommended"]["RoleBefore"]=="Renamed"
    assert result["Recommended"]["RoleAfter"]=="Renamed"


def test_changed_identity_with_unique_semantics_refreshes_advisor_label(
    bro_factory,simple_role
):
    bro=bro_factory()
    original={**simple_role(("HP","MAtk","MDef")),"id":"old_id"}
    replacement={**original,"id":"new_id","name":"Replacement Label"}
    cache=IncrementalCache(None)
    cache.store_advisor(bro,[original],{"AnchorRole":original["name"]})
    warm=IncrementalCache(cache.manifest_payload(generated_at="x",source_save="x"))

    assert warm.get_advisor(bro,[replacement])["AnchorRole"]=="Replacement Label"
    assert warm.stats.advisor_reused==1


def test_malformed_advisor_metadata_is_not_counted_or_carried_forward(
    bro_factory,simple_role
):
    bro=bro_factory()
    role={**simple_role(("HP","MAtk","MDef")),"id":"test_build"}
    cache=IncrementalCache(None)
    cache.store_advisor(bro,[role],{"AnchorRole":role["name"]})
    manifest=cache.manifest_payload(generated_at="x",source_save="x")
    entry=next(iter(manifest["brothers"].values()))
    entry["advisor"]["role_labels"]="corrupt"
    warm=IncrementalCache(manifest)

    assert warm.get_advisor(bro,[role]) is None
    assert warm.stats.advisor_reused==0
    assert "advisor" not in next(iter(warm._current.values()), {})


def test_ambiguous_semantic_association_recomputes_advisor(
    bro_factory,simple_role
):
    bro=bro_factory()
    original={**simple_role(("HP","MAtk","MDef")),"id":"old_one"}
    duplicate={**original,"id":"old_two","name":"Duplicate"}
    cache=IncrementalCache(None)
    cache.store_advisor(bro,[original,duplicate],{"AnchorRole":original["name"]})
    warm=IncrementalCache(cache.manifest_payload(generated_at="x",source_save="x"))
    alternatives=[
        {**original,"id":"new_one","name":"One"},
        {**original,"id":"new_two","name":"Two"},
    ]

    assert warm.get_advisor(bro,alternatives) is None
    assert warm.stats.advisor_reused==0
    assert warm.miss_reasons["advisor_role_association_ambiguous"]==1


def test_same_identity_semantic_change_invalidates_only_affected_role(
    bro_factory,simple_role
):
    bro=bro_factory()
    affected={**simple_role(("HP",)),"id":"affected","name":"Affected"}
    unrelated={**simple_role(("MAtk",)),"id":"unrelated","name":"Unrelated"}
    cache=IncrementalCache(None)
    cache.store_role_row(bro,affected,{"Role":"Affected"})
    cache.store_role_row(bro,unrelated,{"Role":"Unrelated"})
    warm=IncrementalCache(cache.manifest_payload(generated_at="x",source_save="x"))
    changed={**affected,"stats":{
        key:dict(value) for key,value in affected["stats"].items()
    }}
    changed["stats"]["HP"]["weight"]+=1

    assert warm.get_role_row(bro,changed) is None
    assert warm.get_role_row(bro,unrelated)["Role"]=="Unrelated"


def test_idless_legacy_rename_does_not_guess_cache_association(
    bro_factory,simple_role
):
    bro=bro_factory()
    original=simple_role(("HP",))
    cache=IncrementalCache(None)
    cache.store_role_row(bro,original,{"Role":original["name"]})
    warm=IncrementalCache(cache.manifest_payload(generated_at="x",source_save="x"))

    assert warm.get_role_row(bro,{**original,"name":"Renamed"}) is None


def manifest_with_downstream(bro, roles, class_cfg):
    state=brother_projection_fingerprint(bro)
    return {
        "schema":"bb-incremental-v1",
        "brothers":{
            "previous":{
                "projection_state_hash":state,
                "roles":{},
                "advisor":{
                    "input_hash":advisor_fingerprint(bro,roles),
                    "engine_version":ADVISOR_ENGINE_VERSION,
                    "role_labels":[{
                        "identity":role.get("id"),
                        "signature":role_fingerprint(role),
                        "name":role["name"],
                    } for role in roles],
                    "result":{"Recommended":{"Stats":["HP","MAtk","MDef"]}},
                },
                "summary":{
                    "input_hash":brother_summary_fingerprint(bro,roles,class_cfg),
                    "engine_version":BROTHER_SUMMARY_ENGINE_VERSION,
                    "result":{"Category":"Use","BrotherID":bro.BrotherID,"Name":bro.Name,
                              "Level":bro.Level,"Background":bro.Background},
                },
            }
        },
    }


def test_classification_change_reuses_advisor_but_not_summary(bro_factory,simple_role):
    bro=bro_factory()
    roles=[simple_role(("HP","MAtk","MDef"))]
    old_cfg={"invest":0.8}
    new_cfg={"invest":0.9}
    cache=IncrementalCache(manifest_with_downstream(bro,roles,old_cfg))

    assert cache.get_summary(bro,roles,new_cfg) is None
    assert cache.get_advisor(bro,roles)=={"Recommended":{"Stats":["HP","MAtk","MDef"]}}
    assert cache.stats.advisor_reused==1


def test_valid_summary_carries_downstream_artifacts_into_new_manifest(bro_factory,simple_role):
    bro=bro_factory()
    roles=[simple_role(("HP","MAtk","MDef"))]
    cfg={"invest":0.8}
    cache=IncrementalCache(manifest_with_downstream(bro,roles,cfg))
    assert cache.get_summary(bro,roles,cfg)["Category"]=="Use"
    new=cache.manifest_payload(generated_at="x",source_save="x.sav")
    entry=next(iter(new["brothers"].values()))
    assert "summary" in entry
    assert "advisor" in entry


def test_summary_and_advisor_remain_independently_validatable(bro_factory,simple_role):
    bro=bro_factory()
    roles=[simple_role(("HP","MAtk","MDef"))]
    cfg={"invest":0.8}
    manifest=manifest_with_downstream(bro,roles,cfg)
    manifest["brothers"]["previous"]["summary"]["result"]["LevelUpAdvice"]={"stale":True}
    cache=IncrementalCache(manifest)

    summary=cache.get_summary(bro,roles,cfg)
    advice=cache.get_advisor(bro,roles)

    assert "LevelUpAdvice" not in summary
    assert advice=={"Recommended":{"Stats":["HP","MAtk","MDef"]}}


def test_valid_intrinsic_summary_composes_recomputed_advisor(
    monkeypatch,bro_factory,simple_role
):
    bro=bro_factory(Level=11)
    roles=[simple_role(("HP","MAtk","MDef"))]
    cfg={"invest":0.8}
    manifest=manifest_with_downstream(bro,roles,cfg)
    manifest["brothers"]["previous"]["advisor"]["input_hash"]="stale"
    expected={"Recommended":{"Stats":["MAtk","MDef","HP"]}}
    monkeypatch.setattr(analysis_module,"advise_levelup",lambda *_args: expected)
    cache=IncrementalCache(manifest)

    result=analysis_module.analyze_brothers([bro],roles,cfg,cache)

    assert result.summaries[0]["LevelUpAdvice"]==expected
    assert cache.stats.summary_reused==1
    assert cache.stats.summary_computed==0
    assert cache.stats.advisor_reused==0
    assert cache.stats.advisor_computed==1


def test_projection_range_schema_change_rejects_old_downstream_artifacts(bro_factory,simple_role):
    bro=bro_factory()
    roles=[simple_role(("HP","MAtk","MDef"))]
    cfg={"invest":0.8}
    manifest=manifest_with_downstream(bro,roles,cfg)
    entry=manifest["brothers"]["previous"]
    entry["summary"]["engine_version"]=BROTHER_SUMMARY_ENGINE_VERSION-1
    cache=IncrementalCache(manifest)

    assert cache.get_summary(bro,roles,cfg) is None
    assert cache.miss_reasons["summary_engine_changed"]==1
    assert cache.get_advisor(bro,roles)=={"Recommended":{"Stats":["HP","MAtk","MDef"]}}


def test_reused_summary_rehydrates_non_projection_display_state(bro_factory,simple_role):
    old=bro_factory(
        Name="Old name", HumanOffset=10, Background="Old background",
        Perks=["Old perk"], Traits=["Old trait"], Injuries=["Cut leg"],
    )
    current=bro_factory(
        Name="Current name", HumanOffset=20, Background="Current background",
        Perks=["Old perk"], Traits=["Old trait"], Injuries=["Fresh wound"],
    )
    roles=[simple_role(("HP","MAtk","MDef"))]
    cfg={"invest":0.8}
    manifest=manifest_with_downstream(old,roles,cfg)
    result=manifest["brothers"]["previous"]["summary"]["result"]
    result.update({
        "Perks":"Old perk", "Traits":"Old trait", "Injuries":"Cut leg",
    })

    summary=IncrementalCache(manifest).get_summary(current,roles,cfg)

    assert summary["BrotherID"]==current.BrotherID
    assert summary["Name"]=="Current name"
    assert summary["Background"]=="Current background"
    assert summary["Perks"]=="Old perk"
    assert summary["Traits"]=="Old trait"
    assert summary["Injuries"]=="Fresh wound"
