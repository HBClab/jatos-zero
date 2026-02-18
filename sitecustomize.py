"""
Ensure the local ``code`` package loads before the stdlib ``code`` module.

Pytest and other tooling may import the standard library's ``code`` module
early in the interpreter lifetime, which prevents our project package from
being importable as ``code.*``.  We bootstrap the package manually at startup
and stash the real stdlib module so the compatibility layer inside
``code/__init__.py`` can continue to proxy InteractiveConsole and friends.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path


def _bootstrap_local_code() -> None:
    repo_root = Path(__file__).resolve().parent
    package_dir = repo_root / "code"
    init_py = package_dir / "__init__.py"
    if not init_py.exists():
        return

    current = sys.modules.get("code")
    if current is not None and getattr(current, "__file__", None) == str(init_py):
        # Already using the project package.
        return

    # Preserve the stdlib module (if already imported) so the package can proxy.
    if current is not None:
        sys.modules.setdefault("code._stdlib_bootstrap", current)

    loader = importlib.machinery.SourceFileLoader("code", str(init_py))
    spec = importlib.util.spec_from_loader(
        "code",
        loader,
        origin=str(init_py),
        submodule_search_locations=[str(package_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(init_py)
    module.__path__ = [str(package_dir)]

    # Replace stdlib entry with the project-aware package and execute it.
    sys.modules["code"] = module
    loader.exec_module(module)


_bootstrap_local_code()
