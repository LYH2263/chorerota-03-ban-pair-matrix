"""Round-robin weekly chore assignments + swap legality.

禁配（member 不得做 task）在两个环节生效：
- build_week_slots：撞禁配则从当前相位起改派下一位成员，相位照常 +1；
  某格所有候选成员都被禁配时抛 UnassignableSlot。
- swap_legal/apply_swap：确认对调不得让任一格形成禁配（ban_conflict）。
"""


class UnassignableSlot(Exception):
    """某 (day, task) 在禁配矩阵下无人可派。"""

    def __init__(self, day: int, task_id: int):
        self.day = day
        self.task_id = task_id
        super().__init__(f"no eligible member for day={day} task_id={task_id}")


def build_week_slots(
    member_ids: list[int],
    task_ids: list[int],
    days: int = 7,
    banned_pairs: set[tuple[int, int]] | None = None,
) -> list[dict]:
    """Assign each (day, task) to members in round-robin by task then day.

    banned_pairs 为 (member_id, task_id) 禁配集合。从当前相位起取第一位
    未被该任务禁配的成员；每格相位固定 +1（跳过不改相位）。无禁配时
    输出与无禁配版本逐位一致。候选全员禁配时抛 UnassignableSlot。
    """
    if not member_ids or not task_ids:
        return []
    banned = banned_pairs or set()
    n = len(member_ids)
    slots = []
    idx = 0
    for day in range(days):
        for tid in task_ids:
            chosen = None
            for offset in range(n):
                mid = member_ids[(idx + offset) % n]
                if (mid, tid) not in banned:
                    chosen = mid
                    break
            if chosen is None:
                raise UnassignableSlot(day, tid)
            slots.append({"day": day, "task_id": tid, "member_id": chosen})
            idx += 1
    return slots


def swap_legal(
    slots: list[dict],
    a_day: int,
    a_task: int,
    b_day: int,
    b_task: int,
    banned_pairs: set[tuple[int, int]] | None = None,
) -> dict:
    """Two slots may swap only if both exist, different assignees, same week grid.

    额外门禁：交换后两格的 (member, task) 均不得落在 banned_pairs 中。
    """
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
    banned = banned_pairs or set()
    if banned:
        # 交换后：a 格由 B 的成员做 a_task，b 格由 A 的成员做 b_task
        if (sb["member_id"], a_task) in banned or (sa["member_id"], b_task) in banned:
            return {"ok": False, "reason": "ban_conflict"}
    return {
        "ok": True,
        "reason": "",
        "a_member": sa["member_id"],
        "b_member": sb["member_id"],
    }


def apply_swap(
    slots: list[dict],
    a_day: int,
    a_task: int,
    b_day: int,
    b_task: int,
    banned_pairs: set[tuple[int, int]] | None = None,
) -> list[dict]:
    check = swap_legal(slots, a_day, a_task, b_day, b_task, banned_pairs)
    if not check["ok"]:
        raise ValueError(check["reason"])
    out = [dict(s) for s in slots]
    ia = next(i for i, s in enumerate(out) if s["day"] == a_day and s["task_id"] == a_task)
    ib = next(i for i, s in enumerate(out) if s["day"] == b_day and s["task_id"] == b_task)
    out[ia]["member_id"], out[ib]["member_id"] = out[ib]["member_id"], out[ia]["member_id"]
    return out
