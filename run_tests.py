#!/usr/bin/env python3
"""Simple test runner that mimics pytest's basic functionality."""
import sys
import os
import importlib
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = 0

    def run(self):
        test_dir = "tests"
        for fname in sorted(os.listdir(test_dir)):
            if fname.startswith("test_") and fname.endswith(".py"):
                mod_name = f"tests.{fname[:-3]}"
                print(f"\n{'='*60}")
                print(f"  {fname}")
                print(f"{'='*60}")
                try:
                    mod = importlib.import_module(mod_name)
                    for attr_name in sorted(dir(mod)):
                        if attr_name.startswith("Test"):
                            cls = getattr(mod, attr_name)
                            if not isinstance(cls, type):
                                continue
                            print(f"\n  {attr_name}:")
                            for method_name in sorted(dir(cls)):
                                if method_name.startswith("test_"):
                                    method = getattr(cls, method_name)
                                    if not callable(method):
                                        continue
                                    try:
                                        instance = cls()
                                        method(instance)
                                        print(f"    ✓ {method_name}")
                                        self.passed += 1
                                    except AssertionError as e:
                                        print(f"    ✗ {method_name}: {e}")
                                        self.failed += 1
                                    except Exception as e:
                                        print(f"    ! {method_name}: {e}")
                                        traceback.print_exc()
                                        self.errors += 1
                except Exception as e:
                    print(f"  ! Module import error: {e}")
                    traceback.print_exc()
                    self.errors += 1

        print(f"\n{'='*60}")
        print(f"  Results: {self.passed} passed, {self.failed} failed, {self.errors} errors")
        print(f"{'='*60}")
        return self.failed + self.errors


if __name__ == "__main__":
    runner = TestRunner()
    sys.exit(runner.run())
