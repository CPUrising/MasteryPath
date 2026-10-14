# 03 · M1 验收测试清单

> M1 范围：**领域模型（Pydantic）+ SQLite 存储（CAS）+ `mutate`/事件 + 掌握门槛纯函数 + 模式门控纯函数**。
> 不含：LLM 调用、Agent Loop、REST/WS API、前端 UI。
> 判定原则：测试即契约。任何实现只要通过这些用例即为"对"，无需口头确认。

## 一、M1 交付物

| 模块 | 内容 |
| --- | --- |
| `learning/models.py` | 本文 `01` 定义的枚举与实体 |
| `learning/storage.py` | workspace 级 SQLite；`load(path_id)`、`mutate(path_id, fn)`、事件表 |
| `learning/policy.py` | `is_assessed_mastered`、`is_mastered`、`mastery_source`、`objective_status`、`next_objective`、`map_summary`（纯函数，无 I/O） |
| `capabilities/mastery/mode.py` | `MODES`、`TOOL_MODES`、`SHARED_TOOLS`、`tool_is_allowed`、`enforced_mode`、`admission_error`（纯函数） |

## 二、验收测试用例

约定：Given / When / Then。`（INV-xx）` 标注覆盖的不变量。

### A. 模型与校验

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-A1 | Given 一个 `KnowledgePoint`，When `name` 长度 <2 或无 `type`，Then 抛校验错误 | — |
| TC-A2 | Given `type="foo"`，When 构造，Then 拒绝（不静默映射） | INV-16 |
| TC-A3 | Given `type="概念型"`（历史值），When 读取，Then 映射为 `concept` | INV-16 |
| TC-A4 | Given 含未知字段的 JSON，When 反序列化，Then 忽略未知字段且成功 | — |
| TC-A5 | Given `PendingQuestion.options` 为旧式 `["A: x", "B: y"]`，When 读取，Then 解析为 `[{label,body}]` | — |
| TC-A6 | Given 一个 `LearningProgress`，When 序列化再反序列化，Then 全字段相等 | — |

### B. 存储与 CAS

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-B1 | Given 空库，When `load("p1")`，Then 返回 `None` 且**不创建**记录 | — |
| TC-B2 | Given 新建 `p1`，When `load("p1")`，Then 与写入内容相等 | — |
| TC-B3 | Given `p1` version=1，When `mutate` 成功，Then version=2 且 `updated_at` 增大 | INV-11 |
| TC-B4 | Given 会话 S1 读到 version=1，When S2 已提交 version=2 后 S1 用旧 version 提交，Then **失败**且不覆盖 S2 | INV-11 |
| TC-B5 | Given `mutate` 的回调抛异常，When 执行，Then 无任何落库、无事件写入（原子回滚） | INV-11 |
| TC-B6 | Given 两个 workspace，When 同名 path_id 各自写入，Then 互不可见 | — |
| TC-B7 | Given 一次成功 `mutate`，When 查询事件表，Then 新增事件含 `path_id` 与提交后 `revision` | INV-12 |
| TC-B8 | Given 已有事件，When 后续读取，Then 历史事件不变（只追加） | INV-12 |
| TC-B9 | Given 两个**可合并**写并发，When 执行，Then 后者重试后成功，两者修改都在 | INV-11b |
| TC-B10 | Given 非合并安全写（grade 已消失的待答题），When 执行，Then 抛 `PreconditionError`，**不**重试、不落库 | INV-11c |
| TC-B11 | Given 持续冲突达上限（K=3），When 执行，Then 抛 `ConcurrentModificationError` | INV-11b |
| TC-B12 | Given 同 workspace、两线程并发 mutate **不同 path**，Then 两者都成功、互不覆盖、**无 `SQLITE_BUSY` 冒泡** | INV-50 |
| TC-B13 | Given 同 workspace、两线程并发 mutate **同一 path**，Then 一个成功、另一个 CAS 冲突（重试或抛 `ConcurrentModificationError`） | INV-11/50 |
| TC-B14 | Given 写进行中，When 读操作，Then 不被阻塞（WAL 下读到旧快照） | INV-50 |
| TC-B15 | Given `mutate` 内抛异常，Then 状态与事件**都**不落（同事务） | INV-51 |
| TC-B16 | Given 一个 turn 顺序 mutate 两个 path（模拟 `mastery_switch`），Then 均可提交；（lease 属 M2，可登记） | — |
| TC-B17 | Given 跨 workspace 两线程并发写，Then 各自 DB 均成功、互不可见且互不阻塞 | INV-52 |

