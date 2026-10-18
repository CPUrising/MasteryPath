# MasteryPath 使用手册

以知识地图为中心的掌握式学习智能体。本文是**使用说明**；设计与约束见 `docs/`（规格包）。

---

## 1. 快速开始

```powershell
# 1) 环境
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2) 跑测试
.\.venv\Scripts\python.exe -m pytest -q
```

要求：Python ≥ 3.11（当前验证 3.14）。核心依赖仅 `pydantic`；API 需 `fastapi/uvicorn`；测试需 `pytest`（含 `httpx`）。

---

## 2. 启动后端 API

```powershell
.\.venv\Scripts\python.exe -c "import uvicorn; from masterypath.api.app import create_app; from masterypath.learning.storage import LearningStore; uvicorn.run(create_app(LearningStore('data')), host='127.0.0.1', port=8001)"
```

- 默认端口 **8001**；数据落在 `data/learning.db`（workspace 级 SQLite）。
- 真实模型：需自行实现 `masterypath/agents/llm.py::DeepSeekClient`（原生 function calling + 流式）。**当前它是占位适配器**，未接入时任何对话回合会抛 `NotImplementedError`。测试全部用 `FakeLLMClient`，离线运行。

---

## 3. 核心概念速查

| 概念 | 说明 |
| --- | --- |
| **大纲（地图）** | 唯一真相源：模块 → 知识点（KP）。只有 `outline` 模式能改地图 |
| **三种模式** | `outline` 改地图 / `study` 讲与考 / `review` 只考已掌握 |
| **知识点类型** | `memory` `procedure` `concept` `design`；**类型决定"什么叫掌握"** |
| **掌握门槛** | memory/procedure：量化 `mastery_levels ≥ 0.9`；concept/design：定性通过（费曼式） |
| **双轨** | 系统评估通过（来源 `system`，写分数）／学习者声明（来源 `learner`，**不写分数**） |
| **间隔复习** | SM-2；掌握后播种 `RepetitionState`，到期重现 |
| **缺口** | 目标缺口（来源没有）／来源遗漏（选了没用）；未接地 KP 标 `ungrounded` |
| **前置** | `prerequisite_ids` 为**硬门控**：前置未掌握则不可评估 |

---

## 4. Python 用法

### 4.1 基本对象

```python
from masterypath.learning.storage import LearningStore
from masterypath.learning.service import LearningService

store = LearningStore("data")          # 一个 workspace 一个库
service = LearningService(store)       # 所有写经 store.mutate（CAS + 事件）
```

### 4.2 建目标 → 接资料 → 生成大纲

```python
from masterypath.knowledge.loader import scan_folder

service.create_path("p", goal="三个月掌握 Rust 并发", name="Rust 并发")
service.attach_sources("p", scan_folder(r"D:\我的资料"))   # 可选：文件夹知识库

result = service.build("p", {"modules": [
    {"name": "并发基础", "objective": "能解释线程与进程的取舍",
     "materials": ["并发入门.md"],
     "knowledge_points": [
        {"name": "理解线程与进程", "type": "concept", "sources": ["并发入门.md"]},
        {"name": "复现通道收发", "type": "procedure"},
     ]},
]})
print(result.status, [g.kind.value for g in result.gaps])
```

- 空路径 → 创建；**非空路径** → 需 `confirm=True`（重建会重置进度，ADR-004）。
- `materials`/`sources` 引用**来源 label**（相对路径）或**唯一文件名**。
- 编辑已有大纲：`service.revise("p", [{"op": "add_kp", "module_id": "m1", "name": "新目标", "type": "memory"}])`（按 id 差分、**保进度**）。

### 4.3 出题 → 判分（study）

```python
from masterypath.learning.models import PendingQuestion

service.register_question("p", PendingQuestion(
    question_id="q1", knowledge_point_id="k2", question_type="short",
    prompt="通道满时 send 会怎样？", expected_answer="阻塞",
))
service.grade("p", "q1", "阻塞")     # 确定性判分；重复调用幂等（already_graded）
```

### 4.4 定性评估（concept/design）

```python
service.assess("p", "k1", passed=True, evidence="用自己的话解释了线程/进程的取舍")
```

### 4.5 声明掌握 / 复习 / 题库 / 建议

```python
service.override_mastery("p", "k1", note="我已掌握")      # learner 轨，不写分数
state = service.get_state("p")                            # 地图/路标/到期/缺口/来源
service.list_questions("p", tag="exam")                   # 题库（按标签筛）
service.tag_question(entry_id, ["exam", "hard"])          # 手动标签
```

### 4.6 走 Agent Loop（用假模型离线跑）

```python
from masterypath.agents.llm import FakeLLMClient, LLMResponse, ToolCall
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.capabilities.mastery import mode

client = FakeLLMClient([
    LLMResponse(tool_calls=[ToolCall("mastery_build", {"modules": [...]})]),
    LLMResponse(text="大纲已生成。"),
])
ctx = ToolContext(service=service, path_id="p", session_mode=mode.OUTLINE)
events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "带我学 X"}], ctx)
```

---

