from pathlib import Path
import os

import pytest

from bbtool.app.output import MAX_RETAINED_OUTPUTS, prune_outputs


def _archive(root: Path, stamp: str, *, stem: str = "quicksave") -> Path:
    path = root / f"{stem}-{stamp}.zip"
    path.write_bytes(path.name.encode("utf-8"))
    return path


@pytest.mark.parametrize("previous_count", [0, 9])
def test_prune_outputs_keeps_all_when_limit_is_not_exceeded(tmp_path, previous_count):
    for index in range(previous_count):
        _archive(tmp_path, f"20260828-{index:06d}")
    current = _archive(tmp_path, "20260829-105043")

    assert prune_outputs(tmp_path, "quicksave") == []
    assert current.exists()
    assert len(list(tmp_path.glob("*.zip"))) == previous_count + 1


def test_prune_outputs_removes_every_excess_archive_and_retains_current(tmp_path):
    archives = [
        _archive(tmp_path, f"20260828-{index:06d}")
        for index in range(21)
    ]
    current = _archive(tmp_path, "20260829-105043")

    deleted = prune_outputs(tmp_path, "quicksave")

    remaining = sorted(tmp_path.glob("quicksave-*.zip"))
    assert len(remaining) == MAX_RETAINED_OUTPUTS
    assert current in remaining
    assert len(deleted) == 12
    assert not archives[0].exists()


def test_prune_outputs_with_ten_previous_removes_only_the_oldest(tmp_path):
    archives = [
        _archive(tmp_path, f"20260828-{index:06d}")
        for index in range(10)
    ]
    current = _archive(tmp_path, "20260829-105043")

    assert prune_outputs(tmp_path, "quicksave") == [archives[0]]
    assert current.exists()
    assert len(list(tmp_path.glob("quicksave-*.zip"))) == 10


def test_prune_outputs_ignores_other_families_unrelated_files_and_directories(tmp_path):
    for index in range(11):
        _archive(tmp_path, f"20260828-{index:06d}")
    other_archive = _archive(tmp_path, "20200101-000000", stem="autosave")
    unrelated = tmp_path / "notes.zip"
    unrelated.write_text("manual", encoding="utf-8")
    directory = tmp_path / "quicksave-20200101-000000.zip"
    directory.mkdir()

    prune_outputs(tmp_path, "quicksave")

    assert other_archive.exists()
    assert unrelated.exists()
    assert directory.is_dir()


def test_prune_outputs_uses_mtime_for_invalid_encoded_timestamp(tmp_path):
    invalid = _archive(tmp_path, "20261340-250000")
    valid = _archive(tmp_path, "20260829-105043")
    os.utime(invalid, (1, 1))

    deleted = prune_outputs(tmp_path, "quicksave", max_outputs=1)

    assert deleted == [invalid]
    assert valid.exists()


def test_prune_outputs_orders_same_timestamp_by_filename_deterministically(tmp_path):
    first = _archive(tmp_path, "20261340-250000")
    second = _archive(tmp_path, "20261341-250000")
    os.utime(first, (1, 1))
    os.utime(second, (1, 1))

    assert prune_outputs(tmp_path, "quicksave", max_outputs=1) == [first]
    assert not first.exists()
    assert second.exists()


def test_prune_outputs_warns_and_preserves_new_output_when_deletion_fails(
    tmp_path, monkeypatch, capsys
):
    old = _archive(tmp_path, "20260828-000000")
    current = _archive(tmp_path, "20260829-105043")
    original_unlink = Path.unlink

    def fail_old(path, *args, **kwargs):
        if path == old:
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_old)

    assert prune_outputs(tmp_path, "quicksave", max_outputs=1) == []
    assert current.exists()
    assert old.exists()
    assert f"Warning: unable to delete obsolete output {old}" in capsys.readouterr().out


def test_prune_outputs_rejects_non_positive_limit(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        prune_outputs(tmp_path, "quicksave", max_outputs=0)
