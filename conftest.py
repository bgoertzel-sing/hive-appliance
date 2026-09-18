"""Root conftest — fix sys.path so venv packages take precedence over vendor."""
import sys

# Move the vendor path to the end so venv site-packages wins for shared packages
_vendor = "/hive/protomega2/iter-port-omega/vendor"
if _vendor in sys.path:
    sys.path.remove(_vendor)
    sys.path.append(_vendor)
