"""Astra 7718 (docs/ASTRA_REVIEW_7718.md, 30e3d39) on 0ec1a2d.
1 Med F-reset-interruption-replays-restored-pair: a durable reset-intent
      marker is written BEFORE any other disk change and removed only after
      the new rebind-free pair is durable; while it exists startup fences
      (reset_incomplete) and replays nothing.  The old journal is renamed
      aside (not copied).
2 Med F-reset-error-live-pending: reset_journal() discards pending rebinds
      and fences in memory BEFORE any disk work; any error leaves it fenced
      (reset_failed); replay and clear_journal_fence() carry nothing.
Fault injection: every os.open/write/fsync/replace/unlink call made by
reset_journal() is failed in turn (crash = BaseException, disk error = OSError).
"""
import contextlib
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import feed, run
from tests.test_astra7656 import S
from tests.test_astra7708 import _restored_pair

HOOKS = ("open", "replace", "unlink", "fsync", "write")


class Crash(BaseException):
    """Simulated process death."""


@contextlib.contextmanager
def _inject(at, exc):
    calls = [0]
    saved = {n: getattr(os, n) for n in HOOKS}

    def wrap(n):
        real = saved[n]

        def f(*a, **k):
            i = calls[0]
            calls[0] += 1
            if at is not None and i == at:
                raise exc(f"injected failure of os.{n} (call #{i})")
            return real(*a, **k)
        return f
    for n in HOOKS:
        setattr(os, n, wrap(n))
    try:
        yield calls
    finally:
        for n, f in saved.items():
            setattr(os, n, f)


def _held(h):
    return h._plan_owner.get("a1:p") is None


def _fresh(jp):
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    return h


def _pair(tmp_path, k):
    d = tmp_path / f"k{k}"
    d.mkdir()
    jp = _restored_pair(d)
    h = _fresh(jp)
    assert len(h._journal_pending) == 1 and h.journal_status()["healthy"]
    return jp, h


def _n_calls(tmp_path):
    jp, h = _pair(tmp_path, "count")
    with _inject(None, OSError) as calls:
        assert h.reset_journal(actor="op", reason="count")["status"] == "completed"
    return calls[0]


def _recovered(jp):
    for _ in range(2):
        h = run(S, journal=jp)
        assert _held(h) and h.journal_status()["healthy"] is True
    r = h.rebind_plan_owner("a1", "p", "i", actor="op", reason="re-issued")
    assert r and r.status == "applied"
    assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


def test_crash_at_every_reset_step_never_revives(tmp_path):
    n = _n_calls(tmp_path)
    assert n >= 20
    for k in range(n):
        jp, h = _pair(tmp_path, k)
        old = {f: open(f, "rb").read() for f in (jp, jp + ".id")}
        with _inject(k, Crash), pytest.raises(Crash):
            h.reset_journal(actor="op", reason="restore")
        marker = os.path.lexists(jp + ".reset-intent")
        if k == 0:
            # died before its first disk change: the reset never happened
            assert not marker
            assert {f: open(f, "rb").read() for f in old} == old
        else:
            for _ in range(2):                           # plain restarts
                h2 = run(S, journal=jp)
                assert _held(h2), k                      # never revived
                st = h2.journal_status()
                if marker:
                    assert st["fence"]["kind"] == "reset_incomplete", k
                    assert st["reset_in_progress"] is True
                    assert not h2.rebind_plan_owner("a1", "p", "i", actor="op",
                                                    reason="t")
                else:                                    # crashed after commit
                    assert st["healthy"] is True, k
        h3 = _fresh(jp)                                  # operator retries
        if k % 2 or k == 0 or not marker:
            assert h3.reset_journal(actor="op", reason="retry")["status"] == "completed"
        else:
            assert h3.clear_journal_fence(actor="op", reason="after crash")
            assert h3.journal_status()["fence_clearances"][-1]["rebinds_rejournaled"] == 0
        assert not os.path.lexists(jp + ".reset-intent")
        feed(h3, S)
        assert _held(h3) and h3.journal_status()["healthy"] is True
        _recovered(jp)


def test_disk_error_at_every_reset_step_fails_closed(tmp_path):
    n = _n_calls(tmp_path)
    for k in range(n):
        jp, h = _pair(tmp_path, k)
        old = {f: open(f, "rb").read() for f in (jp, jp + ".id")}
        with _inject(k, OSError), pytest.raises(OSError):
            h.reset_journal(actor="op", reason="restore")
        st = h.journal_status()
        assert st["healthy"] is False and st["fence"]["kind"] == "reset_failed", k
        assert st["pending"] == 0 and h.journal_pending() == []
        assert st["journal_resets"][-1]["status"] == "failed"
        feed(h, S)                                       # replay applies nothing
        assert _held(h), k
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
        # restart (read-only) before any operator action
        h2 = run(S, journal=jp)
        if st["fence"]["intent_durable"]:
            assert h2.journal_status()["fence"]["kind"] == "reset_incomplete"
            assert _held(h2), k
        elif st["fence"]["failed_step"] == "remove reset-intent marker":
            assert _held(h2) and h2.journal_status()["healthy"], k
        else:
            # documented boundary: the intent marker itself could not be
            # written, so nothing changed on disk -- the old pair is intact
            assert st["fence"]["failed_step"] == "create reset-intent marker"
            assert {f: open(f, "rb").read() for f in old} == old
        # Astra's sequence: verify_journal() then clear_journal_fence()
        assert h.verify_journal() is False
        assert h.clear_journal_fence(actor="op", reason="after failed reset")
        assert h.journal_status()["fence_clearances"][-1]["rebinds_rejournaled"] == 0
        assert _held(h) and h.journal_status()["healthy"] is True
        assert not os.path.lexists(jp + ".reset-intent")
        _recovered(jp)


def test_retry_after_failed_reset_completes(tmp_path):
    jp, h = _pair(tmp_path, "retry")
    with _inject(12, OSError), pytest.raises(OSError):
        h.reset_journal(actor="op", reason="first")
    info = h.reset_journal(actor="op", reason="retry")
    assert info["status"] == "completed" and info["was_fenced"] == "reset_failed"
    feed(h, S)
    assert _held(h) and h.journal_status()["healthy"] is True
    _recovered(jp)


def test_old_journal_is_renamed_aside_not_copied(tmp_path):
    jp, h = _pair(tmp_path, "rename")
    old = open(jp, "rb").read()
    ino = os.stat(jp).st_ino
    info = h.reset_journal(actor="op", reason="r")
    arch = info["archived"][jp]
    assert os.stat(arch).st_ino == ino and open(arch, "rb").read() == old
