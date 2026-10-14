# 05 · API 契约（REST / WS / 事件 / 运行时边界）

> 依据 `INV-07/08/37/38/39` 与 ADR-014。必须在 **M2 接 Agent Loop 前**冻结：Loop 的输入/输出即 WS 回合契约；前端唯一依赖即 REST。

## 一、两个通道的分工

| 通道 | 职责 | 原则 |
| --- | --- | --- |
| **WS** | **对话回合**：流式文本、工具调用、卡片、结束 | 只有"一轮导师对话"走这里 |
| **REST** | 其余一切：地图读写、模式、状态、复习队列、画像、会话列表 | 非回合操作，可幂等、可重放 |

## 二、REST 端点清单（MVP 裁剪）

**路径 / 主题**
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/paths` | 列表 + 概览（目标数/已掌握/到期数） |
| POST | `/learning/paths` | 创建目标（名称 + goal + sources） |
| GET | `/learning/paths/{path_id}` | 完整状态快照（map / next / pending / review due / profile） |
| PATCH | `/learning/paths/{path_id}` | 改名 / 改 goal / 归档 |
| DELETE | `/learning/paths/{path_id}` | 删除 |

**地图（仅 outline 模式可写）**
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| PUT | `/learning/paths/{path_id}/map` | 整图替换（编辑）；schema 见 `06` §一 |
| POST | `/learning/paths/{path_id}/rebuild` | **重建**，须 `confirm=true`（ADR-004） |
| POST | `/learning/paths/{path_id}/objectives/{kp_id}/override` | 声明掌握（learner 轨） |
| POST | `/learning/paths/{path_id}/gaps/{gap_id}/resolve` | 缺口：`accept` / `regenerate` |

**会话与模式**
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/paths/{path_id}/sessions` | 该主题下会话（侧栏归档） |
| POST | `/learning/sessions` | 新建会话并绑定 path |
| PUT | `/learning/paths/{path_id}/sessions/{session_id}/mode` | 切模式（校验 `admission_error`，记 `mode.changed`） |
| GET | `/learning/sessions/{session_id}` | 会话历史 |

**复习 / 进度 / 画像**
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/paths/{path_id}/review-queue` | 到期复习（按遗忘风险排序） |
| GET | `/learning/paths/{path_id}/mastery` | `map_summary` |
| GET | `/learning/paths/{path_id}/questions` | 题目/证据（题库视图） |
| GET/PUT | `/learning/paths/{path_id}/profile` | 学习者画像（intake） |
| GET | `/learning/paths/{path_id}/events?since={rev}` | 恢复用事件流 |

## 三、WS 回合契约

```
WS /ws
请求:  { session_id, path_id, mastery_path_id, mode:"outline|study|review",
        capability:"mastery_path", message, turn_id }
事件:  text_delta / tool_call / tool_result / question_card /
       mode_changed / usage / turn_end / error
