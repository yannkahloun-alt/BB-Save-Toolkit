from pathlib import Path


SCRIPT = Path("run_mutation.ps1").read_text(encoding="utf-8")


def test_all_is_module_by_module_not_monolithic():
    assert "function Invoke-AllMutationTargets" in SCRIPT
    assert 'Where-Object { $_.Kind -eq "module" }' in SCRIPT
    assert '"-Target", $item.Name' in SCRIPT
    assert '"-AllChild"' in SCRIPT


def test_all_reselects_dependencies_per_module():
    assert "Get-AutomaticSelectedTests $item.Path $item.Kind" in SCRIPT
    assert "-Tests cannot be combined with -Target all/-All" in SCRIPT


def test_all_continues_and_aggregates_failures():
    assert '$failed += $item.Name' in SCRIPT
    assert 'continuing.' in SCRIPT
    assert 'Failed targets' in SCRIPT


def test_time_scale_and_history_contract():
    assert 'mutation-history.json' in SCRIPT
    assert 'if ($Seconds -lt 3600) { return "minutes" }' in SCRIPT
    assert 'if ($Seconds -lt 86400) { return "hours" }' in SCRIPT
    assert 'return "days"' in SCRIPT
    assert 'elapsed_seconds' in SCRIPT
    assert 'last_run' in SCRIPT


def test_list_targets_shows_scale_basis():
    assert 'scale={4,-7} ({5})' in SCRIPT
    assert '"measured"' in SCRIPT
    assert '"estimated"' in SCRIPT
