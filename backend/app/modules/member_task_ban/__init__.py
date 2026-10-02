"""人任禁配矩阵仓储。

两张层：
- member_task_bans：现行矩阵，随时可增删；
- week_ban_snapshots(_items)：每次生成周表时把当时的矩阵钉版到该周，
  之后现行矩阵再变动也不影响旧周格位与回看。

本模块只做存取与校验，调用方负责 commit / rollback。
非法禁配（重复、指向不存在 id、指向停用/脏成员）一律抛 ValueError，
且在抛错前不做任何写入，保证矩阵不增行。
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS member_task_bans(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(member_id, task_id)
);
CREATE TABLE IF NOT EXISTS week_ban_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id INTEGER NOT NULL UNIQUE,
    pinned_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS week_ban_snapshot_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL
);
"""

_LIST_SQL = """
SELECT b.id, b.member_id, b.task_id, m.name AS member_name, t.title AS task_title
FROM member_task_bans b
JOIN members m ON m.id = b.member_id
JOIN tasks t ON t.id = b.task_id
ORDER BY b.task_id, b.member_id, b.id
"""


def init_schema(c):
    c.executescript(SCHEMA)


def list_bans(c) -> list[dict]:
    """现行矩阵全部禁配行（带成员名/任务名）。"""
    return [dict(r) for r in c.execute(_LIST_SQL)]


def add_ban(c, member_id: int, task_id: int) -> int:
    """新增一条禁配；非法时抛 ValueError(code) 且不写入。返回新行 id。"""
    m = c.execute(
        "SELECT id,active,data_quality FROM members WHERE id=?", (member_id,)
    ).fetchone()
    if m is None:
        raise ValueError("member_not_found")
    if not m["active"] or m["data_quality"] != "clean":
        # 停用或脏数据成员不得进入矩阵
        raise ValueError("member_ineligible")
    if c.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone() is None:
        raise ValueError("task_not_found")
    dup = c.execute(
        "SELECT 1 FROM member_task_bans WHERE member_id=? AND task_id=?",
        (member_id, task_id),
    ).fetchone()
    if dup is not None:
        raise ValueError("duplicate_ban")
    cur = c.execute(
        "INSERT INTO member_task_bans(member_id,task_id) VALUES (?,?)",
        (member_id, task_id),
    )
    return cur.lastrowid


def remove_ban(c, ban_id: int) -> bool:
    cur = c.execute("DELETE FROM member_task_bans WHERE id=?", (ban_id,))
    return cur.rowcount > 0


def current_pairs(c) -> set[tuple[int, int]]:
    return {
        (r["member_id"], r["task_id"])
        for r in c.execute("SELECT member_id,task_id FROM member_task_bans")
    }


def pin_snapshot(c, week_id: int, pairs) -> int:
    """把一组禁配对钉版到某周（同周重新生成则整体替换）。"""
    c.execute("DELETE FROM week_ban_snapshot_items WHERE snapshot_id IN "
              "(SELECT id FROM week_ban_snapshots WHERE week_id=?)", (week_id,))
    c.execute("DELETE FROM week_ban_snapshots WHERE week_id=?", (week_id,))
    sid = c.execute(
        "INSERT INTO week_ban_snapshots(week_id) VALUES (?)", (week_id,)
    ).lastrowid
    c.executemany(
        "INSERT INTO week_ban_snapshot_items(snapshot_id,member_id,task_id) VALUES (?,?,?)",
        [(sid, m, t) for m, t in sorted(pairs)],
    )
    return sid


def snapshot_pairs(c, week_id: int) -> set[tuple[int, int]] | None:
    """某周钉版的禁配对；该周从未生成返回 None。"""
    row = c.execute(
        "SELECT id FROM week_ban_snapshots WHERE week_id=?", (week_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        (r["member_id"], r["task_id"])
        for r in c.execute(
            "SELECT member_id,task_id FROM week_ban_snapshot_items WHERE snapshot_id=?",
            (row["id"],),
        )
    }


def effective_pairs(c, week_id: int) -> set[tuple[int, int]]:
    """对调门禁用：当周钉版快照 ∪ 现行矩阵。

    生成后新增的禁配不会重切旧周格位，但若会让某次确认对调形成禁配，
    仍须拦下，所以两套禁配同时生效。
    """
    pairs = current_pairs(c)
    snap = snapshot_pairs(c, week_id)
    if snap:
        pairs |= snap
    return pairs


def list_snapshot(c, week_id: int) -> dict:
    """按周回看钉版禁配（带名称）；未钉版返回 pinned=False。"""
    row = c.execute(
        "SELECT id,pinned_at FROM week_ban_snapshots WHERE week_id=?", (week_id,)
    ).fetchone()
    if row is None:
        return {"pinned": False, "pinned_at": None, "bans": []}
    rows = c.execute(
        """SELECT i.member_id, i.task_id, m.name AS member_name, t.title AS task_title
           FROM week_ban_snapshot_items i
           JOIN members m ON m.id = i.member_id
           JOIN tasks t ON t.id = i.task_id
           WHERE i.snapshot_id=?
           ORDER BY i.task_id, i.member_id""",
        (row["id"],),
    )
    return {
        "pinned": True,
        "pinned_at": row["pinned_at"],
        "bans": [dict(r) for r in rows],
    }
