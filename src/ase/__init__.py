"""ASE — Agent Simulation Engine.

Public API surface. Import from here, not from internal modules.
"""

from __future__ import annotations

import os
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

# ASE does not rely on third-party Pydantic plugins. Disabling plugin auto-load
# keeps CLI startup deterministic even when unrelated plugins are installed in
# the active environment.
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

from ase.errors import ASEError

__version__ = "0.1.0"
__all__ = ["ASEError", "__version__"]
