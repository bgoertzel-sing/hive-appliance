"""Run pytest with vendor path moved to end of sys.path."""
import sys
_vendor = "/hive/protomega2/iter-port-omega/vendor"
if _vendor in sys.path:
    sys.path.remove(_vendor)
    sys.path.append(_vendor)

import pytest
sys.exit(pytest.main(sys.argv[1:]))
