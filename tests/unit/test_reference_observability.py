import hashlib
import ssl
import urllib.error

import references.update_references as refs


def test_download_retries_transient_tls_failure_and_reports_recovery(
    monkeypatch, capsys
):
    payload = b"recovered payload"
    attempts = []
    sleeps = []

    def flaky_download(url, timeout):
        attempts.append((url, timeout))
        if len(attempts) == 1:
            raise urllib.error.URLError(ssl.SSLError("temporary handshake failure"))
        return payload

    monkeypatch.setattr(refs, "_download_once", flaky_download)
    monkeypatch.setattr(refs.time, "sleep", sleeps.append)

    result, provenance = refs._download_with_provenance(
        "https://example.invalid/archive.zip",
        12,
        selected_revision="fixed-ref",
    )

    assert result == payload
    assert len(attempts) == 2
    assert sleeps == [refs.DOWNLOAD_RETRY_BACKOFF_SECONDS]
    output = capsys.readouterr().out
    assert "Reference download failed (attempt 1/3)" in output
    assert "Retrying in" in output
    assert "Reference download succeeded (attempt 2/3)" in output


def test_download_does_not_retry_permanent_http_failure(monkeypatch):
    attempts = []

    def missing_download(url, timeout):
        attempts.append((url, timeout))
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(refs, "_download_once", missing_download)
    monkeypatch.setattr(
        refs.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(AssertionError("unexpected retry")),
    )

    try:
        refs._download_with_provenance(
            "https://example.invalid/missing.zip",
            12,
            selected_revision="fixed-ref",
        )
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("expected permanent HTTP failure")

    assert len(attempts) == 1


def test_download_stops_after_bounded_transient_retries(monkeypatch):
    attempts = []
    sleeps = []

    def unavailable_download(url, timeout):
        attempts.append((url, timeout))
        raise urllib.error.HTTPError(url, 503, "Unavailable", {}, None)

    monkeypatch.setattr(refs, "_download_once", unavailable_download)
    monkeypatch.setattr(refs.time, "sleep", sleeps.append)

    try:
        refs._download_with_provenance(
            "https://example.invalid/archive.zip",
            12,
            selected_revision="fixed-ref",
        )
    except urllib.error.HTTPError as exc:
        assert exc.code == 503
    else:
        raise AssertionError("expected exhausted transient failure")

    assert len(attempts) == refs.DOWNLOAD_MAX_ATTEMPTS
    assert sleeps == [
        refs.DOWNLOAD_RETRY_BACKOFF_SECONDS,
        refs.DOWNLOAD_RETRY_BACKOFF_SECONDS * 2,
    ]


def test_download_provenance_records_revision_size_and_checksum(monkeypatch):
    payload = b"deterministic reference payload"
    monkeypatch.setattr(refs, "_download_bytes", lambda url, timeout: payload)

    result, provenance = refs._download_with_provenance(
        "https://example.invalid/archive.zip",
        12,
        selected_revision="fixed-ref",
    )

    assert result == payload
    assert provenance["source"] == "network"
    assert provenance["url"] == "https://example.invalid/archive.zip"
    assert provenance["selected_revision"] == "fixed-ref"
    assert provenance["size_bytes"] == len(payload)
    assert provenance["sha256"] == hashlib.sha256(payload).hexdigest()


def test_cached_reference_status_reports_schemas_paths_and_final_state(
    monkeypatch, tmp_path
):
    paths = {
        "DICTIONARY_OUT": tmp_path / "dictionary.json",
        "BACKGROUNDS_OUT": tmp_path / "backgrounds.json",
        "PERK_EFFECTS_OUT": tmp_path / "perk_effects.json",
        "TRAIT_EFFECTS_OUT": tmp_path / "trait_effects.json",
        "PERMANENT_INJURY_EFFECTS_OUT": tmp_path / "permanent_injury_effects.json",
        "PERK_AUDIT_OUT": tmp_path / "perk_audit.json",
    }
    for attribute, path in paths.items():
        path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(refs, attribute, path)

    for predicate in (
        "reference_dictionary_is_present",
        "background_dictionary_is_present",
        "perk_effect_dictionary_is_present",
        "trait_effect_dictionary_is_present",
        "permanent_injury_effect_dictionary_is_present",
        "perk_audit_is_present",
    ):
        monkeypatch.setattr(refs, predicate, lambda: True)
    monkeypatch.setattr(refs, "build_perk_audit", lambda: {})
    monkeypatch.setattr(
        refs,
        "_download_bytes",
        lambda *args: (_ for _ in ()).throw(AssertionError("unexpected network")),
    )

    status = refs.ensure_references(verbose=False)

    assert status["schema"] == "bbtool.reference_status.v1"
    assert status["reference_schemas"] == refs.REFERENCE_CACHE_SCHEMAS
    assert status["cache_directory"] == str(refs.HERE.resolve())
    assert status["download_sources"] == {}
    assert status["fallback_used"] is False
    assert set(status["final_cache"]) == {
        "dictionary",
        "backgrounds",
        "perks",
        "traits",
        "permanent_injuries",
        "perk_audit",
    }
    assert all(item["exists"] for item in status["final_cache"].values())
    assert all(item["valid"] for item in status["final_cache"].values())
    assert status["final_cache"]["dictionary"]["source"] == "cache"
    assert status["final_cache"]["perk_audit"]["source"] == "cache-derived"
