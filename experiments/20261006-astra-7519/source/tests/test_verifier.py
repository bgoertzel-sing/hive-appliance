"""Tests for the exit code verifier."""

from schemas.types import Receipt
from verifier.exit_code_verifier import ExitCodeVerifier


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
        assert v.verify(r, {"exit_code": 0, "stdout_contains": "inactive"}) is False

    def test_verify_sets_receipt_verified(self):
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0)
        v.verify(r, {"exit_code": 0})
        assert r.verified is True
