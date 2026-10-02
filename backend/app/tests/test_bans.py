"""禁配矩阵：引擎规避、仓储拒写、生成落库/快照的集成测例。"""

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmp

from app import seed  # noqa: E402
from app.db import connect  # noqa: E402
from app.engines.rota import (  # noqa: E402
    UnassignableSlot,
    apply_swap,
    build_week_slots,
    swap_legal,
)
from app.modules import member_task_ban as bans  # noqa: E402
from app.modules.week_generation import GenerationBlocked, generate_week  # noqa: E402


@pytest.fixture()
def db():
    # 每个用例一个独立库文件：连接按 DATA_DIR 单文件，故用子目录隔离。
    d = tempfile.mkdtemp()
    os.environ["DATA_DIR"] = d
    seed.init_db()
    c = connect()
    yield c
    c.close()


def _add(c, sql, args):
    return c.execute(sql, args).lastrowid


# ---------- 引擎：无禁配回退一致 ----------

def test_no_ban_matches_legacy_round_robin():
    legacy = build_week_slots([1, 2, 3], [10, 20], days=7)
    assert legacy == build_week_slots([1, 2, 3], [10, 20], days=7, banned_pairs=set())
    assert legacy == build_week_slots([1, 2, 3], [10, 20], days=7,
                                      banned_pairs={(99, 99)})  # 不相关禁配
    assert len(legacy) == 14 and legacy[0]["member_id"] == 1
    assert legacy[3]["member_id"] == 1  # wraps


# ---------- 引擎：有禁配改派并继续相位 ----------

def test_ban_reassigns_to_next_member_phase_continues():
    # 3 成员 × 1 任务，禁 (1,10)：成员 1 轮到的每格都顺延给成员 2，
    # 相位仍逐格 +1。序列（idx=0..3）：2,2,3,2。
    slots = build_week_slots([1, 2, 3], [10], days=4, banned_pairs={(1, 10)})
    assert [s["member_id"] for s in slots] == [2, 2, 3, 2]
    assert all(s["task_id"] == 10 for s in slots)
    # 未禁配时同一相位序列是 1,2,3,1，证明只是就地顺延、没有重排
    assert [s["member_id"] for s in build_week_slots([1, 2, 3], [10], days=4)] == [1, 2, 3, 1]


def test_ban_scoped_per_task():
    # 禁 (1,10) 不影响成员 1 做任务 20：
    # d0/10 idx0→1 被禁→2；d0/20 idx1→2；d1/10 idx2→3；d1/20 idx3→0→1（可派 20）
    slots = build_week_slots([1, 2, 3], [10, 20], days=2, banned_pairs={(1, 10)})
    by = {(s["day"], s["task_id"]): s["member_id"] for s in slots}
    assert by[(0, 10)] == 2
    assert by[(1, 20)] == 1  # 同一成员在别的任务上照常落位
    assert all(s["member_id"] != 1 or s["task_id"] != 10 for s in slots)


def test_unassignable_when_all_banned():
    with pytest.raises(UnassignableSlot) as ei:
        build_week_slots([1, 2], [10], days=3, banned_pairs={(1, 10), (2, 10)})
    assert ei.value.day == 0 and ei.value.task_id == 10


# ---------- 对调门禁 ----------

def test_swap_blocked_by_ban_conflict():
    slots = build_week_slots([1, 2], [10], days=2)  # day0->1, day1->2
    # 对调后 day0 的 10 由成员 2 做，day1 由成员 1 做；禁 (1,10) 已在表内不触发，
    # 禁 (2,10) 会让 day0 形成禁配。
    r = swap_legal(slots, 0, 10, 1, 10, banned_pairs={(2, 10)})
    assert r["ok"] is False and r["reason"] == "ban_conflict"
    with pytest.raises(ValueError):
        apply_swap(slots, 0, 10, 1, 10, banned_pairs={(2, 10)})


def test_swap_ok_when_no_ban_after():
    slots = build_week_slots([1, 2], [10], days=2)
    r = swap_legal(slots, 0, 10, 1, 10, banned_pairs={(1, 20), (2, 20)})
    assert r["ok"] is True


# ---------- 仓储：非法禁配拒写 ----------

def test_add_ban_happy_path(db):
    bid = bans.add_ban(db, 1, 1)  # 阿明 × 洗碗
    db.commit()
    assert (1, 1) in bans.current_pairs(db)
    assert bid > 0


def test_duplicate_ban_rejected_no_row(db):
    bans.add_ban(db, 1, 1)
    db.commit()
    before = len(bans.list_bans(db))
    with pytest.raises(ValueError) as e:
        bans.add_ban(db, 1, 1)
    assert str(e.value) == "duplicate_ban"
    assert len(bans.list_bans(db)) == before


