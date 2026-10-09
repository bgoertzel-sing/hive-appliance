"""Astra 7734 (docs/ASTRA_REVIEW_7734.md, 48c10cc) on 8c54bdf.
1 Med F-reset-intent-durability-status: an existing reset-intent marker is
      classified with os.lstat() (errors propagate); a stat EIO/EACCES is never
      read as "not a file"; non-regular markers are rejected; intent_durable
      is True only after file fsync AND directory fsync.
2 Low F-reset-error-metadata-status: a failed presence check is "unknown"
      (intent_present None + presence_error), never "absent"; the failure text
      is built from the steps that actually completed (completed_steps).
Audit: reset/clear/startup use a strict presence check (only ENOENT = absent).
"""
import errno
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import run
from tests.test_astra7718 import _held, _pair


def _fence(h):
    return h.journal_status()["fence"]


def _old(jp):
    return {p: open(p, "rb").read() for p in (jp, jp + ".id")}


def _lstat_fail(monkeypatch, target, err, calls_to_fail):
    """Fail os.lstat(target) on the given call numbers ('all' = every call)."""
    real = os.lstat
    n = [0]

    def f(p, *a, **k):
        if os.fspath(p) == target:
            i = n[0]
            n[0] += 1
            if calls_to_fail == "all" or i in calls_to_fail:
                raise OSError(err, f"injected lstat {errno.errorcode[err]} #{i}", p)
        return real(p, *a, **k)
    monkeypatch.setattr(os, "lstat", f)
    return n


def _fsyncs(monkeypatch):
    real = os.fsync
    seen = []

    def f(fd):
        try:
            seen.append(os.readlink(f"/proc/self/fd/{fd}"))
        except OSError:
            seen.append(fd)
        return real(fd)
    monkeypatch.setattr(os, "fsync", f)
    return seen


def _leftover(tmp_path, k):
    jp, _ = _pair(tmp_path, k)
    ip = jp + ".reset-intent"
    with open(ip, "wb") as f:                       # real, un-fsync'd marker
        f.write(b'{"op": "reset_intent"}\n')
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    assert _fence(h)["kind"] == "reset_incomplete"
    return jp, ip, h


@pytest.mark.parametrize("err", [errno.EIO, errno.EACCES], ids=["EIO", "EACCES"])
@pytest.mark.parametrize("which", [(0,), (1,), "all"], ids=["first", "helper", "all"])
def test_stat_error_on_existing_marker_never_durable(tmp_path, monkeypatch, err, which):
    jp, ip, h = _leftover(tmp_path, f"{err}{which}")
    old = _old(jp)
    seen = _fsyncs(monkeypatch)
    _lstat_fail(monkeypatch, ip, err, which)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    assert os.path.realpath(ip) not in seen          # marker never fsync'd ...
    f = _fence(h)
    assert f["kind"] == "reset_failed"
    assert f["intent_durable"] is False               # ... so never "durable"
    assert h.journal_status()["journal_resets"][-1]["intent_durable"] is False
    assert "fsync confirmed" not in f["error"] and "every start fences" not in f["error"]
    assert "keep the service stopped" in f["error"]
    if which == "all":
        assert f["intent_present"] is None and "presence_error" in f
        assert "UNKNOWN" in f["error"]
    assert _old(jp) == old and os.path.lexists(ip)
    assert h.journal_pending() == [] and _held(h)
    h2 = run([], journal=jp)                          # restart still fences
    assert _fence(h2)["kind"] == "reset_incomplete" and _held(h2)
    assert h.reset_journal(actor="op", reason="retry")["status"] == "completed"
    assert not os.path.lexists(ip) and _held(run([], journal=jp))


@pytest.mark.parametrize("kind", ["symlink", "directory"])
def test_non_regular_marker_rejected_not_durable(tmp_path, kind):
    jp, _ = _pair(tmp_path, kind)
    ip = jp + ".reset-intent"
    if kind == "symlink":
        os.symlink(jp + ".id", ip)
    else:
        os.mkdir(ip)
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    assert _fence(h)["kind"] == "reset_incomplete" and _held(h)
    old = _old(jp)
    with pytest.raises(OSError, match="not a regular file"):
        h.reset_journal(actor="op", reason="restore")
    f = _fence(h)
    assert f["intent_durable"] is False and f["intent_present"] is True
    assert f["failed_step"] == "confirm existing reset-intent marker"
    assert _old(jp) == old
    assert _fence(run([], journal=jp))["kind"] == "reset_incomplete"


