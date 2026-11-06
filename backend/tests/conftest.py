"""Test setup: mongomock does not accept the newest pymongo bulk arguments, so ignore them."""
import sys
from pathlib import Path

import mongomock.collection as mc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _name in ("add_replace", "add_update", "add_delete"):
    _orig = getattr(mc.BulkOperationBuilder, _name, None)
    if _orig is not None:
        def _wrap(self, *a, _orig=_orig, **kw):
            for extra in ("sort", "hint", "collation", "array_filters", "namespace"):
                kw.pop(extra, None)
            return _orig(self, *a, **kw)
        setattr(mc.BulkOperationBuilder, _name, _wrap)
