# Chorerota · 家庭值日轮转

底座：成员+任务 → round-robin 生成周表 → 申请对调 → 确认改表。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5100 |
| API | 10100 |

```bash
docker compose up --build
pytest backend/app/tests
```

种子含 clean/dirty。0-1 空桩：`streak_badge` / `skip_week` / `chore_photo`。

## 禁配矩阵（人任禁配）

「任务」「成员」两页均可维护禁配行：某人不得做某任务。

- 生成周表时禁配对不出现：命中禁配在该槽位内顺移下一位活跃 clean 成员，相位不被顺移消耗；无禁配时输出与改造前同参逐格一致。
- 取舍拍板：某 (day, task) 全员禁配时**跳过该格并落 `assignment_gaps` 缺口**（不整次失败）；生成回包与看板读同一份落库数据，二者一致。
- 非法禁配拒写且矩阵不增行：重复（`duplicate_exclusion`）、成员/任务不存在（`member_not_found`/`task_not_found`）、成员停用或 dirty（`member_not_assignable`）。
- 生成时把现行矩阵整体钉入 `week_exclusions` 当周快照：看板格位、禁配列表、`GET /api/weeks/{id}/exclusions` 三路同源；只改现行矩阵不重切旧周格位。
- 生成后新增禁配不改旧周，但确认对调若会形成禁配对 → `exclusion_conflict`，格表不动（申请与确认两道门禁都用现行矩阵）。

| 接口 | 说明 |
| --- | --- |
| `GET/POST/DELETE /api/exclusions` | 现行矩阵查/增/删 |
| `GET /api/weeks/{id}/exclusions` | 当周生成时钉下的禁配快照 |
| `POST /api/weeks/{id}/generate` | 回包含 `slots`/`gaps`/`exclusions`（钉入快照） |

模块边界：矩阵仓储 `app/modules/exclusions/`、指派规避与对调门禁 `app/engines/rota.py`、生成落库 `app/services/generation.py`。
