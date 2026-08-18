from __future__ import annotations

import argparse
import ast
from pathlib import Path


TEST_ROOTS = (Path("tests/unit"), Path("tests/integration"))


def module_name_from_path(path: str) -> str:
    p = Path(path.replace("\\", "/"))
    parts = list(p.with_suffix("").parts)
    if not parts or parts[0] != "bbtool":
        raise ValueError(f"Expected bbtool path, got {path!r}")
    return ".".join(parts)


def imported_modules(test_path: Path) -> set[str]:
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                imported.add(base)
            for alias in node.names:
                if base:
                    imported.add(f"{base}.{alias.name}")
    return imported


def target_module_names(target_path: str, target_kind: str) -> set[str]:
    path = Path(target_path.replace("\\", "/"))
    if target_kind == "module":
        return {module_name_from_path(str(path))}

    names: set[str] = set()
    for py in path.rglob("*.py"):
        if py.name == "__init__.py":
            continue
        names.add(module_name_from_path(str(py)))
    # Importing the package itself is also a direct dependency.
    names.add(module_name_from_path(str(path / "__init__.py")).removesuffix(".__init__"))
    return names


def depends_on_target(imports: set[str], targets: set[str], target_kind: str) -> bool:
    if target_kind == "module":
        target = next(iter(targets))
        # Exact import, "from parent import module", and imports from submodules
        # under a module promoted to a package in the future.
        return any(
            name == target
            or name.startswith(target + ".")
            for name in imports
        )

    prefixes = tuple(t + "." for t in targets)
    return any(name in targets or name.startswith(prefixes) for name in imports)


def find_import_tests(target_path: str, target_kind: str) -> list[str]:
    targets = target_module_names(target_path, target_kind)
    matches: list[str] = []
    for root in TEST_ROOTS:
        if not root.exists():
            continue
        for test in sorted(root.rglob("test_*.py")):
            imports = imported_modules(test)
            if depends_on_target(imports, targets, target_kind):
                matches.append(test.as_posix())
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_path")
    parser.add_argument("target_kind", choices=("module", "package"))
    args = parser.parse_args()
    for path in find_import_tests(args.target_path, args.target_kind):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
