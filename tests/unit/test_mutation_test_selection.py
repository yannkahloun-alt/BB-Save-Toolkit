from pathlib import Path

from tests.mutation.select_tests import (
    depends_on_target,
    imported_modules,
    module_name_from_path,
)


def test_module_name_from_path():
    assert module_name_from_path("bbtool/levelup_advisor.py") == "bbtool.levelup_advisor"
    assert module_name_from_path(r"bbtool\projection\perks.py") == "bbtool.projection.perks"


def test_imported_modules_captures_common_direct_import_forms(tmp_path: Path):
    test_file = tmp_path / "test_x.py"
    test_file.write_text(
        "import bbtool.levelup_advisor\n"
        "from bbtool import levelup_advisor\n"
        "from bbtool.levelup_advisor import recommend\n",
        encoding="utf-8",
    )
    imports = imported_modules(test_file)
    assert "bbtool.levelup_advisor" in imports
    assert "bbtool.levelup_advisor.recommend" in imports


def test_module_dependency_matching_is_exact_not_sibling_based():
    target = {"bbtool.levelup_advisor"}
    assert depends_on_target({"bbtool.levelup_advisor"}, target, "module")
    assert depends_on_target({"bbtool.levelup_advisor.recommend"}, target, "module")
    assert not depends_on_target({"bbtool.projection.trajectory"}, target, "module")
