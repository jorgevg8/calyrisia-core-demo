from __future__ import annotations

import importlib.abc
import importlib.util
import os
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent.parent


class _DirectStatPathFinder(importlib.abc.MetaPathFinder):
    """Fallback module finder using direct stat() when virtual/FUSE readdir caches lag."""

    def find_spec(self, fullname: str, path=None, target=None):
        if not fullname.startswith("app."):
            return None
        rel_parts = fullname.split(".")
        candidate_py = _APP_ROOT.joinpath(*rel_parts).with_suffix(".py")
        if os.path.isfile(candidate_py):
            return importlib.util.spec_from_file_location(fullname, str(candidate_py))
        candidate_pkg = _APP_ROOT.joinpath(*rel_parts, "__init__.py")
        if os.path.isfile(candidate_pkg):
            return importlib.util.spec_from_file_location(
                fullname,
                str(candidate_pkg),
                submodule_search_locations=[str(candidate_pkg.parent)],
            )
        return None


if not any(type(f).__name__ == "_DirectStatPathFinder" for f in sys.meta_path):
    sys.meta_path.append(_DirectStatPathFinder())
