"""Astra 7727 (docs/ASTRA_REVIEW_7727.md, 1a33645) on 7ce5cd5.
F-reset-intent-durability-status (Medium): a failed reset_journal() reports
intent_durable True ONLY after the reset-intent marker's file fsync AND its
directory fsync have succeeded (a pre-existing marker is re-synced first).
Marker presence alone is never reported as durable.
"""
import errno
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import run
from tests.test_astra7718 import _held, _pair


def _fence(h):
    return h.journal_status()["fence"]


def _last(h):
    return h.journal_status()["journal_resets"][-1]


def _not_durable(h, jp, old, present):
    f = _fence(h)
    assert f["kind"] == "reset_failed"
    assert f["intent_durable"] is False and _last(h)["intent_durable"] is False
    assert f["intent_present"] is present and _last(h)["intent_present"] is present
    assert "NOT confirmed" in f["error"] and "keep the" in f["error"]
    assert "every start fences" not in f["error"]
    assert h.journal_pending() == [] and _held(h)     # live discard kept
    assert {p: open(p, "rb").read() for p in old} == old   # old pair intact


def _old(jp):
    return {p: open(p, "rb").read() for p in (jp, jp + ".id")}


def _fail_fsync_number(monkeypatch, n, exc=None):
    real = os.fsync
    calls = [0]

    def f(fd):
        i = calls[0]
        calls[0] += 1
        if i == n:
            raise exc or OSError(errno.EIO, f"injected fsync #{i}")
        return real(fd)
    monkeypatch.setattr(os, "fsync", f)
    return calls


@pytest.mark.parametrize("which", [0, 1], ids=["file_fsync", "dir_fsync"])
def test_each_marker_fsync_failure_reports_not_durable(tmp_path, monkeypatch, which):
    jp, h = _pair(tmp_path, which)
    old = _old(jp)
    _fail_fsync_number(monkeypatch, which)   # #0 marker file, #1 its directory
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    assert _fence(h)["failed_step"] == "create reset-intent marker"
    _not_durable(h, jp, old, present=os.path.lexists(jp + ".reset-intent"))


def test_fsync_eio_and_cleanup_unlink_eacces_not_durable(tmp_path, monkeypatch):
    # Astra witness 2: marker stays visible, nothing was confirmed durable
    jp, h = _pair(tmp_path, "w2")
    old = _old(jp)
    _fail_fsync_number(monkeypatch, 0)
    real_unlink = os.unlink

    def unlink(p, *a, **k):
        if p == jp + ".reset-intent":
            raise PermissionError(errno.EACCES, "injected")
        return real_unlink(p, *a, **k)
    monkeypatch.setattr(os, "unlink", unlink)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    assert os.path.lexists(jp + ".reset-intent")
    _not_durable(h, jp, old, present=True)
    # a visible marker still blocks ordinary restarts ...
    assert _fence(run([], journal=jp))["kind"] == "reset_incomplete"


def test_error_right_after_marker_open_zero_fsyncs(tmp_path, monkeypatch):
    # Astra witness 1: empty marker created, zero fsync calls, then failure
    jp, h = _pair(tmp_path, "w1")
    old = _old(jp)
    ip = jp + ".reset-intent"
    real_open = os.open
    calls = _fail_fsync_number(monkeypatch, -1)

    def opn(p, *a, **k):
        fd = real_open(p, *a, **k)
        if p == ip:
            os.close(fd)
            raise OSError(errno.EIO, "injected after successful O_CREAT")
        return fd
    monkeypatch.setattr(os, "open", opn)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    assert calls[0] == 0 and os.path.getsize(ip) == 0
    _not_durable(h, jp, old, present=True)
    # modeled loss of the unsynced marker: the old pair would replay p --
    # exactly why intent_durable must be False here
    os.unlink(ip)
    assert run([], journal=jp)._journal_pending


def test_preexisting_marker_is_resynced_before_durable(tmp_path, monkeypatch):
    for which in (0, 1):
        jp, h = _pair(tmp_path, f"pre{which}")
        ip = jp + ".reset-intent"
        open(ip, "wb").close()                       # leftover, unsynced
        h = hr.HiveReducer(rebind_journal=jp)
        h.register_agent("a1")
        assert _fence(h)["kind"] == "reset_incomplete"
        old = _old(jp)
        _fail_fsync_number(monkeypatch, which)
        with pytest.raises(OSError):
            h.reset_journal(actor="op", reason="restore")
        monkeypatch.undo()
        assert _fence(h)["failed_step"] == "confirm existing reset-intent marker"
        _not_durable(h, jp, old, present=True)
        assert h.reset_journal(actor="op", reason="retry")["status"] == "completed"
        assert not os.path.lexists(ip) and _held(run([], journal=jp))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode 000")
def test_unreadable_preexisting_marker_not_durable(tmp_path):
    jp, _h = _pair(tmp_path, "m000")
    ip = jp + ".reset-intent"
    open(ip, "wb").close()
    os.chmod(ip, 0)
    try:
        h = hr.HiveReducer(rebind_journal=jp)
        h.register_agent("a1")
        with pytest.raises(OSError):
            h.reset_journal(actor="op", reason="restore")
        assert _fence(h)["intent_durable"] is False
        assert os.path.lexists(ip)                   # not deleted
    finally:
        os.chmod(ip, 0o600)


def test_failure_after_confirmed_intent_reports_durable(tmp_path, monkeypatch):
    jp, h = _pair(tmp_path, "after")
    real = os.replace

    def rep(a, b, *x, **k):
        if a == jp:                                  # move old journal aside
            raise OSError(errno.EIO, "injected")
        return real(a, b, *x, **k)
    monkeypatch.setattr(os, "replace", rep)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    f = _fence(h)
    assert f["intent_durable"] is True and f["intent_present"] is True
    assert "fsync confirmed" in f["error"]
    for _ in range(2):
        h2 = run([], journal=jp)
        assert _fence(h2)["kind"] == "reset_incomplete" and _held(h2)
