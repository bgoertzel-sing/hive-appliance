"""Tests for the exit code verifier (P0-fixed).

F6: Verifier independently returns bool; appliance sets receipt.verified.
F6: Fixed inactive/active substring bug with word-boundary regex.
"""
from verifier.exit_code_verifier import ExitCodeVerifier
from schemas.types import Receipt


class TestExitCodeVerifier:
    def test_verify_success(self):
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0, stdout="ok")
        assert v.verify(r, {"exit_code": 0}) is True

    def test_verify_failure(self):
        v = ExitCodeVerifier()
        r = Receipt(exit_code=1, stderr="error")
        assert v.verify(r, {"exit_code": 0}) is False

    def test_verify_stdout_contains(self):
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0, stdout="active")
        assert v.verify(r, {"exit_code": 0, "stdout_contains": "active"}) is True

    def test_verify_inactive_not_active(self):
        """F6: inactive should NOT match active."""
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0, stdout="inactive")
        assert v.verify(r, {"exit_code": 0, "stdout_contains": "active"}) is False

    def test_verifier_returns_bool(self):
        """F6: Verifier returns bool; appliance sets receipt.verified."""
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0)
        result = v.verify(r, {"exit_code": 0})
        assert result is True
