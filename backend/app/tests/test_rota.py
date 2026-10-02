from app.engines.rota import build_week_slots, swap_legal, apply_swap, swap_exclusion_conflicts

def test_round_robin_covers_grid():
    slots = build_week_slots([1, 2, 3], [10, 20], days=7)["slots"]
    assert len(slots) == 14
    assert slots[0]["member_id"] == 1
    assert slots[1]["member_id"] == 2
    assert slots[3]["member_id"] == 1  # wraps

def test_no_exclusions_matches_legacy_sequence():
    # 无禁配回退：逐格与改造前同参一致
    out = build_week_slots([1, 2, 3], [10, 20], days=2)
    assert out["gaps"] == []
    assert out["slots"] == [
        {"day": 0, "task_id": 10, "member_id": 1},
        {"day": 0, "task_id": 20, "member_id": 2},
        {"day": 1, "task_id": 10, "member_id": 3},
        {"day": 1, "task_id": 20, "member_id": 1},
    ]

def test_exclusion_bumps_to_next_member_and_phase_continues():
    # 有禁配改派：槽位 0 基准是成员 1，禁配 (1,10) 顺移给成员 2；
    # 相位不被顺移消耗——后续槽位基准仍按槽位序号走（成员 2、3）
    out = build_week_slots([1, 2, 3, 4], [10], days=3, exclusions={(1, 10)})
    assert [s["member_id"] for s in out["slots"]] == [2, 2, 3]
    assert out["gaps"] == []

def test_all_excluded_records_gap_and_skips_cell():
    # 无人可派取舍：跳过该格并记缺口，其余格位不受影响
    out = build_week_slots([1, 2], [10, 20], days=1, exclusions={(1, 10), (2, 10)})
    assert out["slots"] == [{"day": 0, "task_id": 20, "member_id": 2}]
    assert out["gaps"] == [{"day": 0, "task_id": 10, "reason": "no_eligible_member"}]

def test_swap_rejects_same_assignee():
    slots = [{"day": 0, "task_id": 1, "member_id": 9}, {"day": 1, "task_id": 1, "member_id": 9}]
    r = swap_legal(slots, 0, 1, 1, 1)
    assert r["ok"] is False and r["reason"] == "same_assignee"

def test_apply_swap_exchanges():
    slots = build_week_slots([1, 2], [10], days=2)["slots"]
    out = apply_swap(slots, 0, 10, 1, 10)
    assert out[0]["member_id"] == 2 and out[1]["member_id"] == 1

def test_swap_exclusion_conflicts_detects_pair_after_swap():
    slots = [{"day": 0, "task_id": 10, "member_id": 1},
             {"day": 1, "task_id": 20, "member_id": 2}]
    # 交换后成员 1 会落到任务 20 → 命中禁配 (1,20)
    assert swap_exclusion_conflicts(slots, {(1, 20)}, 0, 10, 1, 20) == [{"member_id": 1, "task_id": 20}]
    # 无禁配 / 不涉及的禁配 → 放行
    assert swap_exclusion_conflicts(slots, set(), 0, 10, 1, 20) == []
    assert swap_exclusion_conflicts(slots, {(1, 10)}, 0, 10, 1, 20) == []
