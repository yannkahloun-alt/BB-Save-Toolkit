from types import SimpleNamespace
from bbtool.incremental.cache import IncrementalCache
from bbtool.incremental.fingerprint import ROLE_PROJECTION_ENGINE_VERSION, brother_projection_fingerprint, role_fingerprint, stable_hash
from bbtool.incremental.manifest import find_previous_manifest, write_manifest

def test_stable_hash_is_order_independent():
    assert stable_hash({"a":1,"b":2})==stable_hash({"b":2,"a":1})

def test_projection_fingerprint_ignores_name_and_local_offset(bro_factory):
    assert brother_projection_fingerprint(bro_factory(Name="A",HumanOffset=1))==brother_projection_fingerprint(bro_factory(Name="B",HumanOffset=999))

def test_projection_fingerprint_changes_for_relevant_state(bro_factory):
    assert brother_projection_fingerprint(bro_factory(HP=60))!=brother_projection_fingerprint(bro_factory(HP=61))

def _manifest(bro,role,result):
    state=brother_projection_fingerprint(bro)
    return {"schema":"bb-incremental-v1","brothers":{state:{"projection_state_hash":state,"roles":{role["name"]:{"role_hash":role_fingerprint(role),"engine_version":ROLE_PROJECTION_ENGINE_VERSION,"result":result}}}}}

def test_exact_role_reuse_and_role_invalidation(bro_factory,simple_role):
    bro=bro_factory();role=simple_role(("HP","Fatigue"));result={"Role":role["name"],"ProjectedFitPct":75.0}
    cache=IncrementalCache(_manifest(bro,role,result));row=cache.get_role_row(bro,role);assert row["Role"]==result["Role"] and row["ProjectedFitPct"]==75.0
    changed={**role,"stats":{k:dict(v) for k,v in role["stats"].items()}};changed["stats"]["HP"]["weight"]=9.0
    assert cache.get_role_row(bro,changed) is None

def test_changed_brother_is_not_reused(bro_factory,simple_role):
    old=bro_factory(HP=60);new=bro_factory(HP=61);role=simple_role(("HP",));cache=IncrementalCache(_manifest(old,role,{"Role":role["name"]}))
    assert cache.get_role_row(new,role) is None

def test_ambiguous_identical_state_is_not_reused(bro_factory,simple_role):
    bro=bro_factory();role=simple_role(("HP",));state=brother_projection_fingerprint(bro)
    entry={"projection_state_hash":state,"roles":{role["name"]:{"role_hash":role_fingerprint(role),"engine_version":ROLE_PROJECTION_ENGINE_VERSION,"result":{"Role":role["name"]}}}}
    cache=IncrementalCache({"schema":"bb-incremental-v1","brothers":{"x":entry,"y":dict(entry)}});assert cache.get_role_row(bro,role) is None;assert cache.stats.ambiguous_states==1

def test_manifest_atomic_write_and_discovery(tmp_path):
    root=tmp_path/"output";run=root/"run";run.mkdir(parents=True);ws=SimpleNamespace(root=run,base="save-1");payload={"schema":"bb-incremental-v1","brothers":{}}
    path=write_manifest(ws,payload);found_path,found=find_previous_manifest(root);assert found_path==path;assert found==payload

def test_corrupt_manifest_is_ignored(tmp_path):
    root=tmp_path/"output";root.mkdir();(root/"bad-incremental-manifest.json").write_text("{",encoding="utf-8");assert find_previous_manifest(root)==(None,None)


def test_manifest_keeps_duplicate_states_as_separate_brothers(bro_factory,simple_role):
    a=bro_factory(Name="Twin",HumanOffset=10)
    b=bro_factory(Name="Twin",HumanOffset=20)
    role=simple_role(("HP",))
    cache=IncrementalCache(None)
    cache.store_role_row(a,role,{"Role":role["name"]})
    cache.store_role_row(b,role,{"Role":role["name"]})
    payload=cache.manifest_payload(generated_at="x",source_save="x.sav")
    assert len(payload["brothers"])==2
    assert {v["projection_state_hash"] for v in payload["brothers"].values()}=={brother_projection_fingerprint(a)}
    next_cache=IncrementalCache(payload)
    assert next_cache.get_role_row(a,role) is None
    assert next_cache.stats.ambiguous_states==1


def test_manifest_from_other_save_slot_is_not_reused(tmp_path):
    root=tmp_path/"output";run=root/"run";run.mkdir(parents=True);ws=SimpleNamespace(root=run,base="save-1")
    a=tmp_path/"a.sav";b=tmp_path/"b.sav";a.write_bytes(b"a");b.write_bytes(b"b")
    write_manifest(ws,{"schema":"bb-incremental-v1","source_save_path":str(a.resolve()),"brothers":{}})
    assert find_previous_manifest(root,source_save=b)==(None,None)


def test_reused_role_row_is_rehydrated_with_current_display_identity(bro_factory,simple_role):
    old=bro_factory(Name="Old",HumanOffset=10);new=bro_factory(Name="New",HumanOffset=20);role=simple_role(("HP",))
    result={"BrotherID":old.BrotherID,"Name":old.Name,"Level":old.Level,"Background":old.Background,"Role":role["name"]}
    cache=IncrementalCache(_manifest(old,role,result));row=cache.get_role_row(new,role)
    assert row["BrotherID"]==new.BrotherID and row["Name"]=="New"

def test_summary_reuse_requires_same_roles_and_classification(bro_factory,simple_role):
    bro=bro_factory();role=simple_role(("HP",));cfg={"threshold":1};first=IncrementalCache(None)
    first.store_summary(bro,[role],cfg,{"BrotherID":bro.BrotherID,"Name":bro.Name,"Level":bro.Level,"Background":bro.Background,"Category":"Use"})
    payload=first.manifest_payload(generated_at="x",source_save="x",source_save_path="x")
    second=IncrementalCache(payload);assert second.get_summary(bro,[role],cfg)["Category"]=="Use"
    assert second.get_summary(bro,[role],{"threshold":2}) is None


def test_projection_fingerprint_changes_when_trait_identity_changes(bro_factory):
    from bbtool.incremental.fingerprint import brother_projection_fingerprint
    a = bro_factory(TraitIDs=[], Traits=[])
    b = bro_factory(TraitIDs=["trait.strong"], Traits=["Strong"])
    assert brother_projection_fingerprint(a) != brother_projection_fingerprint(b)
