# 06 · 工具契约（build / revise / quiz / grade + 判分 + 缺口）

> 依据 ADR-002/003/004/008/010/011，不变量 `INV-23…28`、`INV-32…36`、`INV-40…46`。
> 这些工具是 **Agent Loop 的 schema**，属回合契约，**M2 前冻结**；且与 REST `PUT map` 共用同一地图 schema。

## 一、共用地图形状（先定这个）

```
Module = { id, name, objective, order, display_target, knowledge_points:[KP] }
KP     = { id, name, type, module_id, prerequisite_ids:[kp_id], source_ids:[source_id], grounding }
```
`build` / `revise` / `PUT map` 三者围绕这一个形状工作（`INV-43`）。

---

## 二、`mastery_build` 契约

**用途**：生成大纲。**空路径 = 创建；非空路径 = 重建**（→ 走 ADR-004）。

**入参**
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `description` | str? | 路线一句话描述 |
| `modules[]` | array | `{ name, objective?, materials?:[文件名], knowledge_points[] }` |
| `knowledge_points[]` | array | `{ name, type, prerequisites?:[名称], sources?:[文件名] }` |
| `confirm` | bool? | 非空路径重建时必填 `true` |

**关键点**：build 时 KP 还没有服务端 id，故**前置用"名称"表达**，服务端解析为 id（因此 build 内 KP 名必须唯一）。

**校验（失败给可操作错误，`INV-40`）**：modules 非空；KP `name≥2`；`type∈enum`；**KP 名唯一**；prerequisite 名可解析；`materials`/`sources` 能映射到 `TopicSource`。

**返回**
```
{ status: "built" | "refused_rebuild",
  path_revision, map:{...}, gaps:[SourceGap], coverage:CoverageReport, next:{...} }
```
- 非空路径且无 `confirm` → `refused_rebuild`，列出**将丢失的内容**，地图不变（`INV-41`）。
- **必须返回 `coverage`**（`INV-56`）：`{documents, covered, missing:[{label,document}], reported, grounding_ratio, acyclic}`；`reported=false` 时不下结论（`09`）。

---

## 三、`mastery_revise` 契约

**用途**：编辑已有大纲（outline 模式），**保进度**。

**入参**：差分操作数组（**以 id 定位**，未触动的 KP 进度得以保留）
| op | 参数 |
| --- | --- |
| `add_module` | name, objective?, after? |
| `update_module` | module_id, name?, objective? |
| `remove_module` | module_id |
| `add_kp` | module_id, name, type, prerequisites?:[kp_id] |
| `update_kp` | kp_id, name?, prerequisites? （**不含 type**） |
| `remove_kp` | kp_id |
| `move_kp` | kp_id, module_id |
| `reorder` | module_id, kp_ids[] |

**返回**
```
{ status:"revised", path_revision, applied:[...],
  dropped_kp_ids:[...], gaps:[...], next:{...} }
```

**两条必区分的语义（否则进度一定丢）**
| | `mastery_build` | `mastery_revise` |
| --- | --- | --- |
| 形状 | **整图替换** | **差量操作** |
| 进度 | **重置**（须 confirm） | **保留**（按 id 匹配） |
| type | 可设 | **已存在 KP 的 type 只读**（ADR-003 / `INV-42`） |
| 事件 | `outline.built` | `outline.revised` |

## 四、缺口处理（ADR-011 / `INV-23…25`）

**先分类再路由**，不是二选一：

| 方向 | 再分 | 应对 |
| --- | --- | --- |
| **目标缺口**（目标要 X，来源没有） | 来源里根本没有 | 接受缺口 或 补来源（重生成**无效**） |
| **来源遗漏**（选了却没用） | 生成漏了 | 重新生成（能捞回来） |

- build/revise 产出结构化 `SourceGap`（见 `01`），**绝不静默**重建或丢弃内容。
- **接受缺口** = 显式状态：KP `source_ids=[]` ⇒ `grounding=ungrounded`，地图显示"待补充来源"角标；补来源后**自动重检消解**（活状态）。
- **未接地 KP 的语义**（`INV-25`，**已确认：方案 A**）：可掌握，但证据标"未接地"、题库不带来源链接。
- "重新生成"本身是一次重建 → 受 ADR-004（显式确认）约束。

---

## 五、`mastery_quiz` 契约

**用途**：为 memory/procedure 类 KP 注册题目 → 出答题卡 → **结束本回合**（`INV-44`）。

