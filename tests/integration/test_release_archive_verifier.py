import pytest
pytestmark=pytest.mark.integration
from tools.verify_release_zip import audit_members

def test_release_archive_contract_accepts_clean_manifest():
    assert audit_members(['pkg/config/archetypes.json','pkg/bbtool/x.py','pkg/tests/test_x.py'])==[]

def test_release_archive_contract_rejects_caches_pyc_and_competing_archetypes():
    issues=audit_members(['pkg/config/archetypes.json','pkg/archetypes_old.json','pkg/__pycache__/x.pyc','pkg/.pytest_cache/a'])
    assert any('cache artifact' in x for x in issues) and any('archetype configs' in x for x in issues)
