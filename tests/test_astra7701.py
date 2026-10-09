"""Astra 7701 (docs/ASTRA_REVIEW_7701.md, 1a87ae9) on 865fd63.
1 Med F-startup-identity-adoption: the identity anchor is written+fsync'd
      BEFORE the journal; a journal without a matching anchor always fences.
2 Med F-legacy-marker-startup-bypass: any pre-v5 artifact (old fence files,
      cancelled/abort records, v1-v4 journal) fences BEFORE create/adopt,
      with a migration message.
"""
import json
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import run
from tests.test_astra7656 import S


class Crash(BaseException):
    """Simulated process death (not caught by the reducer's OSError paths)."""


def _held(h):
    return h._plan_owner.get("a1:p") is None and h.owner_rebinds == []


# ------------------------------------------------ 1 anchor first, never adopt
def test_crash_between_anchor_and_journal_creation_fences(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    real = hr.HiveReducer._replace_durably

    def crash_on_journal(self, path, data):
        if path == jp:
            raise Crash()
        return real(self, path, data)
    monkeypatch.setattr(hr.HiveReducer, "_replace_durably", crash_on_journal)
    with pytest.raises(Crash):
        run(S, journal=jp)
    monkeypatch.undo()
    assert os.path.exists(jp + ".id") and not os.path.exists(jp)  # anchor FIRST
    h = run(S, journal=jp)
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["kind"] == "identity"
    assert not os.path.exists(jp)                       # nothing created/adopted
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.clear_journal_fence(actor="op", reason="interrupted create")
    h2 = run(S, journal=jp)
    assert h2.journal_status()["healthy"] is True
    assert h2.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_crash_after_journal_before_anchor_fences(tmp_path):
    # Astra's focused7701.startup_identity disk state (old create order):
    # a genuine hashed header-only journal and no .id
    jp = str(tmp_path / "rebinds.jsonl")
    hdr = hr.HiveReducer._header_record("deadbeef" * 4)
    open(jp, "w").write(json.dumps(hdr, sort_keys=True) + "\n")
    for _ in range(2):                                   # every restart
        h = run(S, journal=jp)
        st = h.journal_status()
        assert st["healthy"] is False and st["fence"]["kind"] == "identity"
        assert not os.path.exists(jp + ".id")
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_empty_journal_file_fences(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    open(jp, "w").close()
    st = run(S, journal=jp).journal_status()
    assert st["healthy"] is False and st["fence"]["kind"] == "identity"


# ------------------------------------------------ 2 legacy artifacts first
@pytest.mark.parametrize("sfx", [".fence", ".fence.tmp"])
@pytest.mark.parametrize("state", ["none", "header_only", "anchor_only"])
def test_legacy_marker_fences_before_create_or_adopt(tmp_path, sfx, state):
    jp = str(tmp_path / "rebinds.jsonl")
    if state != "none":
        run(S, journal=jp)
        if state == "anchor_only":
            os.unlink(jp)
    before = sorted(os.listdir(tmp_path))
    open(jp + sfx, "w").write("{}")
    for _ in range(2):                                   # two plain restarts
        h = run(S, journal=jp)
        st = h.journal_status()
        assert st["healthy"] is False and st["fence"]["kind"] == "legacy"
        assert "MIGRATION" in st["fence"]["error"]
        assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
        assert _held(h)
        assert sorted(os.listdir(tmp_path)) == sorted(before + [os.path.basename(jp + sfx)])
    assert h.clear_journal_fence(actor="op", reason="migrated")
    assert not os.path.exists(jp + sfx)
    assert any(n.startswith(os.path.basename(jp + sfx) + ".cleared-")
               for n in os.listdir(tmp_path))
    h2 = run(S, journal=jp)
    assert h2.journal_status()["healthy"] is True
    r = h2.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert r and r.status == "applied"
    for _ in range(2):                                   # Astra's witness
        assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


def _legacy_lines():
    return [
        {"v": 3, "op": "owner_rebind", "op_id": "o1", "agent_id": "a1",
         "plan_id": "p", "incident_id": "i", "actor": "op", "reason": "t"},
        {"v": 3, "op": "abort_rebind", "op_id": "o1"},          # cancelled
        {"v": 4, "op": "rebind_pending", "op_id": "o2", "agent_id": "a1",
         "plan_id": "p", "incident_id": "i", "prev": ""},
    ]


@pytest.mark.parametrize("k", [0, 1, 2])
def test_legacy_journal_records_fence_with_migration(tmp_path, k):
    jp = str(tmp_path / "rebinds.jsonl")
    open(jp, "w").write(json.dumps(_legacy_lines()[k]) + "\n")
    h = run(S, journal=jp)
    st = h.journal_status()
    assert st["fence"]["kind"] == "legacy" and "MIGRATION" in st["fence"]["error"]
    assert _held(h) and not os.path.exists(jp + ".id")  # nothing created
    old = open(jp, "rb").read()
    assert h.clear_journal_fence(actor="op", reason="migrated")
    arch = h.journal_status()["fence_clearances"][-1]["archived"]
    assert open(arch, "rb").read() == old                # kept byte-for-byte
    assert run(S, journal=jp).journal_status()["healthy"] is True


def test_legacy_record_after_valid_v5_prefix_fences(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    run(S, journal=jp)
    with open(jp, "a") as f:
        f.write(json.dumps(_legacy_lines()[1]) + "\n")
    st = run(S, journal=jp).journal_status()
    assert st["fence"]["kind"] == "legacy"
