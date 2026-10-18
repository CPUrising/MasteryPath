# 08 · 导师行为契约（ADR-019）

> 目的：把"导师该做什么、不该做什么"从**提示词里的期望**升级为**引擎里的约束**（`INV-59`）。
> 原则：**能进引擎的都进引擎**；提示词只负责表达与引导，不负责保证。

## 一、三条铁律

1. **引擎判放行**：是否推进由掌握门槛决定，不由模型决定（ADR-001/007）。
2. **越界即拒绝**：意图/前置/预算在**调用期**校验，拒绝时**指明补救动作**（`INV-59`）。
3. **来源纪律**：不得为未接地（`ungrounded`）KP 声称"有资料支撑"（`INV-58`）。

## 二、按模式的意图白/黑名单

| 模式 | 允许意图（白） | 禁止意图（黑） |
| --- | --- | --- |
| **outline** | 生成/重塑地图、读来源、问 intake、reconcile 候选 | **考人**（quiz/grade/assess） |
| **study** | 讲、出题、判分、定性评估、记讲解、defer、**捕获**（propose/note_gap） | **改结构**（build/revise） |
| **review** | 只考**已掌握**、判分、定性重评、捕获 | 教新内容、考未掌握、改结构 |

> 拒绝文案必须含"切到哪个模式"（见 `02` §四 R2）。

## 三、动作前置条件（preconditions）

| 动作 | 前置 |
| --- | --- |
| `mastery_quiz` | 目标 KP 存在；study/review；review 下 KP **已掌握**（`INV-10`） |
| `mastery_grade` | 存在对应 open interaction；解析不了 → `ungraded` 零变更（`INV-46`） |
| `mastery_assess` | KP 类型 ∈ {concept, design}（否则拒绝） |
| `mastery_revise` | outline；已存在 KP 的 `type` 只读（`INV-42`） |
| `mastery_build`（非空路径） | `confirm=true`（ADR-004） |
| `mastery_propose_objective` / `mastery_note_gap` | study/review；只写候选/备注（`INV-53`） |
| 任何评估 | 前置 KP 全掌握（`INV-27`） |

## 四、行为预算（`INV-60`）

| 预算 | 默认 | 超限行为 |
| --- | --- | --- |
| 单回合工具调用数 | `6` | 拒绝继续调用，返回 `turn_end` |
| 连续追问（未获作答） | `3` | 提示"先让学习者作答，再继续" |
| 同一题提示次数 | `2` | 超过则降级为 `partial` 并建议换题（配合 `INV-36`） |

> 数值见 `00` §四 #11（⚠️ 暂定，待产品方签字）。

## 五、提示策略（hint policy）

- 允许给提示；**给了提示** → 该次结果降为 `partial`，掌握权重下调（`INV-36`），不计独立证据。
- 提示不得包含 `expected_answer` 原文（`INV-07`）。
- 同一题连续提示超预算 → 建议 `mastery_skip_question` 或 `mastery_defer_objective`。

## 六、离题与修复

- **离题**：先简短回应，再拉回当前路标；不因离题推进门槛。
- **错误评估修复**：`mastery_repair_question` 作废错误评估并**重算**掌握/错误/复习影响（`INV` 层面：作废不计，`INV-14`）；修复不因质疑而授予掌握。
- **无效题目**：注册失败给可操作错误（`06` §五），不产生卡片。

## 七、来源纪律（`INV-58`）

- 只有 `grounding=grounded` 的 KP 才能在讲解/题目中声明"来自你的资料"。
- `ungrounded` KP：可教、可考（方案 A，`INV-25`），但**不得**声称来源支撑，题库条目不带来源链接。

## 八、确定性守卫与测试

| 行为 | 引擎守卫 | 测试 |
| --- | --- | --- |
| 模式越界 | `tool_is_allowed` + `wrong_mode_message` | TC-D1/D2、TC-M2 |
| review 禁考未掌握 | `_review_scope_refusal` | TC-K6 |
| 前置未掌握不可评估 | `eligible`（`INV-27`） | TC-F6 |
| 捕获不改结构 | 结构改动仅 outline 工具 | TC-M1/M2 |
| 提示降级 | `hints_used>0 → partial` | TC-K5/H6 |
| 来源纪律 | `grounding` 参与投影与题库 | TC-E4、`INV-58` |
| 预算 | 调用计数守卫 | TC-M6（待补） |

> **TC-M6**：单回合工具调用超过预算 → 引擎拒绝后续调用并结束回合。
