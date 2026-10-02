import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.rota import swap_legal, apply_swap, swap_exclusion_conflicts
from app.modules import exclusions as excl
from app.services.generation import generate_week

app = FastAPI(title="Chorerota", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

@app.get("/api/health")
def health(): return {"ok": True, "project": "chorerota"}

@app.get("/api/members")
def list_members():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM members")]; c.close(); return rows

@app.post("/api/members")
def add_member(body: dict):
    c = connect()
    cur = c.execute("INSERT INTO members(name,active,data_quality) VALUES (?,?,?)",
                    (body.get("name","未命名"), int(body.get("active",1)), body.get("data_quality","clean")))
    c.commit(); mid = cur.lastrowid; c.close(); return {"id": mid}

@app.get("/api/tasks")
def list_tasks():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM tasks")]; c.close(); return rows

@app.post("/api/tasks")
def add_task(body: dict):
    c = connect()
    cur = c.execute("INSERT INTO tasks(title,weight,data_quality) VALUES (?,?,?)",
                    (body.get("title","任务"), int(body.get("weight",1)), body.get("data_quality","clean")))
    c.commit(); tid = cur.lastrowid; c.close(); return {"id": tid}

@app.get("/api/exclusions")
def list_exclusions():
    c = connect()
    rows = [dict(r) for r in c.execute("""
        SELECT e.id, e.member_id, e.task_id, m.name AS member_name, t.title AS task_title
        FROM exclusions e
        LEFT JOIN members m ON m.id=e.member_id
        LEFT JOIN tasks t ON t.id=e.task_id
        ORDER BY e.id""")]
    c.close(); return rows

class ExclusionBody(BaseModel):
    member_id: int
    task_id: int

@app.post("/api/exclusions")
def add_exclusion(body: ExclusionBody):
    c = connect()
    try:
        row = excl.add_exclusion(c, body.member_id, body.task_id)
    except excl.ExclusionError as e:
        c.close(); raise HTTPException(400, e.reason)
    c.close(); return row

@app.delete("/api/exclusions/{exclusion_id}")
def delete_exclusion(exclusion_id: int):
    c = connect()
    ok = excl.remove_exclusion(c, exclusion_id)
    c.close()
    if not ok: raise HTTPException(404, "exclusion_not_found")
    return {"ok": True}

@app.get("/api/weeks/{week_id}/exclusions")
def week_exclusion_snapshot(week_id: int):
    """按周回看：生成时钉下的禁配快照，与当周格位同源，不随现行矩阵改动。"""
    c = connect()
    rows = [dict(r) for r in c.execute("""
        SELECT w.member_id, w.task_id, m.name AS member_name, t.title AS task_title
        FROM week_exclusions w
        LEFT JOIN members m ON m.id=w.member_id
        LEFT JOIN tasks t ON t.id=w.task_id
        WHERE w.week_id=? ORDER BY w.id""", (week_id,))]
    c.close(); return rows

@app.get("/api/weeks")
def list_weeks():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM weeks")]; c.close(); return rows

@app.get("/api/weeks/{week_id}/board")
def week_board(week_id: int):
    c = connect()
    week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week: c.close(); raise HTTPException(404, "week not found")
    assigns = [dict(r) for r in c.execute("SELECT * FROM assignments WHERE week_id=?", (week_id,))]
    gaps = [dict(r) for r in c.execute(
        "SELECT day,task_id,reason FROM assignment_gaps WHERE week_id=? ORDER BY day,task_id", (week_id,))]
    members = {r["id"]: r["name"] for r in c.execute("SELECT id,name FROM members")}
    tasks = {r["id"]: r["title"] for r in c.execute("SELECT id,title FROM tasks")}
    c.close()
    for a in assigns:
        a["member_name"] = members.get(a["member_id"], "?")
        a["task_title"] = tasks.get(a["task_id"], "?")
    for g in gaps:
        g["task_title"] = tasks.get(g["task_id"], "?")
    return {"week": dict(week), "assignments": assigns, "gaps": gaps}

class GenBody(BaseModel):
    days: int = 7

@app.post("/api/weeks/{week_id}/generate")
def generate(week_id: int, body: GenBody = GenBody()):
    c = connect()
    week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week: c.close(); raise HTTPException(404, "week not found")
    result = generate_week(c, week_id, days=body.days)
    c.close()
    return result

class SwapBody(BaseModel):
    a_day: int; a_task: int; b_day: int; b_task: int; note: str = ""

@app.post("/api/weeks/{week_id}/swaps")
def request_swap(week_id: int, body: SwapBody):
    c = connect()
    assigns = [dict(r) for r in c.execute("SELECT day,task_id,member_id FROM assignments WHERE week_id=?", (week_id,))]
    check = swap_legal(assigns, body.a_day, body.a_task, body.b_day, body.b_task)
    if not check["ok"]:
        c.close(); raise HTTPException(400, check["reason"])
    if swap_exclusion_conflicts(assigns, excl.live_pairs(c), body.a_day, body.a_task, body.b_day, body.b_task):
        c.close(); raise HTTPException(400, "exclusion_conflict")
    cur = c.execute(
        "INSERT INTO swap_requests(week_id,a_day,a_task,b_day,b_task,status,note) VALUES (?,?,?,?,?,?,?)",
        (week_id, body.a_day, body.a_task, body.b_day, body.b_task, "pending", body.note))
    c.commit(); sid = cur.lastrowid; c.close()
    return {"id": sid, "status": "pending", **check}

@app.get("/api/swaps")
def list_swaps():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM swap_requests ORDER BY id DESC")]; c.close(); return rows

@app.post("/api/swaps/{swap_id}/confirm")
def confirm_swap(swap_id: int):
    c = connect()
    sw = c.execute("SELECT * FROM swap_requests WHERE id=?", (swap_id,)).fetchone()
    if not sw: c.close(); raise HTTPException(404, "swap not found")
    if sw["status"] != "pending":
        c.close(); raise HTTPException(400, "not_pending")
    assigns = [dict(r) for r in c.execute(
        "SELECT id,day,task_id,member_id FROM assignments WHERE week_id=?", (sw["week_id"],))]
    slots = [{"day": a["day"], "task_id": a["task_id"], "member_id": a["member_id"]} for a in assigns]
    # 对调门禁：以现行禁配矩阵复核（生成后新增禁配不改旧周，但拦住促成禁配的对调）
    if swap_exclusion_conflicts(slots, excl.live_pairs(c), sw["a_day"], sw["a_task"], sw["b_day"], sw["b_task"]):
        c.close(); raise HTTPException(400, "exclusion_conflict")
    try:
        new_slots = apply_swap(slots, sw["a_day"], sw["a_task"], sw["b_day"], sw["b_task"])
    except ValueError as e:
        c.close(); raise HTTPException(400, str(e))
    for a, s in zip(assigns, new_slots):
        c.execute("UPDATE assignments SET member_id=? WHERE id=?", (s["member_id"], a["id"]))
    c.execute("UPDATE swap_requests SET status='confirmed' WHERE id=?", (swap_id,))
    c.commit(); c.close()
    return {"ok": True, "swap_id": swap_id}

@app.get("/api/settings")
def get_settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.put("/api/settings")
def put_settings(body: dict):
    c = connect()
    for k, v in body.items():
        c.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    c.commit(); c.close(); return {"ok": True}