```
- **"答卡片"没有单独端点**——作答就是下一条 turn message（见 `06` §五）。
- 幂等/恢复靠 `turn_id` + 事件序号；丢线重连用 REST `events?since=` 补齐。
- `question_card` 只带公共投影，**不含** `expected_answer`（`INV-07`）。

## 四、领域事件（durable，供恢复/审计）

设计原则：命名 `实体.过去式动作`；**只在提交成功时发出**（`INV-37`）；带 `revision` 且单调（`INV-38`）；消费方以 `(path_id, revision)` 去重；**聚合仍是唯一真相**，不做完整事件溯源。

| event_type | 触发 | payload 关键字段 | 消费者 |
| --- | --- | --- | --- |
| `path.created` | 创建目标 | goal, sources | 侧栏 |
| `path.renamed` / `path.goal_changed` | 改名/改目标 | name / goal | 侧栏 |
| `path.archived` | 归档 | — | 侧栏 |
| `path.rebuilt` | 显式重建 | confirmed, dropped | 地图 |
| `outline.built` | `mastery_build` | module_count | 地图 |
| `outline.revised` | `mastery_revise` | added/removed/changed ids | 地图 |
| `gap.detected` | 生成遇缺口 | gap_id, kind, ref | 地图角标 |
| `gap.resolved` | 缺口处理 | gap_id, action | 地图角标 |
| `objective.explained` | `mastery_note_explained` | kp_id, summary | 进度 |
| `question.registered` | `mastery_quiz` | question_id, kp_id, type | 卡片 |
| `question.skipped` | `mastery_skip_question` | question_id, kp_id | 卡片 |
| `question.repaired` | `mastery_repair_question` | question_id, reason | 进度重算 |
| `attempt.graded` | `mastery_grade` | kp_id, is_correct, result, hints_used, mastery_after | 进度/题库 |
| `qualitative.assessed` | `mastery_assess` | kp_id, passed, quality | 进度 |
| `objective.mastered` | 门槛清除（里程碑） | kp_id, source(system\|learner) | 进度环 |
| `objective.deferred` / `undeferred` | defer | kp_id | 地图 |
| `mastery.override` | 声明掌握 | kp_id, note | 进度（**不产 evidence**，`INV-15`） |
| `review.scheduled` | 排期/重排 | kp_id, next_review_at, interval_index, provenance | 复习队列 |
| `mode.changed` | 模式切换（**session 级**） | from, to, **actor** | 徽章/恢复/审计 |

> 地图编辑**整组发一条 `outline.revised`**，不要每 KP 一条（事件爆炸）。

## 五、WS 流事件（瞬时）

`text_delta` · `tool_call` · `tool_result` · `question_card` · `mode_changed` · `usage` · `turn_end` · `error`

`mode_changed`（瞬时）与领域 `mode.changed`（持久）**同名不同寿命**，字段保持一致。

## 六、错误码

| 码 | 场景 | 关联 |
| --- | --- | --- |
| `409 mode_conflict` | 非 outline 模式写地图 | `INV-08` |
| `409 cas_conflict` | CAS 重试耗尽 | `INV-11b` |
| `412 precondition` | 前置条件失败（如 grade 已消失的题） | `INV-11c` |
| `422 invalid_map` | build/revise 入参校验失败 | `INV-40` |
| `409 rebuild_requires_confirm` | 非空路径重建无 confirm | `INV-41` |

## 七、三条设计约束

1. **模式门控在 REST 侧也生效**：`PUT map`、`rebuild` 必须校验当前会话 `mode==outline`，否则 `409`（`INV-08` 的 REST 半边）。
2. **重建 ≠ 编辑**：`PUT map` 是编辑，`POST rebuild` 是重建，后者必须 `confirm=true`，不合并。
3. **无 LLM 的端点不得依赖 LLM**：列表、状态、复习队列、事件均为纯读，M1 存储/策略层即可支撑。

## 八、运行时边界（ADR-014，供应商）

- **领域层（`learning/*`）零耦合供应商**；Loop 层经 `LLMClient`（chat/tool-call/stream）+ `TaskModelClient` 适配器隔离。
- 提供 **fake/echo 客户端**，令 M1/M2 测试离线可跑。
- **M2 前必须定**：主导师模型、**工具调用机制**（原生 function calling vs 文本解析）、流式契约、Task Model、失败/超时回退。
- 供应商差异（工具调用格式、流式协议、上下文窗口）由适配器吸收，不泄漏进领域层。

## 九、测试

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-I1 | 非 outline 模式 `PUT map` → `409`，地图不变 | INV-08 |
| TC-I2 | `rebuild` 无 `confirm` → 拒绝 | INV-41 |
| TC-I3 | `question_card` 投影不含 `expected_answer` | INV-07 |
| TC-I4 | WS 断线后 `events?since` 能补齐缺失事件 | INV-38 |
| TC-I5 | 一次失败 mutate → 无事件；随后成功 → 事件 `revision` 连续 | INV-37/38 |
| TC-I6 | `events?since=rev0` 能重建 rev1 的状态差异（字段级） | INV-38 |
| TC-I7 | `mastery.override` 事件存在，但 `learning_evidence` 无新增 | INV-15 |