**入参**
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `knowledge_point_id` | ✔ | 原样取自 `mastery_status` |
| `question` | ✔ | 题面本身；choice **不要**在题面列选项 |
| `expected_answer` | ✔ | 正确答案，**仅服务端** |
| `question_type` | | `choice\|short\|open`；缺省：有 options→choice，否则 short |
| `options` | | `[{label, body}]`，label 连续 A/B/C…，body 唯一（仅 choice） |
| `explanation` | | **仅服务端**，随作答入题库 |
| `difficulty` | | `easy\|medium\|hard` |
| `accepted_answers` | | 等价答案（翻译/同义），注册时校验 |

**校验**：KP 存在；mode∈{study,review}；review 下 KP 必须已掌握（`INV-10`）；choice label 规范、body 唯一、`expected_answer` 能解析为标签；short/open 不得带 options；**单槽位**：已有 open 题 → 重放旧卡、忽略新参数。

**返回**
```
{ status: "registered" | "already_pending",
  path_revision, knowledge_point_id, question_id,
  pending_question: <公共投影> }        # 不含 expected_answer/explanation（INV-07）
```
- 成功即触发 `end_turn`，其后工具不执行。
- KP 是 concept/design → 附警告："判分不会打开它，需用 `mastery_assess`"。

## 六、`mastery_grade` 契约

**用途**：对当前待答题**确定性判分**。

**入参**
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `question_id` | ✔ | 即 interaction_id，判分幂等键（`INV-21`） |
| `answer` | ✔ | 学习者作答 |
| `hints_used` | | >0 → 降为 `partial`（`INV-36`） |
| `confidence` / `response_time` | | 可选，入题库 |

**行为**：按 `(path_id, question_id)` 定位事务：
1. 已 `graded` → 返回首次存储结果，不重算、不新增证据（`INV-22/45`）；
2. 按类型判分（见 §七）；
3. 解析不了 → 返回 `ungraded` + 澄清提示，**零状态变更**（`INV-33/46`）；
4. 成功 → 写 attempt+evidence+更新掌握+排期，发 `attempt.graded`（门槛清除再发 `objective.mastered`）。

**返回**
```
{ status: "graded" | "ungraded" | "already_graded",
  knowledge_point_id, is_correct,
  result: "correct" | "incorrect" | "partial",
  mastery_before, mastery_after, gate_cleared: bool,
  source?: "system", next:{...}, explanation }
```
- `explanation` **判分后**才对模型可见。
- 两条作答路径（卡片直交 / 自由文本）都归一到同一 `(path_id, question_id)`。

**模式差异**：`study` 判分可推进前沿；`review` 只巩固、不推进，且只考已掌握点。

---

## 七、判分规则（ADR-008）

总原则：**判分时刻不调用 LLM，参照物全部注册时固定**（`INV-32`）。

### choice（精确）
- 期望存**规范标签**，选项 `{label: body}` 且 body 唯一。
- 解析作答 → 标签：① 去空白后是合法标签；② 否则与某 body 唯一匹配；③ 歧义/不匹配 → **不判分**，回问澄清。
- 正确 ⟺ 解析标签 == 期望。**解析不了就"不判"，绝不判错**（`INV-33`）。

### short（模糊，≤30 字）
归一化：`NFKC → casefold → 去首尾空白 → 折叠空白 → 去尾标点；CJK 再去空格`。
按序短路：
| 步骤 | 规则 |
| --- | --- |
| 精确 | 归一化后相等 → correct |
| 等价 | 命中 `accepted_answers` → correct |
| 数字 | 均解析为数且相对误差 ≤1e-6 → correct |
| 模糊 | `1 - 编辑距离/max(len)` ≥ **0.90** → correct |
| 超长回退 | >30 字 → **只做精确匹配**（`INV-34`） |

### open（关键词命中）
- 关键词**注册时固定**（服务端），不得判分时现抽。
- 命中**必需关键词全部** 且 可选命中率 **≥60%** → accepted；命中部分 → `partial`；否则 `incorrect`。
- **open 是三类里最弱的**：**不得单独授予掌握**（最多 `partial`）；记忆/程序类完整掌握靠 choice/short，概念/设计走 `mastery_assess`（`INV-35`）。

### 通用边界
1. **"无法判定 ≠ 错误"**：解析失败返回未判分，不写负证据。
2. **提示降级**：`hints_used>0` → `partial`（`INV-36`）。
3. **等价答案**：`accepted_answers` 必须注册时给定且可信。
4. 判分错误会直接污染 `mastery_levels`（近期加权正确率），故宁可"不判"。

