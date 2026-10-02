"""周表生成落库：同一事务内钉禁配快照并重排当周格位。

调用方负责 commit / close；本模块任何异常都不应被 commit，
无人可派时在写入前抛 GenerationBlocked，旧表与旧快照原样保留。
"""

from app.engines.rota import UnassignableSlot, build_week_slots
from app.modules import member_task_ban as bans


class GenerationBlocked(Exception):
    """禁配导致某格无人可派，整次生成作废。"""

    def __init__(self, day: int, task_id: int):
        self.day = day
        self.task_id = task_id
        super().__init__(f"unassignable day={day} task_id={task_id}")


def generate_week(c, week_id: int, days: int = 7) -> dict:
    week = c.execute("SELECT id FROM weeks WHERE id=?", (week_id,)).fetchone()
    if week is None:
        raise LookupError("week not found")

    mids = [r["id"] for r in c.execute(
        "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]
    tids = [r["id"] for r in c.execute(
        "SELECT id FROM tasks WHERE data_quality='clean' AND weight>0 ORDER BY id")]
    pairs = bans.current_pairs(c)

    # 先纯计算：无人可派时在这里抛出，此前没有任何写入，旧表不动。
    try:
        slots = build_week_slots(mids, tids, days=days, banned_pairs=pairs)
    except UnassignableSlot as e:
        raise GenerationBlocked(e.day, e.task_id) from e

    # 钉快照与落格位同一事务，一起提交或一起回滚。
    bans.pin_snapshot(c, week_id, pairs)
    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    c.executemany(
        "INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (?,?,?,?)",
        [(week_id, s["day"], s["task_id"], s["member_id"]) for s in slots],
    )
    c.execute("UPDATE weeks SET status='ready' WHERE id=?", (week_id,))
    return {
        "count": len(slots),
        "slots": slots,
        "snapshot": bans.list_snapshot(c, week_id),
    }
