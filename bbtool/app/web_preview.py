"""Static, presentation-only previews built from approved public datasets."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
import re
import shutil

from ..html_report import render_html_report
from .output import PACKAGE_ROOT
from .render_only import load_render_dataset


_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_TABS = frozenset({"roster", "levelup", "management", "recruits"})


class PreviewCatalogError(ValueError):
    """The preview catalog is unsafe or incompatible."""


@dataclass(frozen=True)
class PreviewMetadata:
    source_label: str
    source_sha: str
    generated_at: str


def _load_catalog(path: Path) -> list[dict]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreviewCatalogError(f"Invalid preview catalog {path}: {exc}") from exc
    scenarios = catalog.get("scenarios") if isinstance(catalog, dict) else None
    if not isinstance(scenarios, list) or not scenarios:
        raise PreviewCatalogError("Preview catalog must contain a non-empty scenarios array")
    return scenarios


def _preview_banner(metadata: PreviewMetadata, scenario: str, schema: str) -> str:
    return (
        '<aside class="preview-metadata" role="note">'
        '<strong>Render-only preview</strong>'
        f'<span>Source: {escape(metadata.source_label)}</span>'
        f'<span>Commit: <code>{escape(metadata.source_sha)}</code></span>'
        f'<span>Fixture: {escape(scenario)}</span>'
        f'<span>Contract: <code>{escape(schema)}</code></span>'
        f'<span>Generated: {escape(metadata.generated_at)}</span>'
        '</aside>'
    )


def _activate_tab(html: str, tab: str) -> str:
    if tab == "roster":
        return html
    html = html.replace(
        'class="tab-button active" data-tab-button="roster"',
        'class="tab-button" data-tab-button="roster"',
        1,
    ).replace(
        'id="tab-roster" class="tab-panel active"',
        'id="tab-roster" class="tab-panel"',
        1,
    )
    button_pattern = re.compile(
        rf'class="(?P<classes>[^"]*\btab-button\b[^"]*)" '
        rf'data-tab-button="{re.escape(tab)}"'
    )
    html, replacements = button_pattern.subn(
        lambda match: (
            f'class="{match.group("classes")} active" data-tab-button="{tab}"'
        ),
        html,
        count=1,
    )
    if replacements != 1:
        raise PreviewCatalogError(f"Rendered report does not expose tab {tab!r}")
    html = html.replace(
        f'id="tab-{tab}" class="tab-panel"',
        f'id="tab-{tab}" class="tab-panel active"',
        1,
    )
    return html


def build_web_previews(
    catalog_path: Path,
    output_root: Path,
    metadata: PreviewMetadata,
) -> tuple[Path, ...]:
    """Validate approved datasets and emit static interactive preview pages."""
    catalog_path = catalog_path.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    built = []
    seen = set()
    for index, scenario in enumerate(_load_catalog(catalog_path)):
        if not isinstance(scenario, dict):
            raise PreviewCatalogError(f"Scenario {index} must be an object")
        name = scenario.get("name")
        tab = scenario.get("initial_tab", "roster")
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name) or name in seen:
            raise PreviewCatalogError(f"Scenario {index} has an unsafe or duplicate name")
        if tab not in _TABS:
            raise PreviewCatalogError(f"Scenario {name!r} has unsupported initial_tab {tab!r}")
        relative = Path(str(scenario.get("dataset", "")))
        if not relative.name or relative.is_absolute() or ".." in relative.parts:
            raise PreviewCatalogError(f"Scenario {name!r} has an unsafe dataset path")
        dataset_path = (catalog_path.parent / relative).resolve()
        if catalog_path.parent not in dataset_path.parents:
            raise PreviewCatalogError(f"Scenario {name!r} escapes the catalog directory")
        dataset = load_render_dataset(dataset_path)
        html = render_html_report(
            Path(name), dataset.bros, dataset.fits, dataset.summaries,
            dataset.roles, dataset.classification,
            generated_at=metadata.generated_at, recruits=dataset.recruits,
        )
        banner = _preview_banner(metadata, name, dataset.manifest["schema"])
        html = html.replace("<body>", f"<body>{banner}", 1)
        html = _activate_tab(html, tab)
        target = output_root / name
        target.mkdir(parents=True, exist_ok=False)
        (target / "index.html").write_text(html, encoding="utf-8")
        shutil.copy2(PACKAGE_ROOT / "report.css", target / "report.css")
        shutil.copy2(PACKAGE_ROOT / "report.js", target / "report.js")
        built.append(target)
        seen.add(name)
    return tuple(built)