def test_handler_lstat_eio_after_journal_moved_reports_unknown(tmp_path, monkeypatch):
    # Astra metadata7734 case 1
    jp, h = _pair(tmp_path, "m1")
    ip, idp = jp + ".reset-intent", jp + ".id"
    real_open = os.open
    broke = [False]

    def opn(p, *a, **k):        # anchor read uses os.open since Astra 7741
        if os.fspath(p) == idp and not broke[0]:
            broke[0] = True
            raise OSError(errno.EIO, "injected anchor read")
        return real_open(p, *a, **k)
    monkeypatch.setattr(os, "open", opn)
    real_lstat = os.lstat

    def lst(p, *a, **k):
        if broke[0] and os.fspath(p) == ip:
            raise OSError(errno.EIO, "injected handler lstat", p)
        return real_lstat(p, *a, **k)
    monkeypatch.setattr(os, "lstat", lst)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    f = _fence(h)
    assert f["failed_step"] == "archive old anchor"
    assert f["intent_present"] is None and "presence_error" in f
    assert f["intent_durable"] is False
    assert "unchanged on disk" not in f["error"]
    assert "old journal renamed" in f["error"]
    assert any(s.startswith("old journal renamed") for s in f["completed_steps"])
    assert os.path.lexists(ip) and not os.path.lexists(jp)
    h2 = run([], journal=jp)
    assert _fence(h2)["kind"] == "reset_incomplete" and _held(h2)


def test_handler_lstat_eio_after_failed_unlink_reports_unknown(tmp_path, monkeypatch):
    # Astra metadata7734 case 2
    jp, h = _pair(tmp_path, "m2")
    ip = jp + ".reset-intent"
    real_unlink, real_lstat = os.unlink, os.lstat
    broke = [False]

    def unl(p, *a, **k):
        if os.fspath(p) == ip:
            broke[0] = True
            raise PermissionError(errno.EACCES, "injected unlink")
        return real_unlink(p, *a, **k)

    def lst(p, *a, **k):
        if broke[0] and os.fspath(p) == ip:
            raise OSError(errno.EIO, "injected handler lstat", p)
        return real_lstat(p, *a, **k)
    monkeypatch.setattr(os, "unlink", unl)
    monkeypatch.setattr(os, "lstat", lst)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    f = _fence(h)
    assert f["failed_step"] == "remove reset-intent marker"
    assert f["intent_present"] is None and f["intent_durable"] is False
    assert "marker was unlinked" not in f["error"]
    assert "reset-intent marker unlinked" not in f["completed_steps"]
    assert "new rebind-free journal written" in f["completed_steps"]
    assert "not known" in f["error"] and "restart is safe" in f["error"]
    assert os.path.lexists(ip)
    h2 = run([], journal=jp)
    assert _fence(h2)["kind"] == "reset_incomplete" and _held(h2)


def test_failed_unlink_with_visible_marker_says_not_unlinked(tmp_path, monkeypatch):
    jp, h = _pair(tmp_path, "m3")
    ip = jp + ".reset-intent"
    real_unlink = os.unlink

    def unl(p, *a, **k):
        if os.fspath(p) == ip:
            raise PermissionError(errno.EACCES, "injected unlink")
        return real_unlink(p, *a, **k)
    monkeypatch.setattr(os, "unlink", unl)
    with pytest.raises(OSError):
        h.reset_journal(actor="op", reason="restore")
    monkeypatch.undo()
    f = _fence(h)
    assert f["intent_present"] is True and "NOT unlinked" in f["error"]
    assert "marker was unlinked" not in f["error"]


@pytest.mark.parametrize("err", [errno.EIO, errno.EACCES], ids=["EIO", "EACCES"])
def test_startup_marker_lstat_error_is_present_not_absent(tmp_path, monkeypatch, err):
    jp, _ = _pair(tmp_path, f"s{err}")
    ip = jp + ".reset-intent"
    _lstat_fail(monkeypatch, ip, err, "all")
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    f = h._journal_fence
    assert f["kind"] == "reset_incomplete" and f["intent_present"] is None
    assert h._journal_pending == [] and h._reset_discard is True
    assert h.journal_status()["reset_in_progress"] is None      # unknown
    monkeypatch.undo()


@pytest.mark.parametrize("err", [errno.EIO, errno.EACCES], ids=["EIO", "EACCES"])
def test_startup_legacy_fence_file_lstat_error_fences(tmp_path, monkeypatch, err):
    jp, _ = _pair(tmp_path, f"l{err}")
    _lstat_fail(monkeypatch, jp + ".fence", err, "all")
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    monkeypatch.undo()
    assert _fence(h)["kind"] == "unwritable" and h._journal_pending == []


def test_clear_fence_presence_error_raises_and_stays_fenced(tmp_path, monkeypatch):
    jp, ip, h = _leftover(tmp_path, "clr")
    _lstat_fail(monkeypatch, ip, errno.EIO, "all")
    with pytest.raises(OSError):
        h.clear_journal_fence(actor="op", reason="after crash")
    monkeypatch.undo()
    assert h.journal_status()["healthy"] is False and os.path.lexists(ip)
    assert h.clear_journal_fence(actor="op", reason="retry")
    assert not os.path.lexists(ip) and h.journal_status()["healthy"] is True
    assert _held(run([], journal=jp))