## 5. REST 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/paths` | 路径列表 + 概览 |
| POST | `/learning/paths` | 创建目标 `{path_id, goal, name}` |
| GET | `/learning/paths/{id}` | 完整状态（map/next/sources/gaps/pending/due） |
| DELETE | `/learning/paths/{id}` | 删除 |
| PUT | `/learning/paths/{id}/map?session_id=` | 改地图（`{modules}` 或 `{ops}`）；**须 outline 模式** |
| POST | `/learning/paths/{id}/rebuild?session_id=` | 重建，`{confirm:true}` |
| POST | `/learning/paths/{id}/objectives/{kp}/override` | 声明掌握 `{note}` |
| POST | `/learning/paths/{id}/gaps/{gap}/resolve` | `{action:"accept"|"regenerate"}` |
| GET | `/learning/paths/{id}/mastery` | 地图摘要 |
| POST | `/learning/paths/{id}/sources` | 接文件夹 `{folder}` |
| GET | `/learning/paths/{id}/sources` | 已接来源 |
| GET | `/learning/paths/{id}/review-queue` | 到期复习 |
| GET | `/learning/paths/{id}/events?since=` | 事件流（恢复用） |
| GET | `/learning/paths/{id}/suggest-question` | 建议下一问（草稿） |
| GET | `/learning/paths/{id}/questions?tag=` | 题库 |
| POST | `/learning/questions/{entry_id}/tags` | 打标签 `{tags:[...]}` |
| PUT | `/learning/paths/{id}/sessions/{sid}/mode` | 切模式 `{mode, actor}` |
| PATCH | `/learning/paths/{id}` | 改名 `{name}` |
| POST | `/learning/paths/{id}/redo` | 重置进度（保留地图） |
| PUT | `/learning/paths/{id}/review-settings` | 复习目标 `{desired_retention}` |
| GET | `/learning/paths/{id}/sessions` | 会话列表 |
| GET | `/learning/sessions/{sid}` | 会话详情（含消息） |
| POST | `/learning/paths/{id}/quiz` | 出题（无需 LLM） |
| POST | `/learning/paths/{id}/grade` | 判分（无需 LLM） |
| POST | `/learning/paths/{id}/assess` | 定性评估 |
| POST | `/learning/paths/{id}/skip-question` | 跳过当前题 |
| GET/PUT | `/settings/{section}` | 配置：`providers`/`llm`/`task-models`/`embedding`/`general` |

错误码：`409 mode_conflict` / `409 rebuild_requires_confirm` / `409 cas_conflict` / `412 precondition` / `422 invalid_map`。

---

## 6. WS 回合协议

```
WS /ws
请求: { session_id, path_id, mode:"outline|study|review", capability, message, turn_id }
事件: text_delta / tool_call / tool_result / question_card / mode_changed / usage / turn_end / error
```

- **答卡片没有单独端点**：作答就是下一条 turn 的 `message`。
- `tool_result.metadata.question_card` 是公共投影，**不含答案**（`INV-07`）。
- `mastery_quiz` 出题即结束回合（`turn_end.reason = "card"`）。

---

## 7. 工具清单（Loop 挂载）

| 工具 | 归属模式 | 作用 |
| --- | --- | --- |
| `mastery_build` / `mastery_revise` | outline | 生成 / 编辑大纲 |
| `mastery_quiz` | study/review | 出题（注册答案 + 出卡 + 结束回合） |
| `mastery_grade` | study/review | 确定性判分（幂等） |
| `mastery_assess` | study/review | concept/design 定性通过 |
| `mastery_skip_question` | study/review | 放弃当前题 |
| `mastery_note_explained` | study/review | 记录讲解（不授予掌握） |
| `mastery_defer_objective` | study/review | 暂时跳过某目标 |

> 未记录的 mode（CLI/SDK）**不门控**；错误模式下调用被拒且零状态变更。

---

## 8. 端到端最小脚本

```python
from masterypath.learning.storage import LearningStore
from masterypath.learning.service import LearningService
from masterypath.learning.models import PendingQuestion

store = LearningStore("data"); service = LearningService(store)
service.build("p", {"modules": [{"name": "M", "knowledge_points": [
    {"name": "fact one", "type": "memory"}]}]})
service.register_question("p", PendingQuestion(
    question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"))
print(service.grade("p", "q1", "4"))          # -> gate_cleared True
print(service.get_state("p")["next"]["action"])   # 全部掌握 -> complete（到期后 -> review）
store.close()
```

---

## 9. 文件夹知识库

- `scan_folder(root)` 递归扫 `.txt/.md`（跳过隐藏与 `node_modules/.venv/__pycache__` 等）。
- 每个文件 → `TopicSource`：`id=src:相对路径`、`label=相对路径`、`excerpt=前 500 字`。
- 引用键：大纲 `materials/sources` 用 `label`；**唯一文件名**可作别名。
- 缺口自动生效：文件没用上 → `source_omission`；KP 无来源 → `goal_gap`（角标「待补来源」）。
- PDF/DOCX 未支持（可在 `knowledge/loader.py` 同接口后扩展）。

---

## 10. 前端（M7，暂未验收）

```bash
cd web
npm install
npm run dev     # http://localhost:3000/?path=<pathId>
```

- 后端地址：`NEXT_PUBLIC_API_BASE`（默认 `http://127.0.0.1:8001`）。
- 工作区：当前主题 / 路标 / 进度环 / 大纲树 / 对话 / 三模式按钮 / 输入框（Tab 采纳建议）/ Activity 抽屉 / 侧边查看器。

---

## 11. 注意事项

- **改配置用 ADR**：规格包要求变更先写 ADR（`docs/00`），不就地改值。
- **答案不外泄**：`expected_answer`/`explanation` 只在服务端，公共投影永不含它们。
- **解析不了不判错**：判分遇到无法解析的作答返回 `ungraded`，零状态变更。
- **声明 ≠ 评估**：声明掌握推进地图但**不写分数**，且会以更低稳定度播种复习。
- **重建会重置进度**：非空路径 `build` 需 `confirm`，先告知学习者将丢失什么。
