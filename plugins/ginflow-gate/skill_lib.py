"""Single lookup for Ginflow core modules in `skills/ginflow/lib`.

Repo checkout first, then the installed skill under `~/.agents/skills`.
Each module loads once and is shared by gate, routing, block routing, and publish.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


def _lib_dir() -> Path:
    real_home = Path(os.environ.get("HERMES_REAL_HOME", str(Path.home()))).expanduser().resolve()
    candidates = (
        Path(__file__).resolve().parents[2] / "skills/ginflow/lib",
        real_home / ".agents/skills/ginflow/lib",
    )
    for candidate in candidates:
        if (candidate / "harness_core.py").is_file():
            return candidate
    raise ImportError("unable to locate Ginflow skill lib; checked: " + ", ".join(map(str, candidates)))


LIB = _lib_dir()


def load(name: str) -> ModuleType:
    key = f"ginflow_lib_{name}"
    if key in sys.modules:
        return sys.modules[key]
    path = LIB / f"{name}.py"
    spec = importlib.util.spec_from_file_location(key, path)
    if not spec or not spec.loader:
        raise ImportError(f"unable to load Ginflow lib module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(key, None)
        raise
    return module