def test_ban_nonexistent_member_or_task(db):
    with pytest.raises(ValueError) as e:
        bans.add_ban(db, 999, 1)
    assert str(e.value) == "member_not_found"
    with pytest.raises(ValueError) as e:
        bans.add_ban(db, 1, 999)
    assert str(e.value) == "task_not_found"
    assert bans.current_pairs(db) == set()


def test_ban_inactive_or_dirty_member_rejected(db):
    ghost = db.execute("SELECT id FROM members WHERE name='幽灵成员'").fetchone()["id"]
    with pytest.raises(ValueError) as e:
        bans.add_ban(db, ghost, 1)
    assert str(e.value) == "member_ineligible"
    # 停用的 clean 成员同样拒绝
    mid = _add(db, "INSERT INTO members(name,active,data_quality) VALUES (?,?,?)",
               ("休假成员", 0, "clean"))
    with pytest.raises(ValueError) as e:
        bans.add_ban(db, mid, 1)
    assert str(e.value) == "member_ineligible"
    assert bans.current_pairs(db) == set()


# ---------- 生成落库：改派 / 整次失败保旧表 / 快照钉版 ----------

def test_generate_pins_snapshot_and_assigns(db):
    bans.add_ban(db, 1, 1)  # 阿明不洗碗
    db.commit()
    res = generate_week(db, 1, days=7)
    db.commit()
    # 回包含快照，且快照正是当周禁配
    assert res["snapshot"]["pinned"] is True
    assert {(b["member_id"], b["task_id"]) for b in res["snapshot"]["bans"]} == {(1, 1)}
    assert (1, 1) in bans.snapshot_pairs(db, 1)
    # 没有任何一格让成员 1 做任务 1
    assert all(not (s["member_id"] == 1 and s["task_id"] == 1) for s in res["slots"])
    assert res["count"] == 21  # 3 clean 任务 × 7（扫地 weight=2 仍是一行任务）


def test_generate_failure_keeps_old_board_and_snapshot(db):
    # 先生成一版干净周表 + 快照
    first = generate_week(db, 1, days=7)
    db.commit()
    old_assigns = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1")]
    assert first["count"] == 21

    # 让任务 1（洗碗）的 3 个活跃 clean 成员全部禁配 → 无人可派
    for mid in (1, 2, 3):
        bans.add_ban(db, mid, 1)
    db.commit()
    with pytest.raises(GenerationBlocked) as ei:
        generate_week(db, 1, days=7)
    db.rollback()
    assert ei.value.task_id == 1

    # 旧格位原样
    now_assigns = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1")]
    assert now_assigns == old_assigns
    # 旧快照仍是空集，新禁配没有钉进去
    assert bans.snapshot_pairs(db, 1) == set()
    assert db.execute("SELECT status FROM weeks WHERE id=1").fetchone()["status"] == "ready"


def test_new_ban_after_generation_does_not_recut_old_week(db):
    generate_week(db, 1, days=7)
    db.commit()
    before = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1 ORDER BY id")]
    bans.add_ban(db, 1, 1)
    db.commit()
    after = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1 ORDER BY id")]
    assert before == after  # 只改现行矩阵，不重切旧周
    # 旧周快照不含新禁配，但 effective_pairs（对调门禁）含
    assert (1, 1) not in bans.snapshot_pairs(db, 1)
    assert (1, 1) in bans.effective_pairs(db, 1)


def test_later_swap_blocked_by_new_ban_grid_unchanged(db):
    generate_week(db, 1, days=7)
    db.commit()
    before = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1 ORDER BY day,id")]
    # round-robin 下 day0 前两格：task1→成员1、task2→成员2（不同任务不同人）
    a, b = before[0], before[1]
    assert a["day"] == b["day"] == 0 and a["task_id"] != b["task_id"]
    assert a["member_id"] != b["member_id"]
    # 新增禁配：b 格成员不得做 a 格任务 → 对调后 a 格形成禁配
    bans.add_ban(db, b["member_id"], a["task_id"])
    db.commit()
    slots = [{"day": r["day"], "task_id": r["task_id"], "member_id": r["member_id"]}
             for r in before]
    check = swap_legal(slots, a["day"], a["task_id"], b["day"], b["task_id"],
                       banned_pairs=bans.effective_pairs(db, 1))
    assert check["ok"] is False and check["reason"] == "ban_conflict"
    with pytest.raises(ValueError):
        apply_swap(slots, a["day"], a["task_id"], b["day"], b["task_id"],
                   banned_pairs=bans.effective_pairs(db, 1))
    after = [dict(r) for r in db.execute(
        "SELECT day,task_id,member_id FROM assignments WHERE week_id=1 ORDER BY day,id")]
    assert after == before  # 门禁失败，格表不动
