"""The app's package on Lambda holds only part of the context layer, so the backend,
and the data modules it imports, may import only the context layer's modules the
package ships. The repo has all of context/, so nothing else would catch an import
that fails only on Lambda."""

import ast
from pathlib import Path

from deploy.functions import APP_PACKAGE

REPO = Path(__file__).resolve().parents[2]
OURS = ("backend", "data", "context")


def module_path(module: str) -> Path | None:
    """The file of one of our modules, or None for a package's own name or anything
    not ours."""
    path = REPO.joinpath(*module.split("."))
    if path.with_suffix(".py").exists():
        return path.with_suffix(".py")
    if (path / "__init__.py").exists():
        return path / "__init__.py"
    return None


def imports_of(path: Path) -> set[str]:
    """Our modules a file imports, a module imported from a package among them."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
        else:
            continue
        found |= {name for name in names if name.split(".")[0] in OURS}
    return {name for name in found if module_path(name)}


def reached_from_the_backend() -> set[str]:
    """Every module of ours the backend's own modules import, followed through."""
    to_read = [
        f"backend.{path.stem}"
        for path in (REPO / "backend").glob("*.py")
        if path.stem != "__init__"
    ]
    reached: set[str] = set()
    while to_read:
        module = to_read.pop()
        if module in reached:
            continue
        reached.add(module)
        path = module_path(module)
        if path:
            to_read.extend(imports_of(path) - reached)
    return reached


def test_the_backend_imports_only_the_context_modules_its_package_ships():
    shipped = {
        "context." + Path(path).stem
        for path in APP_PACKAGE
        if path.startswith("context/") and path != "context/__init__.py"
    }
    reached = {m for m in reached_from_the_backend() if m.startswith("context.")}
    assert reached == shipped
