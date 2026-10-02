"""禁配矩阵仓储：现行矩阵增删查 + 非法拒写 + 按周快照钉存/读取。

非法禁配（重复、指向不存在 id、指向脏/停用成员）一律抛 ExclusionError，
校验先于写入，矩阵不增行。快照在生成周表时整体钉入 week_exclusions，
之后只改现行矩阵不会影响已钉旧周。
"""


class ExclusionError(ValueError):
    """非法禁配。reason 为稳定错误码，供 API 层透传。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def list_exclusions(c) -> list[dict]:
    return [dict(r) for r in c.execute("SELECT * FROM exclusions ORDER BY id")]


def live_pairs(c) -> set[tuple[int, int]]:
    """现行禁配对集合 {(member_id, task_id)}，供引擎规避与对调门禁。"""
    return {(r["member_id"], r["task_id"]) for r in c.execute("SELECT member_id,task_id FROM exclusions")}


def add_exclusion(c, member_id: int, task_id: int) -> dict:
    m = c.execute("SELECT active,data_quality FROM members WHERE id=?", (member_id,)).fetchone()
    if m is None:
        raise ExclusionError("member_not_found")
    if not m["active"] or m["data_quality"] != "clean":
        raise ExclusionError("member_not_assignable")
    if c.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone() is None:
        raise ExclusionError("task_not_found")
    if c.execute("SELECT 1 FROM exclusions WHERE member_id=? AND task_id=?",
                 (member_id, task_id)).fetchone() is not None:
        raise ExclusionError("duplicate_exclusion")
    cur = c.execute("INSERT INTO exclusions(member_id,task_id) VALUES (?,?)", (member_id, task_id))
    c.commit()
    return {"id": cur.lastrowid, "member_id": member_id, "task_id": task_id}


def remove_exclusion(c, exclusion_id: int) -> bool:
    cur = c.execute("DELETE FROM exclusions WHERE id=?", (exclusion_id,))
    c.commit()
    return cur.rowcount > 0


def pin_snapshot(c, week_id: int) -> list[dict]:
    """把现行矩阵整体钉到当周（重生成则重钉），返回钉入行。不提交，由调用方统一提交。"""
    c.execute("DELETE FROM week_exclusions WHERE week_id=?", (week_id,))
    rows = list_exclusions(c)
    for r in rows:
        c.execute("INSERT INTO week_exclusions(week_id,member_id,task_id) VALUES (?,?,?)",
                  (week_id, r["member_id"], r["task_id"]))
    return [{"week_id": week_id, "member_id": r["member_id"], "task_id": r["task_id"]} for r in rows]


def snapshot_for_week(c, week_id: int) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT member_id,task_id FROM week_exclusions WHERE week_id=? ORDER BY id", (week_id,))]
