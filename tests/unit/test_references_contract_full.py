from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import load_reference_dictionary,ref_name


def test_bundled_reference_dictionary_contains_resolvable_entries_and_perk_like_names():
    root=Path(__file__).resolve().parents[2]
    refs=load_reference_dictionary(root)
    assert refs and any(isinstance(v,dict) and v.get('name') for v in refs.values())
    # Perks are resolved through generated reference catalogs; ensure the shipped catalogs exist/nonempty.
    import json
    cat=json.loads((root/'references/perk_catalog.json').read_text(encoding="utf-8"))
    assert cat


def test_reference_fallback_name_for_missing_id():
    assert 'Unknown' in ref_name({},'DEADBEEF')
