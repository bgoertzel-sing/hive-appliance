"""Astra 7741 (docs/ASTRA_REVIEW_7741.md, fb8bdb2) on 2c7e337.
1 Med F-dangling-anchor-overwrite: the identity anchor (<journal>.id) and the
      journal are read strictly -- only an lstat ENOENT on the entry itself is
      "absent".  A symlink (dangling or valid) or directory fences at startup,
      is never followed and never overwritten; clear/reset move it aside intact.
2 Low: journal_resets failure entries carry presence_error like the fence.
"""
import errno
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import run
from tests.test_astra7718 import _pair


def _fence(h):
    return h.journal_status()["fence"]


def _snap(p):
    st = os.lstat(p)
    return (st.st_mode, st.st_ino, os.readlink(p) if os.path.islink(p) else None)


def _make(kind, p, tmp_path):
    if kind == "dangling":
        os.symlink(str(tmp_path / "nowhere.id"), p)
    elif kind == "valid":
        tgt = tmp_path / "real.id"
        tgt.write_text('{"journal_id": "x", "v": 5}\n')
        os.symlink(str(tgt), p)
    else:
        os.mkdir(p)


def _start(jp):
    h = hr.HiveReducer(rebind_journal=jp)
    h.register_agent("a1")
    return h


KINDS = ["dangling", "valid", "directory"]


@pytest.mark.parametrize("journal", ["missing", "present"])
@pytest.mark.parametrize("kind", KINDS)
def test_non_regular_anchor_fences_never_overwritten(tmp_path, kind, journal):
    if journal == "present":
        jp, _ = _pair(tmp_path, kind)
        os.unlink(jp + ".id")
        before_j = open(jp, "rb").read()
    else:
        d = tmp_path / kind
        d.mkdir()
        jp = str(d / "rebinds.jsonl")
    idp = jp + ".id"
    _make(kind, idp, tmp_path)
    snap = _snap(idp)
    for _ in range(2):                                  # every restart
        h = _start(jp)
        f = _fence(h)
        assert f["kind"] == "identity" and h.journal_status()["healthy"] is False
        assert "not a regular file" in f["error"] and f["artifacts"] == [idp]
        assert h._journal_pending == [] and h._journal_applied == []
        assert _snap(idp) == snap                       # untouched
        if journal == "missing":
            assert not os.path.lexists(jp)              # nothing created
        else:
            assert open(jp, "rb").read() == before_j
    if kind == "valid":
        assert open(tmp_path / "real.id").read() == '{"journal_id": "x", "v": 5}\n'
    # explicit operator commands move the entry aside intact, then succeed
    h = _start(jp)
    if journal == "present":
        assert h.reset_journal(actor="op", reason="fix anchor")["status"] == "completed"
        aside = [p for p in os.listdir(os.path.dirname(jp)) if p.startswith("rebinds.jsonl.id.reset-")]
    else:
        assert h.clear_journal_fence(actor="op", reason="fix anchor") is True
        aside = [p for p in os.listdir(os.path.dirname(jp)) if p.startswith("rebinds.jsonl.id.cleared-")]
    assert len(aside) == 1
    assert _snap(os.path.join(os.path.dirname(jp), aside[0]))[0] == snap[0]
    assert os.path.isfile(idp) and not os.path.islink(idp)
    h2 = _start(jp)
    assert h2.journal_status()["healthy"] is True


@pytest.mark.parametrize("kind", KINDS)
def test_non_regular_journal_entry_fences(tmp_path, kind):
    jp, _ = _pair(tmp_path, "j" + kind)
    os.unlink(jp)
    _make(kind, jp, tmp_path)
    snap = _snap(jp)
    h = _start(jp)
    assert _fence(h)["kind"] == "identity" and "rebind journal" in _fence(h)["error"]
    assert _snap(jp) == snap and h._journal_pending == []
    assert h.clear_journal_fence(actor="op", reason="fix") is True
    assert os.path.isfile(jp) and not os.path.islink(jp)
    archived = h.journal_fence_clearances[-1]["archived"]
    assert archived and _snap(archived)[0] == snap[0]
    assert _start(jp).journal_status()["healthy"] is True


def test_regular_and_missing_anchor_controls(tmp_path):
    d = tmp_path / "fresh"
    d.mkdir()
    jp = str(d / "rebinds.jsonl")
    h = _start(jp)                                      # genuine first use
    assert h.journal_status()["healthy"] is True and os.path.isfile(jp + ".id")
    assert _start(jp).journal_status()["healthy"] is True   # regular pair adopted


@pytest.mark.parametrize("err", [errno.EIO, errno.EACCES, errno.ENOTDIR])
def test_anchor_lstat_error_fences_unwritable(tmp_path, monkeypatch, err):
    d = tmp_path / str(err)
    d.mkdir()
    jp = str(d / "rebinds.jsonl")
    real = os.lstat

    def f(p, *a, **k):
        if os.fspath(p) == jp + ".id":
            raise OSError(err, "injected", p)
        return real(p, *a, **k)
    monkeypatch.setattr(os, "lstat", f)
    h = _start(jp)
    monkeypatch.undo()
    assert _fence(h)["kind"] == "unwritable"
    assert not os.path.lexists(jp) and not os.path.lexists(jp + ".id")


def test_runtime_journal_swapped_for_symlink_fences(tmp_path):
    jp, _ = _pair(tmp_path, "rt")
    h = _start(jp)
    assert h.journal_status()["healthy"] is True
    real = jp + ".real"
    os.replace(jp, real)
    os.symlink(real, jp)
    assert h.verify_journal() is False and _fence(h)["kind"] == "changed"


def test_failed_reset_audit_carries_presence_error(tmp_path, monkeypatch):
    jp, h = _pair(tmp_path, "low")
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
    f, a = _fence(h), h.journal_status()["journal_resets"][-1]
    assert f["intent_present"] is None and a["intent_present"] is None
    assert a["presence_error"] == f["presence_error"]
    assert "injected handler lstat" in a["presence_error"]
