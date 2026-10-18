# 02 · 三模式与工具权限矩阵

> 依据 ADR-001 / ADR-005 及不变量 INV-08 / INV-09 / INV-10 / INV-17。
> 本文件是"模式能做什么"的唯一权威来源；实现必须与之逐条对齐。

## 一、模式定义

| 模式 | 常量 | 语义 | 进入条件 |
| --- | --- | --- | --- |
| 大纲 | `outline` | 设计/编辑地图，与学习者共创 | 默认（新目标的首次对话） |
| 学习 | `study` | 推进已商定的大纲：讲与考 | **必须已有大纲**（见 `admission_error`） |
| 复习 | `review` | 只重测已掌握的知识点 | 无到期门槛（到期是提醒，非许可） |

- `DEFAULT_MODE = study`（仅用于**展示/框架**时的回退）。
- 模式是**会话上的可变状态**，不是会话属性；可在同一轮内被 `mastery_mode` 切换。

## 二、为什么在"调用期"门控而非"挂载期"

一轮 turn 的**工具 schema 与 system prompt 在首轮之前一次性装配**。因此：
- 所有 mastery 工具**每轮都挂载**；
- 模式专属工具在**执行时**校验模式（`tool_is_allowed`）；
- 被拒绝时，拒绝消息必须**指明 `mastery_mode` 及目标模式**，否则模型会重复同一错误调用。

> 学习者的可见保证不变：静止的 outline 会话无法考人，因为引擎在调用期拒绝。

## 三、权限矩阵

图例：✅ 允许；❌ 拒绝（且不得改变状态）；— 不属于该工具语义。

| 工具 | 归属 | outline | study | review | 说明 |
| --- | --- | :---: | :---: | :---: | --- |
| `mastery_build` | outline | ✅ | ❌ | ❌ | 首次生成大纲 |
| `mastery_revise` | outline | ✅ | ❌ | ❌ | 重塑模块/KP（受 module.objective 契约约束） |
| `mastery_quiz` | study+review | ❌ | ✅ | ✅※ | 出题；注册后**结束本回合** |
| `mastery_grade` | study+review | ❌ | ✅ | ✅※ | 确定性判分 |
| `mastery_assess` | study+review | ❌ | ✅ | ✅※ | 概念/设计定性通过 |
| `mastery_skip_question` | study+review | ❌ | ✅ | ✅ | 跳过当前题 |
| `mastery_repair_question` | study+review | ❌ | ✅ | ✅ | 作废错误评估并重算 |
| `mastery_defer_objective` | study+review | ❌ | ✅ | ✅ | 暂时跳过某 KP |
| `mastery_note_explained` | study+review | ❌ | ✅ | ✅ | 记录"已讲解"（不授予掌握） |
| `mastery_propose_objective` | study+review | ❌ | ✅ | ✅ | **提议候选 KP**（不改地图，ADR-017 / `INV-53/54`） |
| `mastery_note_gap` | study+review | ❌ | ✅ | ✅ | **记缺口**（学习中发现的覆盖缺失，不改地图） |
| `mastery_status` | 共享 | ✅ | ✅ | ✅ | 读状态/刷新快照 |
| `mastery_mode` | 共享 | ✅ | ✅ | ✅ | 切换模式（返回新模式的提示词块） |
| `mastery_profile` | 共享 | ✅ | ✅ | ✅ | 记录学习者画像（intake） |
| `mastery_paths` | 共享 | ✅ | ✅ | ✅ | 列出已有 path |
| `mastery_switch` | 共享 | ✅ | ✅ | ✅ | 切换当前 path |
| `mastery_leave` | 共享 | ✅ | ✅ | ✅ | 离开当前 path |
| `rag` / `read_source` | 共享 | ✅ | ✅ | ✅ | 检索/读来源 |

※ review 下的额外约束见 §五（禁考未掌握）。

## 四、门控规则

### R1 · 调用期校验
```
raw = kwargs["_mastery_session_mode"]        # 原始值，不做归一化
if tool_is_allowed(tool_name, raw): 放行
else: 返回失败，消息 = wrong_mode_message(tool_name, raw)
```
- `tool_is_allowed(tool, mode)`：若 `tool` 不在归属表中 → 视为共享 → `True`。
- `enforced_mode(raw)`：`raw ∈ {outline,study,review}` 才返回它；否则 `None`。
- `enforced_mode == None` → **不门控**（INV-09）。

### R2 · 拒绝消息必须指路
拒绝文案必须包含："`<tool>` 属于 X 模式，当前是 Y；先调用 `mastery_mode(mode='X')`，并告知学习者切换原因。"

### R3 · 进入 study 需已有大纲
```
admission_error(mode, has_outline):
    mode == "study" and not has_outline
        → "还没有可学习的大纲，请先在 outline 模式与学习者设计一个"
    else → ""
```
- 该规则**同时**用于工具与 REST 模式切换端点，保证导师与学习者得到一致答复。
- review **不**按到期门控。

