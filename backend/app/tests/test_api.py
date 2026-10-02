import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.main import app
    with TestClient(app) as cl:
        yield cl


def gen(client, week=1):
    r = client.post(f"/api/weeks/{week}/generate", json={})
    assert r.status_code == 200
    return r.json()


def test_generate_without_exclusions_matches_legacy_and_board(client):
    # 无禁配回退：与改造前同参一致（种子成员 1/2/3、任务 1/2/3，每天依次 1→2→3）
    out = gen(client)
    assert out["count"] == 21 and out["gaps"] == [] and out["exclusions"] == []
    first = [s for s in out["slots"] if s["day"] == 0]
    assert [(s["task_id"], s["member_id"]) for s in first] == [(1, 1), (2, 2), (3, 3)]
    # 生成回包与看板一致
    board = client.get("/api/weeks/1/board").json()
    got = sorted((a["day"], a["task_id"], a["member_id"]) for a in board["assignments"])
    want = sorted((s["day"], s["task_id"], s["member_id"]) for s in out["slots"])
    assert got == want and board["gaps"] == []


def test_generate_with_exclusion_bumps_and_pins_snapshot(client):
    assert client.post("/api/exclusions", json={"member_id": 1, "task_id": 1}).status_code == 200
    out = gen(client)
    # 每天任务 1 的基准成员是 1，禁配 (1,1) 后顺移给成员 2，相位继续
    t1 = [s for s in out["slots"] if s["task_id"] == 1]
    assert all(s["member_id"] == 2 for s in t1) and len(t1) == 7
    assert out["gaps"] == [] and len(out["exclusions"]) == 1
    snap = client.get("/api/weeks/1/exclusions").json()
    assert [(s["member_id"], s["task_id"]) for s in snap] == [(1, 1)]
    # 只改现行矩阵：旧周格位与快照都不重切
    board_before = client.get("/api/weeks/1/board").json()["assignments"]
    eid = client.get("/api/exclusions").json()[0]["id"]
    assert client.delete(f"/api/exclusions/{eid}").status_code == 200
    assert client.get("/api/weeks/1/board").json()["assignments"] == board_before
    assert len(client.get("/api/weeks/1/exclusions").json()) == 1


def test_generate_all_excluded_records_gaps_consistently(client):
    for mid in (1, 2, 3):
        assert client.post("/api/exclusions", json={"member_id": mid, "task_id": 1}).status_code == 200
    out = gen(client)
    # 无人可派取舍：跳过任务 1 全部 7 格并记缺口，其余 14 格照常
    assert out["count"] == 14
    assert sorted((g["day"], g["task_id"]) for g in out["gaps"]) == [(d, 1) for d in range(7)]
    board = client.get("/api/weeks/1/board").json()
    assert sorted((g["day"], g["task_id"]) for g in board["gaps"]) == [(d, 1) for d in range(7)]
    assert all(a["task_id"] != 1 for a in board["assignments"])


def test_illegal_exclusions_rejected_without_growing_matrix(client):
    assert client.post("/api/exclusions", json={"member_id": 1, "task_id": 2}).status_code == 200
    for body, reason in [
        ({"member_id": 1, "task_id": 2}, "duplicate_exclusion"),
        ({"member_id": 999, "task_id": 1}, "member_not_found"),
        ({"member_id": 1, "task_id": 999}, "task_not_found"),
        ({"member_id": 4, "task_id": 1}, "member_not_assignable"),  # 种子：停用 dirty
    ]:
        r = client.post("/api/exclusions", json=body)
        assert r.status_code == 400 and r.json()["detail"] == reason
    assert len(client.get("/api/exclusions").json()) == 1


def test_swap_confirm_gated_by_exclusion_added_after_generation(client):
    gen(client)  # (day0,task1)→成员1，(day0,task2)→成员2
    r = client.post("/api/weeks/1/swaps", json={"a_day": 0, "a_task": 1, "b_day": 0, "b_task": 2})
    assert r.status_code == 200
    sid = r.json()["id"]
    # 生成后新增禁配：旧周格位不动，但确认对调若会形成禁配对 → 失败且格表不动
    assert client.post("/api/exclusions", json={"member_id": 1, "task_id": 2}).status_code == 200
    before = client.get("/api/weeks/1/board").json()["assignments"]
    r = client.post(f"/api/swaps/{sid}/confirm")
    assert r.status_code == 400 and r.json()["detail"] == "exclusion_conflict"
    assert client.get("/api/weeks/1/board").json()["assignments"] == before


def test_swap_request_gated_by_live_exclusion(client):
    gen(client)
    assert client.post("/api/exclusions", json={"member_id": 1, "task_id": 2}).status_code == 200
    r = client.post("/api/weeks/1/swaps", json={"a_day": 0, "a_task": 1, "b_day": 0, "b_task": 2})
    assert r.status_code == 400 and r.json()["detail"] == "exclusion_conflict"
