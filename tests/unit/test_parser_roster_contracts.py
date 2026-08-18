import pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import parse_roster,DuplicateBrotherNameError

def test_empty_save_fails_controlled(tmp_path):
    p=tmp_path/'empty.sav'; p.write_bytes(b'')
    with pytest.raises(RuntimeError,match='signature'): parse_roster(p)
def test_duplicate_brother_error_type_exists(): assert issubclass(DuplicateBrotherNameError,RuntimeError)