---

## 七之二、捕获工具（ADR-017 · study/review）

**用途**：学习中发现的缺口/新目标**只记录、不改地图**（`INV-53`）。

### `mastery_propose_objective`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `name` | ✔ | 候选目标名（≥2 字） |
| `type` | ✔ | `memory\|procedure\|concept\|design` |
| `reason` | | 为什么需要它 |
| `module_id` / `sources` | | 拟归属模块 / 支撑来源（可空 ⇒ 未接地） |

- 写入 `proposals`（`status=pending`），发 `objective.proposed`；**不影响** `map`/`next_objective`/门槛。
- 返回：`{ proposal_id, status: "pending" }`。

### `mastery_note_gap`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `kind` | ✔ | `goal_gap\|source_omission` |
| `ref` | | kp_id 或 source_id |
| `reason` | | |

- 追加 `SourceGap`，发 `gap.noted`；不改地图结构。

### reconcile（在 outline）
- `POST …/proposals/{id}/resolve {action}`：`accept` → 调用 `mastery_revise` 把候选变 KP；`reject` → 丢弃；发 `objective.proposal_resolved`（`INV-54`）。

---

## 八、测试

**捕获 / 覆盖（`TC-M*`）**
| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-M1 | study 下 `propose_objective` → 写入 `proposals`，`map`/`next_objective` 不变 | INV-53/54 |
| TC-M2 | study 下尝试直接改结构（`mastery_revise`）→ 被拒 | INV-53 |
| TC-M3 | outline 下 accept proposal → 该 KP 出现且可评估 | INV-54 |
| TC-M4 | `build` 返回 `coverage`，`reported=false` 时 `missing` 不展开 | INV-56 |
| TC-M5 | 覆盖比 < 门槛（`00` §四 #10）→ `eval` 报告不达标 | INV-57 |

**缺口（`TC-F2…F5`）**
| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-F2 | "来源里根本没有"的缺口选重新生成 → 缺口仍在（证明 regen 无效） | INV-23 |
| TC-F3 | 来源遗漏触发重新生成 → 该来源被归入某模块（缺口闭合） | INV-23 |
| TC-F4 | 接受缺口 → 地图显示角标、`source_ids` 为空；补来源后角标消失 | INV-24 |
| TC-F5 | 重建路径的缺口处理触发 ADR-004 确认（无确认则不执行） | INV-23/41 |

**build/revise（`TC-J1…J6`）**
| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-J1 | 空路径 build → 模块/KP 数与入参一致，发 `outline.built` | INV-40 |
| TC-J2 | 非空路径 build 无 confirm → `refused_rebuild`，地图与进度不变 | INV-41 |
| TC-J3 | build 两个 KP 同名 → 拒绝 | INV-40 |
| TC-J4 | revise 增删/移动 KP → 未触动 KP 的 `mastery_levels` 不变；发 `outline.revised` | INV-42 |
| TC-J5 | revise 试图改 `type` → 拒绝 | INV-42 |
| TC-J6 | build 的 KP 无来源支撑 → 返回非空 `gaps` | INV-23 |

**quiz/grade（`TC-K1…K6`）**
| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-K1 | choice body 唯一、expected 写标签 → 注册成功；带 options 的 short → 拒绝 | INV-40 |
| TC-K2 | 已有 open 题再次 `quiz` → `already_pending`，无新题 | INV-02 |
| TC-K3 | 重复 `grade` 同 `question_id` → `already_graded`，evidence 数不变 | INV-22/45 |
| TC-K4 | 解析不了 → `ungraded`，`mastery_levels` 不变 | INV-46 |
| TC-K5 | `hints_used>0` → `partial`，`gate_cleared=false` | INV-36 |
| TC-K6 | review 模式对未掌握 KP `quiz` → 拒绝 | INV-10 |

**判分（`TC-H1…H6`）**
| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-H1 | choice 作答写错标签但 body 唯一匹配 → 判对 | INV-33 |
| TC-H2 | choice 作答歧义 → 未判分，`mastery_levels` 不变 | INV-33 |
| TC-H3 | short `2` vs `2.0` → correct；`2` vs `3` → incorrect | INV-34 |
| TC-H4 | short 相似度 0.88<0.90 → incorrect；0.95 → correct | INV-34 |
| TC-H5 | open 命中必需但可选不足 → `partial`，不判掌握 | INV-35 |
| TC-H6 | 有提示答对 → `partial` | INV-36 |
