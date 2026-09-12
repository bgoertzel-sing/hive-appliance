"""
Pytest compatibility shim — provides minimal pytest API for tests
when pytest is not installed. Works with both pytest and run_tests.py.
"""
import sys

if 'pytest' not in sys.modules:
    class _PytestShim:
        """Minimal pytest-compatible stub for use without pytest installed."""
        class raises:
            def __init__(self, expected_exception, match=None):
                self.expected_exception = expected_exception
                self.match = match
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(
                        f"DID NOT RAISE {self.expected_exception!r}"
                    )
                if not issubclass(exc_type, self.expected_exception):
                    return False
                if self.match and self.match not in str(exc_val):
                    raise AssertionError(
                        f"Pattern '{self.match}' not found in '{exc_val}'"
                    )
                return True

        @staticmethod
        def mark(*args, **kwargs):
            """No-op decorator for pytest.mark."""
            def decorator(func):
                return func
            return decorator

    sys.modules['pytest'] = _PytestShim()
