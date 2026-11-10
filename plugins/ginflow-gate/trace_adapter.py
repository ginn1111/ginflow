"""Optional adapter for the standalone ginflow-trace plugin."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])
TRACE_PACKAGE = Path(__file__).resolve().parents[1] / "ginflow-trace/ginflow_trace"


def _load_trace() -> Callable[[F], F]:
    try:
        spec = importlib.util.spec_from_file_location(
            "ginflow_trace", TRACE_PACKAGE / "__init__.py",
            submodule_search_locations=[str(TRACE_PACKAGE)],
        )
        if not spec or not spec.loader:
            raise ImportError("trace package unavailable")
        module = importlib.util.module_from_spec(spec)
        # Register the package before execution so its relative imports work
        # when gate.py/routing.py are loaded as standalone plugin modules.
        sys.modules.setdefault("ginflow_trace", module)
        spec.loader.exec_module(module)
        return module.trace
    except Exception:
        return lambda function: function


trace = _load_trace()