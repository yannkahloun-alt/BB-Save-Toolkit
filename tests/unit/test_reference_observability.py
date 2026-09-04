import hashlib
import re
import ssl
import urllib.error

import references.update_references as refs


def test_external_reference_sources_are_explicit_immutable_commits():
    assert set(refs.REFERENCE_SOURCES) == {
        "bbedit_dictionary",
        "vanilla_scripts",
    }
    for source in refs.REFERENCE_SOURCES.values():
        revision = source["immutable_revision"]
        assert re.fullmatch(r"[0-9a-f]{40}", revision)
        assert revision in source["requested_url"]
        assert "refs/heads/" not in source["requested_url"]
        assert source["upstream_source"].startswith("https://github.com/")
        assert source["generated_references"]


def test_same_configured_revision_always_requests_same_upstream_object(monkeypatch):
    requested = []
    monkeypatch.setattr(
        refs,
        "_download_bytes",
        lambda url, timeout: requested.append((url, timeout)) or b"same bytes",
    )

    first_bytes, first = refs._download_reference_source("vanilla_scripts", 45)
    second_bytes, second = refs._download_reference_source("vanilla_scripts", 45)

    assert first_bytes == second_bytes
    assert requested[0][0] == requested[1][0]
    assert first["immutable_revision"] == second["immutable_revision"]
    assert first["requested_url"] == second["requested_url"]
    assert first["sha256"] == second["sha256"]


def test_missing_pinned_revision_names_exact_source_without_fallback(monkeypatch):
    requested = []

    def missing(url, timeout):
        requested.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(refs, "_download_bytes", missing)

    try:
        refs._download_reference_source("bbedit_dictionary", 20)
    except RuntimeError as exc:
        source = refs.REFERENCE_SOURCES["bbedit_dictionary"]
        message = str(exc)
        assert "bbedit_dictionary" in message
        assert source["immutable_revision"] in message
        assert source["requested_url"] in message
    else:
        raise AssertionError("expected missing immutable revision to fail")

    assert requested == [refs.BBEDIT_DICTIONARY_URL]


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


def test_source_download_provenance_is_complete(monkeypatch):
    payload = b"deterministic source"
    monkeypatch.setattr(refs, "_download_bytes", lambda url, timeout: payload)

    _, provenance = refs._download_reference_source("bbedit_dictionary", 20)

    configured = refs.REFERENCE_SOURCES["bbedit_dictionary"]
    assert provenance["source_name"] == "bbedit_dictionary"
    assert provenance["upstream_source"] == configured["upstream_source"]
    assert provenance["immutable_revision"] == configured["immutable_revision"]
    assert provenance["requested_url"] == configured["requested_url"]
    assert provenance["selected_revision"] == configured["immutable_revision"]
    assert provenance["url"] == configured["requested_url"]
    assert provenance["sha256"] == hashlib.sha256(payload).hexdigest()
    assert provenance["generated_reference_schemas"] == {
        "dictionary": refs.REFERENCE_CACHE_SCHEMAS["dictionary"]
    }


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
    assert status["configured_sources"] == {
        name: refs._configured_source_provenance(name)
        for name in refs.REFERENCE_SOURCES
    }
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