### C. 掌握门槛 / 策略（纯函数）

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-C1 | Given memory KP，`mastery_levels=0.85`，When 判定，Then **未**掌握 | INV-04 |
| TC-C2 | Given memory KP，`mastery_levels=0.90`，When 判定，Then 掌握 | INV-04 |
| TC-C3 | Given procedure KP，`mastery_levels=1.0`，Then 掌握 | INV-04 |
| TC-C4 | Given concept KP，`mastery_levels=1.0` 但无定性通过，Then **未**掌握 | INV-05 |
| TC-C5 | Given concept KP，`qualitative_mastery=True`，Then 掌握 | INV-05 |
| TC-C6 | Given 存在 override，When 判定，Then `is_mastered=True` 且 `mastery_source="learner"` | INV-03 |
| TC-C7 | Given 存在 override 且 `mastery_levels` 原为某值，When 走完声明流程，Then `mastery_levels` **未被写入/改变** | INV-01 |
| TC-C8 | Given override，When 检查 `learning_evidence`，Then 无新增证据 | INV-15 |
| TC-C9 | Given 模块/KP 顺序固定，部分已掌握，When `next_objective`，Then 返回第一个未掌握 KP | INV-03 |
| TC-C10 | Given 全部 KP 已掌握/已 defer，When `next_objective`，Then `action="complete"` | INV-03 |
| TC-C11 | Given 存在 `pending_question`，When `next_objective`，Then `action="answer_pending"` | INV-02 |
| TC-C12 | Given 一个 `voided=True` 的 attempt，When 计算 `mastery_levels` 与 evidence，Then 均不计入 | INV-14 |
| TC-C13 | Given 某 KP 有 attempt，When `objective_status`，Then 分别返回 new/learning/mastered（三分支各一例） | — |
| TC-C14 | Given 某 KP 已掌握，When `map_summary`，Then 其状态与来源与 gate 一致 | INV-03 |
| TC-C15 | Given `deferred` 的 KP，When `next_objective`，Then 被跳过且不计为掌握 | — |
| TC-C16 | Given 已存在 KP，When 请求修改其 `type`，Then 服务层拒绝 | INV-06 |
| TC-C17 | Given 非空 `goal`，When 执行一次 build/revise（模拟），Then `goal` 保持不变 | INV-13 |
| TC-F1 | Given 模块聚合分 < `display_target` 但所有 KP 已掌握，Then `next_objective` 仍返回 `complete`（反证它不是门槛） | INV-18 |
| TC-F6 | Given design KP 的前置 procedure 未掌握，Then `next_objective` 返回该 procedure，**不**返回 design | INV-27 |
| TC-F7 | Given 前置 procedure 通过但 design 未定性通过，Then design 仍未掌握 | INV-27/05 |
| TC-F8 | Given 前置全掌握且 design 定性通过，Then design 掌握（两条件相与） | INV-27/05 |
| TC-F9 | Given 生成器输出一个同时含"实现步骤 + 设计取舍"的 KP，Then 被拆成两个 KP（**M2：由 build 校验实现**） | INV-26 |

