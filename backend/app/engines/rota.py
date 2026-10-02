"""Round-robin weekly chore assignments + swap legality."""

def build_week_slots(member_ids: list[int], task_ids: list[int], days: int = 7,
                     exclusions: set[tuple[int, int]] = frozenset()) -> dict:
    """Assign each (day, task) to members in round-robin by task then day.

    禁配规避：槽位基准相位恒为槽位序号 idx（与改造前一致），命中禁配时
    只在本槽位内顺移取下一位可派成员，相位不因此消耗——无禁配时输出与
    旧版逐格一致。某 (day, task) 全员禁配则跳过该格并记缺口。
    """
    if not member_ids or not task_ids:
        return {"slots": [], "gaps": []}
    slots, gaps = [], []
    idx = 0
    for day in range(days):
        for tid in task_ids:
            base = idx % len(member_ids)
            picked = None
            for step in range(len(member_ids)):
                cand = member_ids[(base + step) % len(member_ids)]
                if (cand, tid) not in exclusions:
                    picked = cand
                    break
            if picked is None:
                gaps.append({"day": day, "task_id": tid, "reason": "no_eligible_member"})
            else:
                slots.append({"day": day, "task_id": tid, "member_id": picked})
            idx += 1
    return {"slots": slots, "gaps": gaps}


def swap_legal(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> dict:
    """Two slots may swap only if both exist, different assignees, same week grid."""
    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None
    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return {"ok": False, "reason": "slot_missing"}
    if sa["member_id"] == sb["member_id"]:
        return {"ok": False, "reason": "same_assignee"}
    if a_day == b_day and a_task == b_task:
        return {"ok": False, "reason": "same_slot"}
    return {
        "ok": True,
        "reason": "",
        "a_member": sa["member_id"],
        "b_member": sb["member_id"],
    }


def apply_swap(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> list[dict]:
    check = swap_legal(slots, a_day, a_task, b_day, b_task)
    if not check["ok"]:
        raise ValueError(check["reason"])
    out = [dict(s) for s in slots]
    ia = next(i for i, s in enumerate(out) if s["day"] == a_day and s["task_id"] == a_task)
    ib = next(i for i, s in enumerate(out) if s["day"] == b_day and s["task_id"] == b_task)
    out[ia]["member_id"], out[ib]["member_id"] = out[ib]["member_id"], out[ia]["member_id"]
    return out


def swap_exclusion_conflicts(slots: list[dict], exclusions: set[tuple[int, int]],
                             a_day: int, a_task: int, b_day: int, b_task: int) -> list[dict]:
    """对调门禁：若交换后某格会形成禁配对，返回冲突列表（空=放行）。

    纯函数，不改动 slots；门禁用现行禁配矩阵，与已钉周快照无关。
    """
    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None
    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return []
    conflicts = []
    if (sa["member_id"], sb["task_id"]) in exclusions:
        conflicts.append({"member_id": sa["member_id"], "task_id": sb["task_id"]})
    if (sb["member_id"], sa["task_id"]) in exclusions:
        conflicts.append({"member_id": sb["member_id"], "task_id": sa["task_id"]})
    return conflicts
