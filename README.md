# MasteryPath

以知识地图为中心的掌握式学习智能体。本仓库当前处于 **M1**：
领域模型 + SQLite(CAS) 存储 + 掌握门槛策略 + 模式门控，全部为**无 LLM 的纯逻辑**。

## 规格

`docs/` 是契约层规格包（先读 `docs/README.md`）：
ADR 定决策、INV 定约束、TC 定对错。实现只以规格为准。

## 布局

```
docs/                        规格包（README + 00–07）
masterypath/
  learning/                  models / policy / storage / pending
  capabilities/mastery/      mode（工具权限 + 守卫）
tests/                       验收测试（对应 docs 的 TC-*）
pyproject.toml
```

## 运行测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

## M1 覆盖

| 组 | 内容 | 状态 |
| --- | --- | --- |
| A | 模型/校验（`TC-A1..A6`） | ✅ |
| B | 存储/CAS/事件/并发（`TC-B1..B17`） | ✅ |
| C | 门槛/导航（`TC-C1..C17`） | ✅ |
| D | 模式门控 + 守卫（`TC-D1..D9`） | ✅ |
| E | 交互单槽位 + 公共投影（`TC-E1/E2/E4`） | ✅ |
| F | 阈值非门槛 / 前置硬门控（`TC-F1/F6..F8`） | ✅ |

未纳入 M1（已在 `docs/03` 标注）：`TC-E3`（判分幂等，待 M2 判分）、`TC-F9`（生成器拆分，M2 build 校验）。

## M2 覆盖（outline：首次接入 Loop）

| 组 | 内容 | 状态 |
| --- | --- | --- |
| J | `mastery_build/revise` 契约（`TC-J1..J6`） | ✅ |
| F | 缺口处理（`TC-F2..F5`） | ✅ |
| I | REST/WS 契约（`TC-I1/I2/I4`） | ✅ |
| — | Agent Loop + 模式调用期门控（`test_loop`） | ✅ |

- 供应商为 `DeepSeekClient` **占位适配器**（`NotImplementedError`）；测试全程用 `FakeLLMClient`，离线运行（ADR-014）。
- `TC-I3`（`question_card` 投影）由 `test_tc_e4` 覆盖（公共投影不含答案）。

## M3 覆盖（study：出题 + 确定性判分 + 量化门槛）

| 组 | 内容 | 状态 |
| --- | --- | --- |
| H | 判分规则（choice/short/open）`TC-H1..H5` | ✅ |
| K | `mastery_quiz/grade` 契约 `TC-K1..K6` | ✅ |
| E | 判分幂等 `TC-E3`（`already_graded`，不重复记证据） | ✅ |
| — | 量化门槛：答对→`mastery_levels`≥0.9→`objective.mastered`→前沿推进 | ✅ |

- 新增 `learning/grading.py`（确定性判分，无 LLM）、`learning/mastery.py`（近期加权掌握度）、`learning/question_card.py`（卡片，无答案）。
- `mastery_quiz` 出题即**结束回合**（`end_turn`，`INV-44`）；`ungraded` **零状态变更**（`INV-46`）。
- 未纳入 M3：`mastery_assess`（concept/design 定性，M4）；`review` 排期（M5）。

## M4 覆盖（concept/design 定性评估）

| 内容 | 状态 |
| --- | --- |
| `mastery_assess` 定性通过/不通过（费曼式，写 `qualitative_mastery`） | ✅ |
| 仅限 concept/design：对 memory/procedure 调 `assess` → 拒绝 | ✅ |
| review 模式禁评未掌握目标 | ✅ |
| 证据 `assessment_type=qualitative`；多次评估证据累积；通过→门槛清除→前瞻推进 | ✅ |

- `mastery_assess` 是 concept/design 的开门方式；选择题判分**不会**打开它们（`INV-05`）。

## M5 覆盖（review + 简化间隔复习 SM-2）

| 内容 | 状态 |
| --- | --- |
| SM-2 间隔序列 1/6/15/38/95、EF 更新与下限 `TC-G1` | ✅ |
| failure 进入重学步、`lapse_count+1`、`scheduled_after_failure=True` `TC-G2` | ✅ |
| 失败后下次成功清除标志、走正常序列 `TC-G3` | ✅ |
| 会话内练习只改 `last_review_at`、不动锚点 `TC-G4` | ✅ |
| 声明轨首间隔约为系统轨 0.5（∈[0.3,0.7]）`TC-G5` | ✅ |
| 掌握→播种 `RepetitionState`+`review_queue`；到期→`next_objective` 返回 review；review 判分重排 | ✅ |

- 新增 `learning/scheduler.py`（纯 SM-2）；`service` 在掌握时播种、review 判分重排、会话内练习只 touch。
- 单调度器、按 provenance 播种（ADR-002）；算法 SM-2，FSRS 字段仅展示（`INV-31`）。
- 未纳入 M5：`scenario` 场景预设（二期）；跨会话「同一天多练不清零」的会话判定属后续细化。

## M6 覆盖（题库同步 + 标签）

| 内容 | 状态 |
| --- | --- |
| 判分/定性评估自动入库（题面、选项、正确答案、解析、难度、作答、结果） | ✅ |
| **知识点自动关联**（`knowledge_point_id` + 名称） | ✅ |
| 标签手动（`tag_question`，去重）；按标签筛选 | ✅ |
| REST：`GET /learning/paths/{id}/questions`、`POST /learning/questions/{id}/tags` | ✅ |

- 新增 `QuestionBankEntry` + `question_bank` 表；入库在判分同一事务内完成（与证据一致）。
- 标签为 MVP 手动；知识点关联**自动**（便于复习按点筛选）。

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

启动 API（需自行接入真实 LLM 客户端）：

```powershell
.\.venv\Scripts\python.exe -c "import uvicorn; from masterypath.api.app import create_app; from masterypath.learning.storage import LearningStore; uvicorn.run(create_app(LearningStore('data')), host='127.0.0.1', port=8001)"
```