### D. 模式门控（纯函数）

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-D1 | Given mode=`outline`，When `tool_is_allowed("mastery_quiz")`，Then `False` | INV-08 |
| TC-D2 | Given mode=`study`，When `tool_is_allowed("mastery_build")`，Then `False` | INV-08 |
| TC-D3 | Given mode=`study`，When `tool_is_allowed("mastery_status")`，Then `True` | — |
| TC-D4 | Given mode 缺失/`None`，When 任意调用，Then 全部 `True`（不门控） | INV-09 |
| TC-D5 | Given mode=`outline`，When `admission_error(mode, has_outline=False)`，Then 返回非空提示 | R3 |
| TC-D6 | Given mode=`study` 且 `has_outline=True`，When `admission_error`，Then `""` | R3 |
| TC-D7 | Given mode=`review` 且目标 KP 未掌握，When 校验，Then 拒绝 | INV-10 |
| TC-D8 | Given mode=`review` 且目标 KP 已掌握，When 校验，Then 放行 | INV-10 |
| TC-D9 | Given `TOOL_MODES` 与 `SHARED_TOOLS`，When 运行完整性守卫，Then 所有 `mastery_*` 工具被显式归类、两集不相交 | INV-17 |

### E. 交互映射（若 M1 已含 interaction 生命周期）

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-E1 | Given 已有 open interaction（`awaiting_input`），When 注册新题，Then 被拒绝（单槽位） | INV-02 |
| TC-E2 | Given 现有题进入 `graded`，When 注册新题，Then 成功 | INV-02 |
| TC-E3 | Given 同一 `interaction_id` 重复提交判分，When 执行，Then 幂等（不重复记账）（**M2：判分实现后**） | — |
| TC-E4 | Given `answer_pending` 的公共 status 投影，When 序列化，Then **不含** `expected_answer`/`explanation` | INV-07 |

## 三、不变量 → 测试追踪表

| 不变量 | 覆盖用例 |
| --- | --- |
| INV-01 | TC-C7 |
| INV-02 | TC-C11, TC-E1, TC-E2 |
| INV-03 | TC-C6, TC-C9, TC-C10, TC-C14 |
| INV-04 | TC-C1, TC-C2, TC-C3 |
| INV-05 | TC-C4, TC-C5 |
| INV-06 | TC-C16 |
| INV-07 | TC-E4 |
| INV-08 | TC-D1, TC-D2 |
| INV-09 | TC-D4 |
| INV-10 | TC-D7, TC-D8 |
| INV-11 | TC-B3, TC-B4, TC-B5, TC-B9, TC-B10, TC-B11 |
| INV-12 | TC-B7, TC-B8 |
| INV-18 | TC-F1 |
| INV-26 | TC-A2（单值 schema）；拆分逻辑 M2，见 `06` |
| INV-27 | TC-F6, TC-F7, TC-F8 |
| INV-50 | TC-B12, TC-B13, TC-B14 |
| INV-51 | TC-B15 |
| INV-52 | TC-B17 |
| INV-13 | TC-C17 |
| INV-14 | TC-C12 |
| INV-15 | TC-C8 |
| INV-16 | TC-A2, TC-A3 |
| INV-17 | TC-D9 |

## 四、M1 完成定义（DoD）

- [ ] §二 A–E 全部用例通过（E 组允许标为 M1.5，但需在文档登记）。
- [ ] 追踪表中每条 `INV-xx` 至少被一个通过的用例覆盖。
- [ ] 存储并发用例（TC-B4）用真实多线程/多连接模拟,不得用 mock 绕过。
- [ ] 纯函数层（policy / mode）无任何 I/O 或 LLM 调用，可离线运行。
- [ ] 未引入未经 ADR 批准的新实体/依赖。

## 五、待补（已移入专门文档）

以下原本列此的待补项，已分别落到专门文档：

| 待补项 | 现位置 |
| --- | --- |
| `mastery_build/revise` 契约 + 缺口处理（`TC-F2…F5`、`TC-J*`） | `06-tools-contract.md` |
| `mastery_quiz/grade` 契约 + 判分规则（`TC-H*`、`TC-K*`） | `06-tools-contract.md` |
| 间隔复习调度（`TC-G*`）与播种参数 | `04-scheduling.md` |
| REST/WS 端点与事件清单（`TC-I*`） | `05-api-contract.md` |
| 模式切换审计（`TC-L*`） | `02-mode-tool-matrix.md` §七 |
