"""Astra 7750 (docs/ASTRA_REVIEW_7750.md, 4a9b3c5) on 6b750ca.
1 Med: a FIFO (or other non-regular entry) swapped in for the journal, its .id
      anchor or the reset-intent marker must never block an open: every open is
      O_NONBLOCK | O_NOFOLLOW, fstat'd and refused unless a regular file before
      any read/write (blocking restored only after the check).
2 Low: a directory swapped in for the journal at runtime sets the "changed"
      fence and marks the journal unhealthy (like a symlink swap).
Every test runs under a SIGALRM watchdog so a hang is a failure, not a stall.
"""
import contextlib
import os
import signal

import pytest

import hive.reducer as hr
from tests.test_astra7638 import run
from tests.test_astra7656 import S

LIMIT = 5


@contextlib.contextmanager
def watchdog(sec=LIMIT):
    def boom(*_):
        raise TimeoutError(f"hung for more than {sec}s")
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(sec)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _fresh(tmp_path, k):
    d = tmp_path / k
    d.mkdir()
    jp = str(d / "rebinds.jsonl")
    with watchdog():
        h = run(S, journal=jp)
    assert h.journal_status()["healthy"] is True and os.path.isfile(jp)
    return jp, h


def _swap(jp, kind):
    os.replace(jp, jp + ".orig")
    if kind == "fifo":
        os.mkfifo(jp)
    else:
        os.mkdir(jp)


def _fence(h):
    return h.journal_status()["fence"]


@pytest.mark.parametrize("which", ["journal", "anchor"])
def test_fifo_at_startup_fences_without_hanging(tmp_path, which):
    jp, _ = _fresh(tmp_path, which)
    p = jp if which == "journal" else jp + ".id"
    os.unlink(p)
    os.mkfifo(p)
    for _ in range(2):
        with watchdog():
            h = run(S, journal=jp)
        f = _fence(h)
        assert f["kind"] == "identity" and "not a regular file" in f["error"]
        assert h.journal_status()["healthy"] is False and h._journal_pending == []
        assert os.path.exists(p) and not os.path.isfile(p)      # untouched fifo
    with watchdog():
        assert h.clear_journal_fence(actor="op", reason="fifo") is True
        assert run(S, journal=jp).journal_status()["healthy"] is True


@pytest.mark.parametrize("which", ["journal", "anchor"])
def test_fifo_swapped_between_lstat_and_open(tmp_path, monkeypatch, which):
    jp, _ = _fresh(tmp_path, "race" + which)
    p = jp if which == "journal" else jp + ".id"
    real = os.lstat
    done = [False]

    def lst(q, *a, **k):
        st = real(q, *a, **k)
        if os.fspath(q) == p and not done[0]:
            done[0] = True
            os.unlink(p)
            os.mkfifo(p)                    # swapped after lstat, before open
        return st
    monkeypatch.setattr(os, "lstat", lst)
    with watchdog():
        h = run(S, journal=jp)
    monkeypatch.undo()
    assert done[0]
    f = _fence(h)
    assert f["kind"] == "unwritable" and "changed while it was being" in f["error"]
    assert h.journal_status()["healthy"] is False and h._journal_pending == []


@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_swap_during_verify_journal(tmp_path, kind):
    jp, h = _fresh(tmp_path, "v" + kind)
    _swap(jp, kind)
    with watchdog():
        assert h.verify_journal() is False
    assert _fence(h)["kind"] == "changed"
    assert h.journal_status()["healthy"] is False


@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_swap_before_append_fences_changed(tmp_path, kind):
    jp, h = _fresh(tmp_path, "a" + kind)
    _swap(jp, kind)
    with watchdog():
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    f = _fence(h)
    assert f["kind"] == "changed", f
    assert h.journal_status()["healthy"] is False
    assert h._plan_owner.get("a1:p") is None            # nothing applied
    assert os.path.exists(jp) and not os.path.isfile(jp)
    with watchdog():                                    # later calls refuse too
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_directory_swap_append_path_alone(tmp_path, monkeypatch):
    """The append itself (not only verify) must classify EISDIR as changed."""
    jp, h = _fresh(tmp_path, "dironly")
    _swap(jp, "directory")
    monkeypatch.setattr(h, "verify_journal", lambda: True)
    with watchdog():
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert _fence(h)["kind"] == "changed"
    assert h.journal_status()["healthy"] is False


def test_intent_marker_fifo_is_refused_without_hanging(tmp_path):
    jp, h = _fresh(tmp_path, "intent")
    ip = jp + ".reset-intent"
    os.mkfifo(ip)
    with watchdog():
        with pytest.raises((OSError, ValueError)):
            h._sync_existing_durably(ip)


def test_open_regular_fd_refuses_fifo_and_restores_blocking(tmp_path):
    f = str(tmp_path / "fifo")
    os.mkfifo(f)
    with watchdog():
        with pytest.raises(hr._NotRegularFile):
            hr._open_regular_fd(f, os.O_RDONLY, "x")
        with pytest.raises(hr._NotRegularFile):
            hr._open_regular_fd(f, os.O_RDWR | os.O_APPEND, "x")
    r = tmp_path / "reg"
    r.write_bytes(b"abc")
    fd, st = hr._open_regular_fd(str(r), os.O_RDONLY, "x")
    try:
        assert os.get_blocking(fd) is True and st.st_size == 3
    finally:
        os.close(fd)


def test_healthy_controls_unchanged(tmp_path):
    jp, h = _fresh(tmp_path, "ok")
    with watchdog():
        assert h.verify_journal() is True
        r = h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
        assert r and r.status == "applied"
        assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"
