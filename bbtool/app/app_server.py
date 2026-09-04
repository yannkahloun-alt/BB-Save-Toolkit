"""Loopback-only HTTP transport for the interactive local application."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from typing import Any
import webbrowser

from .archetype_catalog import (
    ArchetypeCatalogStore,
    CatalogConflictError,
    CatalogValidationError,
)
from .config import load_config
from .health import build_public_analysis_health
from .local_application import ApplicationOperationError, LocalApplication
from .telemetry import TOOLKIT_VERSION
from .user_state import (
    StateConflictError,
    StateLockError,
    StateValidationError,
    UserStateError,
    UserStateStore,
)

API_SCHEMA = "bbtool.local-api.v1"
MAX_REQUEST_BYTES = 256 * 1024
LOOPBACK_HOST = "127.0.0.1"
_STATIC_ROOT = Path(__file__).with_name("static")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def _json_response(status: int, payload: dict[str, Any]) -> HttpResponse:
    return HttpResponse(
        status,
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )


def _static_response(name: str, content_type: str) -> HttpResponse:
    """Serve one fixed application asset; request paths never map to disk."""
    return HttpResponse(200, (_STATIC_ROOT / name).read_bytes(), content_type)


class LocalApplicationApi:
    """Framework-free request dispatcher, directly exercised by in-process tests."""

    def __init__(self, application: LocalApplication, *, origin: str, token: str | None = None):
        self.application = application
        self.origin = origin
        self.token = token or secrets.token_urlsafe(32)

    def handle(
        self,
        method: str,
        target: str,
        headers: Mapping[str, str] | None = None,
        body: bytes = b"",
    ) -> HttpResponse:
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        path = target.split("?", 1)[0]
        try:
            self._validate_host(headers)
            if method == "GET" and path == "/":
                return _static_response("index.html", "text/html; charset=utf-8")
            if method == "GET" and path == "/app.css":
                return _static_response("app.css", "text/css; charset=utf-8")
            if method == "GET" and path == "/app.js":
                return _static_response("app.js", "text/javascript; charset=utf-8")
            if method == "GET" and path == "/api/v1/session":
                return self._ok({"token": self.token})
            if method == "GET" and path == "/api/v1/health":
                return self._ok({
                    "status": "ok", "toolkit_version": TOOLKIT_VERSION,
                    "api_schema": API_SCHEMA, "bind": LOOPBACK_HOST,
                })
            if method == "GET" and path == "/api/v1/shell":
                return self._ok(self._shell_state())
            if method == "GET" and path == "/api/v1/followed-save":
                return self._ok(self.application.followed_save())
            if method == "GET" and path == "/api/v1/archetypes":
                return self._ok(self.application.effective_archetypes())
            if method == "GET" and path == "/api/v1/archetypes/export":
                return self._ok(self.application.export_archetypes())
            assigned_prefix = "/api/v1/assigned-builds/"
            if method == "GET" and path.startswith(assigned_prefix):
                parts = path[len(assigned_prefix):].split("/")
                if len(parts) != 2:
                    raise ApplicationOperationError("invalid_request", "assigned-build read requires campaign and entity tokens")
                return self._ok(self.application.assigned_build(
                    self._integer_text(parts[0], "campaign identity"),
                    self._positive_integer(parts[1], "native entity token"),
                ))
            if method == "GET" and path == "/api/v1/analysis/result":
                return self._ok(self.application.last_result())
            if method == "GET" and path.startswith("/api/v1/analysis/jobs/"):
                job_id = self._positive_integer(path.rsplit("/", 1)[-1], "job id")
                return self._ok(self.application.analysis_job(job_id))
            if method == "GET":
                return self._error(404, "not_found", "endpoint was not found")

            payload = self._mutation_payload(method, headers, body)
            if path == "/api/v1/followed-save/select":
                self._exact_keys(payload, {"path", "expected_revision"}, {"auto_refresh"})
                result = self.application.select_followed_save(
                    payload["path"],
                    expected_revision=self._revision(payload),
                    auto_refresh=payload.get("auto_refresh"),
                )
                return self._ok(result)
            if path == "/api/v1/followed-save/forget":
                self._exact_keys(payload, {"expected_revision"})
                return self._ok(self.application.forget_followed_save(
                    expected_revision=self._revision(payload)
                ))
            if path == "/api/v1/analysis/jobs":
                self._exact_keys(payload, {"expected_preferences_revision"})
                revision = self._integer(payload["expected_preferences_revision"], "expected_preferences_revision")
                return self._ok(self.application.request_analysis(
                    expected_preferences_revision=revision
                ), status=202)
            prefix = "/api/v1/archetypes/"
            if path.startswith(prefix):
                operation = path[len(prefix):].replace("-", "_")
                self._validate_archetype_command(operation, payload)
                return self._ok(self.application.mutate_archetypes(operation, payload))
            assigned_prefix = "/api/v1/assigned-builds/"
            if path.startswith(assigned_prefix):
                operation = path[len(assigned_prefix):].replace("-", "_")
                self._validate_assigned_build_command(operation, payload)
                return self._ok(self.application.mutate_assigned_build(operation, payload))
            return self._error(404, "not_found", "endpoint was not found")
        except ApplicationOperationError as exc:
            status = {
                "job_not_found": 404,
                "not_found": 404,
                "method_not_allowed": 405,
                "untrusted_origin": 403,
                "invalid_session": 403,
                "invalid_host": 403,
                "unsupported_media_type": 415,
                "request_too_large": 413,
            }.get(exc.code, 422)
            return self._error(status, exc.code, exc.message, details=exc.details)
        except StateConflictError as exc:
            return self._error(409, "state_revision_conflict", str(exc))
        except CatalogConflictError as exc:
            return self._error(409, "catalog_conflict", str(exc))
        except (CatalogValidationError, StateValidationError, ValueError, KeyError) as exc:
            details = list(exc.errors) if isinstance(exc, CatalogValidationError) else None
            return self._error(422, "validation_failed", str(exc), details=details)
        except StateLockError as exc:
            return self._error(503, "state_lock_unavailable", str(exc))
        except UserStateError as exc:
            return self._error(500, "user_state_failed", str(exc))
        except Exception:
            # Keep the bounded service alive without reflecting private internal
            # payloads or filesystem details to the browser.
            return self._error(500, "internal_error", "the application operation failed")

    def _shell_state(self) -> dict[str, Any]:
        """Compose a bounded shell snapshot without rebuilding analytical data."""
        followed_save = self.application.followed_save()
        desired_job_id = self.application.coordinator.desired_job_id
        active_job = None
        if desired_job_id is not None:
            try:
                # The authoritative job read also performs the existing
                # publication-persistence bookkeeping when a worker completes.
                active_job = self.application.analysis_job(desired_job_id)
            except ApplicationOperationError as exc:
                if exc.code != "job_not_found":
                    raise

        publication = self.application.coordinator.last_success
        analysis_health = None
        if publication is None:
            result_status = {
                "available": False,
                "freshness": followed_save.get(
                    "freshness", {"status": "unavailable"}
                ),
            }
        else:
            diagnostics = getattr(publication.result, "diagnostics", {}) or {}
            analysis_health = build_public_analysis_health(
                diagnostics.get("run_health", {})
            )
            freshness = {
                "status": (
                    "current"
                    if publication.job_id == desired_job_id
                    else "stale"
                ),
                "generation": publication.generation,
                "represented_source_fingerprint": publication.source_fingerprint,
                "represented_configuration_fingerprints": dict(
                    publication.configuration_fingerprints
                ),
                "artifact_signatures": dict(publication.artifact_signatures),
            }
            watcher = followed_save.get("freshness", {})
            desired_source = watcher.get("desired_source_fingerprint")
            if (
                desired_source is not None
                and desired_source != publication.source_fingerprint
            ):
                freshness["status"] = "stale"
                freshness["reason"] = "selected_save_content_changed"
            elif watcher.get("status") in {
                "detected", "stabilizing", "queued", "analyzing",
                "failed", "unavailable",
            }:
                freshness["status"] = watcher["status"]
                if "reason" in watcher:
                    freshness["reason"] = watcher["reason"]
            result_status = {"available": True, "freshness": freshness}

        return {
            "followed_save": followed_save,
            "result": result_status,
            "analysis_health": analysis_health,
            "active_job": active_job,
        }

    def _validate_host(self, headers: Mapping[str, str]) -> None:
        authority = self.origin.split("//", 1)[1]
        if headers.get("host") != authority:
            raise ApplicationOperationError("invalid_host", "request Host is not the local application")

    def _mutation_payload(
        self, method: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, Any]:
        if method != "POST":
            raise ApplicationOperationError("method_not_allowed", "only POST is allowed for mutations")
        if headers.get("origin") != self.origin:
            raise ApplicationOperationError("untrusted_origin", "mutation Origin is not trusted")
        if not secrets.compare_digest(headers.get("x-bbst-session", ""), self.token):
            raise ApplicationOperationError("invalid_session", "mutation session capability is invalid")
        if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ApplicationOperationError("unsupported_media_type", "mutations require application/json")
        if len(body) > MAX_REQUEST_BYTES:
            raise ApplicationOperationError("request_too_large", "request body exceeds the limit")
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApplicationOperationError("invalid_json", "request body is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ApplicationOperationError("invalid_request", "request body must be a JSON object")
        return value

    @staticmethod
    def _exact_keys(payload: dict, required: set[str], optional: set[str] | None = None) -> None:
        allowed = required | (optional or set())
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - allowed)
        if missing or extra:
            raise ApplicationOperationError(
                "invalid_request_shape",
                "request fields do not match the operation",
                details={"missing": missing, "unexpected": extra},
            )

    def _validate_archetype_command(self, operation: str, payload: dict) -> None:
        shapes = {
            "set_override": ({"id", "patch", "expected_revision"}, set()),
            "set_disabled": ({"id", "disabled", "expected_revision"}, set()),
            "reset_base": ({"id", "expected_revision"}, set()),
            "reset_override": ({"id", "expected_revision"}, set()),
            "create_custom": ({"definition", "expected_revision"}, set()),
            "edit_custom": ({"id", "definition", "expected_revision"}, set()),
            "duplicate": ({"id", "expected_revision"}, {"name"}),
            "delete_custom": ({"id", "expected_revision"}, set()),
            "import": ({"document", "expected_revision"}, {"merge"}),
        }
        if operation not in shapes:
            raise ApplicationOperationError("unknown_operation", "unknown archetype operation")
        required, optional = shapes[operation]
        self._exact_keys(payload, required, optional)
        payload["expected_revision"] = self._revision(payload)
        if "id" in payload and not isinstance(payload["id"], str):
            raise ApplicationOperationError("invalid_request", "id must be a string")
        if "disabled" in payload and not isinstance(payload["disabled"], bool):
            raise ApplicationOperationError("invalid_request", "disabled must be boolean")
        if "merge" in payload and not isinstance(payload["merge"], bool):
            raise ApplicationOperationError("invalid_request", "merge must be boolean")
        if "patch" in payload and not isinstance(payload["patch"], dict):
            raise ApplicationOperationError("invalid_request", "patch must be an object")
        if "definition" in payload and not isinstance(payload["definition"], dict):
            raise ApplicationOperationError("invalid_request", "definition must be an object")
        if "document" in payload and not isinstance(payload["document"], str):
            raise ApplicationOperationError("invalid_request", "document must be a string")

    def _validate_assigned_build_command(self, operation: str, payload: dict) -> None:
        identity = {"campaign_identity", "native_entity_token", "expected_revision"}
        shapes = {
            "assign": (identity | {"build_identity"}, set()),
            "change": (identity | {"build_identity"}, set()),
            "acknowledge": (identity | {"build_identity"}, set()),
            "clear": (identity, set()),
            "clear_campaign": ({"campaign_identity", "expected_revision"}, set()),
        }
        if operation not in shapes:
            raise ApplicationOperationError("unknown_operation", "unknown assigned-build operation")
        required, optional = shapes[operation]
        self._exact_keys(payload, required, optional)
        payload["expected_revision"] = self._revision(payload)
        payload["campaign_identity"] = self._integer(payload["campaign_identity"], "campaign_identity")
        if "native_entity_token" in payload:
            token = self._integer(payload["native_entity_token"], "native_entity_token")
            if token == 0 or token > 0xFFFFFFFF:
                raise ApplicationOperationError("invalid_request", "native_entity_token must be a non-zero unsigned 32-bit integer")
            payload["native_entity_token"] = token
        if "build_identity" in payload and not isinstance(payload["build_identity"], str):
            raise ApplicationOperationError("invalid_request", "build_identity must be a string")

    def _revision(self, payload: dict) -> int:
        return self._integer(payload["expected_revision"], "expected_revision")

    @staticmethod
    def _integer(value: object, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ApplicationOperationError("invalid_request", f"{name} must be a non-negative integer")
        return value

    @classmethod
    def _positive_integer(cls, value: str, name: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ApplicationOperationError("invalid_request", f"{name} must be a positive integer") from exc
        if parsed <= 0:
            raise ApplicationOperationError("invalid_request", f"{name} must be a positive integer")
        return parsed

    @staticmethod
    def _integer_text(value: str, name: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ApplicationOperationError("invalid_request", f"{name} must be a non-negative integer") from exc
        if parsed < 0:
            raise ApplicationOperationError("invalid_request", f"{name} must be a non-negative integer")
        return parsed

    @staticmethod
    def _ok(data: Any, *, status: int = 200) -> HttpResponse:
        return _json_response(status, {"schema": API_SCHEMA, "data": data, "error": None})

    @staticmethod
    def _error(status: int, code: str, message: str, *, details: Any = None) -> HttpResponse:
        error = {"code": code, "message": message}
        if details is not None:
            error["details"] = details
        return _json_response(status, {"schema": API_SCHEMA, "data": None, "error": error})


def _handler(api: LocalApplicationApi):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._dispatch(b"")

        def do_POST(self) -> None:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError:
                length = MAX_REQUEST_BYTES + 1
            body = self.rfile.read(min(max(length, 0), MAX_REQUEST_BYTES + 1))
            self._dispatch(body)

        def _dispatch(self, body: bytes) -> None:
            response = api.handle(self.command, self.path, dict(self.headers), body)
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'")
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            # Deliberately omit request bodies, selected paths, state and save data.
            return

    return Handler


def serve_local_application(
    *, port: int = 0, open_browser: bool = False, state_root: Path | None = None
) -> None:
    """Run the interactive application on IPv4 loopback only."""
    config_root = Path(__file__).resolve().parents[2] / "config"
    config = load_config(config_root / "archetypes.json", config_root / "classification.json")
    store = UserStateStore(state_root)
    application = LocalApplication(
        store, ArchetypeCatalogStore(store, config.roles),
        config.classification,
    )
    application.start_save_watcher()
    server = ThreadingHTTPServer((LOOPBACK_HOST, port), BaseHTTPRequestHandler)
    actual_port = server.server_address[1]
    origin = f"http://{LOOPBACK_HOST}:{actual_port}"
    api = LocalApplicationApi(application, origin=origin)
    server.RequestHandlerClass = _handler(api)
    print(f"Local application: {origin}")
    if open_browser:
        webbrowser.open(origin)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        application.close()


__all__ = [
    "API_SCHEMA", "LOOPBACK_HOST", "MAX_REQUEST_BYTES", "HttpResponse",
    "LocalApplicationApi", "serve_local_application",
]
