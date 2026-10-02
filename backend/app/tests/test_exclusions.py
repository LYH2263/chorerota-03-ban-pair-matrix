import pytest
from app.db import connect
from app.seed import init_db
from app.modules import exclusions as excl


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    init_db()  # 种子：成员 1/2/3 在岗 clean，成员 4 停用 dirty；任务 1/2/3 clean
    c = connect()
    yield c
    c.close()


def count(c):
    return c.execute("SELECT COUNT(*) n FROM exclusions").fetchone()["n"]


def test_add_list_and_live_pairs(db):
    row = excl.add_exclusion(db, 1, 2)
    assert row == {"id": row["id"], "member_id": 1, "task_id": 2}
    assert excl.live_pairs(db) == {(1, 2)}
    assert [r["member_id"] for r in excl.list_exclusions(db)] == [1]


def test_reject_duplicate_keeps_matrix_unchanged(db):
    excl.add_exclusion(db, 1, 2)
    with pytest.raises(excl.ExclusionError, match="duplicate_exclusion"):
        excl.add_exclusion(db, 1, 2)
    assert count(db) == 1


def test_reject_unknown_ids(db):
    with pytest.raises(excl.ExclusionError, match="member_not_found"):
        excl.add_exclusion(db, 999, 1)
    with pytest.raises(excl.ExclusionError, match="task_not_found"):
        excl.add_exclusion(db, 1, 999)
    assert count(db) == 0


def test_reject_inactive_or_dirty_member(db):
    # 种子成员 4：停用且 dirty
    with pytest.raises(excl.ExclusionError, match="member_not_assignable"):
        excl.add_exclusion(db, 4, 1)
    # 停用但 clean / 在岗但 dirty 同样拒写
    db.execute("INSERT INTO members(name,active,data_quality) VALUES ('停用干净',0,'clean')")
    db.execute("INSERT INTO members(name,active,data_quality) VALUES ('在岗脏',1,'dirty')")
    with pytest.raises(excl.ExclusionError, match="member_not_assignable"):
        excl.add_exclusion(db, 5, 1)
    with pytest.raises(excl.ExclusionError, match="member_not_assignable"):
        excl.add_exclusion(db, 6, 1)
    assert count(db) == 0


def test_remove_exclusion(db):
    row = excl.add_exclusion(db, 2, 3)
    assert excl.remove_exclusion(db, row["id"]) is True
    assert excl.live_pairs(db) == set()
    assert excl.remove_exclusion(db, row["id"]) is False


def test_snapshot_pinned_and_immune_to_live_edits(db):
    excl.add_exclusion(db, 1, 1)
    excl.add_exclusion(db, 2, 2)
    pinned = excl.pin_snapshot(db, 1)
    db.commit()
    assert {(r["member_id"], r["task_id"]) for r in pinned} == {(1, 1), (2, 2)}
    # 只改现行矩阵：已钉快照不动
    excl.remove_exclusion(db, 1)
    excl.add_exclusion(db, 3, 3)
    assert {(r["member_id"], r["task_id"]) for r in excl.snapshot_for_week(db, 1)} == {(1, 1), (2, 2)}
    # 重新钉存（重生成）才跟随现行矩阵
    excl.pin_snapshot(db, 1)
    assert {(r["member_id"], r["task_id"]) for r in excl.snapshot_for_week(db, 1)} == {(2, 2), (3, 3)}
