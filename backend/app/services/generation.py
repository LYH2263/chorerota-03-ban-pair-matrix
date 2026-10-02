"""生成落库：读现行禁配矩阵 → 引擎排班 → 落 assignments/gaps/禁配快照/周状态。

取舍拍板：某 (day, task) 全员禁配时跳过该格并落 assignment_gaps，
不整次失败；生成回包与看板读同一份落库数据，二者一致。
"""
from app.engines.rota import build_week_slots
from app.modules import exclusions as excl


def generate_week(c, week_id: int, days: int = 7) -> dict:
    mids = [r["id"] for r in c.execute(
        "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]
    tids = [r["id"] for r in c.execute(
        "SELECT id FROM tasks WHERE data_quality='clean' AND weight>0 ORDER BY id")]
    result = build_week_slots(mids, tids, days=days, exclusions=excl.live_pairs(c))
    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    for s in result["slots"]:
        c.execute("INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (?,?,?,?)",
                  (week_id, s["day"], s["task_id"], s["member_id"]))
    c.execute("DELETE FROM assignment_gaps WHERE week_id=?", (week_id,))
    for g in result["gaps"]:
        c.execute("INSERT INTO assignment_gaps(week_id,day,task_id,reason) VALUES (?,?,?,?)",
                  (week_id, g["day"], g["task_id"], g["reason"]))
    snapshot = excl.pin_snapshot(c, week_id)
    c.execute("UPDATE weeks SET status='ready' WHERE id=?", (week_id,))
    c.commit()
    return {"count": len(result["slots"]), "slots": result["slots"],
            "gaps": result["gaps"], "exclusions": snapshot}
