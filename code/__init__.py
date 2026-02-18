"""
Compatibility helpers for the local ``code`` package.

The project reuses the stdlib module name ``code`` for its own package,
which can break third-party imports that expect the built-in module
(``from code import InteractiveConsole`` for example).  We proxy those
requests back to the real stdlib module so that our package can coexist
with prebuilt libraries that rely on it.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import sysconfig
from functools import lru_cache
from types import ModuleType
from typing import Any, Iterable, Set

__all__: list[str] = []

_PACKAGE_DIR = os.path.dirname(__file__)
_STDLIB_BOOTSTRAP_KEY = "code._stdlib_bootstrap"


def _register_package_path() -> None:
    """
    Guarantee that sibling modules remain importable via absolute paths
    even when the project is executed outside of an installed environment.
    """
    project_root = os.path.dirname(_PACKAGE_DIR)
    candidates = [project_root, _PACKAGE_DIR]
    for path in candidates:
        if path and path not in sys.path:
            sys.path.insert(0, path)


_register_package_path()


def _stdlib_candidates() -> Iterable[str]:
    """Yield plausible filesystem locations for the stdlib ``code`` module."""
    seen: Set[str] = set()
    for key in ("stdlib", "platstdlib"):
        path = sysconfig.get_path(key)
        if not path:
            continue
        candidate = os.path.join(path, "code.py")
        if candidate not in seen and os.path.exists(candidate):
            seen.add(candidate)
            yield candidate


@lru_cache(maxsize=1)
def _load_stdlib_code() -> ModuleType | None:
    """Import the stdlib ``code`` module from disk without clobbering this package."""
    # If sitecustomize stashed the original module, prefer that.
    existing = sys.modules.get(_STDLIB_BOOTSTRAP_KEY)
    if existing:
        return existing

    for module_path in _stdlib_candidates():
        spec = importlib.util.spec_from_file_location("code.__stdlib", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules.setdefault("code._stdlib", module)
            return module
    return None


def __getattr__(name: str) -> Any:
    """
    Lazily proxy missing attributes to the stdlib ``code`` module.

    This keeps ``from code import InteractiveConsole`` working even though
    the project shadows the module name with a package.
    """
    stdlib_module = _load_stdlib_code()
    if stdlib_module and hasattr(stdlib_module, name):
        value = getattr(stdlib_module, name)
        # Cache the attribute locally so repeated lookups are fast.
        globals()[name] = value
        return value
    raise AttributeError(f"module 'code' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Combine local attributes with any public names from the stdlib module."""
    names = set(globals())
    stdlib_module = _load_stdlib_code()
    if stdlib_module:
        names.update(attr for attr in dir(stdlib_module) if not attr.startswith("_"))
    return sorted(names)


# expose project submodules through attribute access
def _expose_submodules() -> None:
    submodules = [
        "main_handler",
        "data_processing",
        "transfer.path_logic",
    ]
    for dotted in submodules:
        short = dotted.split(".")[0]
        try:
            module = importlib.import_module(f"{__name__}.{dotted}")
        except ModuleNotFoundError:
            continue
        globals()[short] = importlib.import_module(f"{__name__}.{short}")
        sys.modules.setdefault(f"{__name__}.{short}", globals()[short])
        sys.modules.setdefault(f"{__name__}.{dotted}", module)


_expose_submodules()


# Populate __all__ with any names proxied from the stdlib module so
# star-import behaviour mirrors the original as closely as possible.
stdlib_module = _load_stdlib_code()
if stdlib_module:
    proxy_names = [attr for attr in dir(stdlib_module) if not attr.startswith("_")]
    __all__.extend(sorted(proxy_names))