### R4 · 复习只重测已掌握
review 模式下，若目标 KP 未掌握：
- `mastery_quiz` / `mastery_grade` / `mastery_assess` → 拒绝；
- 文案提示：要么换一个已掌握 KP，要么 `mastery_mode(mode='study')` 并说明原因。

### R5 · `mastery_quiz` 结束本回合
- 出题注册成功 → 触发 `end_turn`；其后的任何工具调用都不会执行。
- 题目已存在（单槽位）→ **重放**同一张卡，忽略新参数，并明确告知未产生新题。

### R6 · 捕获-延后不改结构（ADR-017 / `INV-53`）
- `mastery_propose_objective` / `mastery_note_gap` 在 study/review 下**只写候选/备注**（`proposals` / `source_gaps`），**不得**增删改模块/KP。
- 结构改动只能经 outline 的 `mastery_build` / `mastery_revise`；accept 一个 proposal = 在 outline 下调用 `mastery_revise`。

### R7 · 行为预算（ADR-019 / `INV-60`）
- 单回合工具调用数、连续追问次数、同一题提示次数均设上限（默认见 `00` §四 #11，⚠️ 暂定）。
- 超限 → 引擎拒绝并给可操作提示（如"先让学习者作答，再继续"）。

## 五、完整性守卫（ADR-005 / INV-17）

### 归属来源：代码拥有的静态表
```python
SHARED_TOOLS   = {mastery_status, mastery_mode, mastery_profile,
                  mastery_paths, mastery_switch, mastery_leave,
                  rag, read_source}
OUTLINE_ONLY   = {mastery_build, mastery_revise}
STUDY_REVIEW   = {mastery_quiz, mastery_grade, mastery_assess,
                  mastery_skip_question, mastery_repair_question,
                  mastery_defer_objective, mastery_note_explained,
                  mastery_propose_objective, mastery_note_gap}

TOOL_MODES = {t: {OUTLINE}        for t in OUTLINE_ONLY} \
           | {t: {STUDY, REVIEW}  for t in STUDY_REVIEW}
# SHARED_TOOLS 不出现在 TOOL_MODES 中，但必须在 SHARED_TOOLS 显式列名
```

### 守卫测试（必须存在）
- **GUARD-1**：所有 `mastery_*` 工具名 ∈ (`TOOL_MODES.keys()` ∪ `SHARED_TOOLS`)；有遗漏即测试失败。
- **GUARD-2**：`SHARED_TOOLS` 与 `TOOL_MODES.keys()` 不相交。
- **GUARD-3**：新增工具若既不声明归属、也不列入 `SHARED_TOOLS` → 测试失败（fail-closed）。

> 这条守卫是"动态白名单"的安全实现方式：白名单源自代码表本身，而不是外部配置。加模式/加工具时，守卫会**强制**你显式表态。

## 六、模式切换的副作用

- `mastery_mode` 返回**新模式对应的提示词块**（因为本轮 system prompt 仍是切换前装配的）。
- 提示词块读取失败时返回空串：模式已切换，只是文案缺失，工具不再拒绝。
- 切换不重置进度、不改地图、不清 pending question。

## 七、模式切换的审计（ADR-015）

模式切换必须留痕，但要区分**"给 UI 看"**与**"给审计看"**。

### 1. 记什么、记在哪
- **`mode.changed` 是 session 级事件**（`INV-39/47`），**不写入 path 聚合**（否则污染地图事件流）。
- 字段：

| 字段 | 说明 |
| --- | --- |
| `session_id` / `path_id` | 作用域 |
| `from` / `to` | `outline`\|`study`\|`review` |
| **`actor`** | `learner`（点按钮）\| `tutor`（调 `mastery_mode`）——**最关键** |
| `reason` | 导师切换必须说明原因（§四 R2 已要求） |
| `turn_id` / `timestamp` | 与对话时间线对齐 |

### 2. 两族事件同名不同寿命
- **瞬时 `mode_changed`**：推给 UI 立即更新徽章（WS 流事件）。
- **持久 `mode.changed`**：落 session 存储，供恢复（重开会话复现每轮模式）与（可选）审计导出。
- 两族字段保持一致，避免 M2 联调打架。

### 3. 被拒绝的切换
- 即"无大纲切 study 被 `admission_error` 挡下"：**默认不持久**，只作瞬时错误返回（`INV-48`）。
- 仅当进入合规场景（需"尝试记录"）才启用 `mode.change_refused`。

### 4. 合规定位

本项目无强制审计法规；真正的驱动是**恢复/溯源**。仅当出现"监护人/未成年人""对外导出学习过程证据"时，才把 session 事件升级为可导出、可设保留期的审计日志。

### 5. 测试
- **TC-L1**：`mastery_mode` 成功 → session 事件含 `actor=tutor` 及 from/to。
- **TC-L2**：学习者点按钮切换 → `actor=learner`。
- **TC-L3**：无大纲切 study 被拒 → **不产生**持久事件，path 与 session 存储不变。
- **TC-L4**：重开会话 → 能按 `turn_id` 复原每轮所处模式。
