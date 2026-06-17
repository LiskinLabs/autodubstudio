import sys, types
import torchvision
import speechbrain.utils.importutils as sb_imports

_orig_getattr = sb_imports.LazyModule.__getattr__
def _safe_getattr(self, attr):
    try: return _orig_getattr(self, attr)
    except ImportError: return types.ModuleType(self.target)

sb_imports.LazyModule.__getattr__ = _safe_getattr
from pyannote.audio import Pipeline
