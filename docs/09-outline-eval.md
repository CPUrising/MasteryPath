# 09 · 大纲生成质量评测（ADR-018）

> 目的：把"自动生成的学习路径准不准"从主观判断变成**可复现、可对比**的度量（`INV-57`）。
> 原则：**确定性指标优先**（无模型裁判）；语义指标用**嵌入匹配**；在线用**编辑率**作代理。

## 一、两层：在线报告 + 离线评测

### 1. 在线覆盖报告（每次 `build` 返回，`INV-56`）
`CoverageReport`（见 `01`）：

| 字段 | 含义 | 确定性 |
| --- | --- | --- |
| `documents` / `covered` / `missing[]` | 选中来源被用上的比例 | ✅ |
| `reported` | 模型是否声明了 materials；`false` ⇒ 不下结论 | ✅ |
| `grounding_ratio` | 有可解析来源的 KP / 总 KP | ✅ |
| `acyclic` | 前置图无环 | ✅ |

> `reported=false` 时**不得**把未用来源当作"漏掉"展示（避免误伤已覆盖的大纲）。

### 2. 离线评测（golden set）
用一组"目标 + 资料 + 参考大纲"跑指标，产出可对比基线。

**用例格式**（`cases.jsonl`，每行一个 JSON）：
```json
{"id":"case-1",
 "goal":"掌握 Rust 并发",
 "materials":["/path/to/notes.md"],
 "reference_modules":[{"name":"并发基础","knowledge_points":[{"name":"理解线程与进程","type":"concept"}]}]}
```

**命令**：
```
python -m masterypath.eval outline --cases cases.jsonl --baseline baseline.json [--min-coverage 0.9]
```

## 二、指标

**确定性（纯函数）**
| 指标 | 定义 | 通过线（⚠️ 暂定） |
| --- | --- | --- |
| `coverage_ratio` | `covered / documents` | `≥ 0.9` |
| `grounding_ratio` | 可解析来源的 KP / 总 KP | `= 1.0`（除非接受缺口） |
| `acyclic` | 前置图无环 | `true` |
| `count_in_bounds` | KP 数在按时间预算推算的区间内 | `true` |
| `type_sanity` | 四类型均有且分布合理 | 软性 |

**语义（嵌入匹配）**
| 指标 | 定义 |
| --- | --- |
| `kp_precision` | 生成 KP 中命中参考的比例 |
| `kp_recall` | 参考 KP 被生成覆盖的比例 |
| `kp_f1` | 上述调和平均 |

> 匹配：对 KP 名称/描述做嵌入（bge-m3），相似度 ≥ 阈值视为同一 KP；阈值可调（默认 0.8，⚠️ 暂定）。

## 三、回归与基线

- `--baseline baseline.json`：与上次基线逐指标对比，**退化**（超出容差）即非零退出。
- 用于：换提示词 / 换模型 / 改分块时的**回归检查**。
- 评分**可复现**：确定性指标不依赖模型；语义指标固定嵌入模型与阈值。

## 四、在线代理指标（无需 golden set）

| 代理 | 采集 | 含义 |
| --- | --- | --- |
| **编辑率** | `outline.revised` / `outline.built` | 生成后学习者改动越多 ⇒ 质量越可疑 |
| **重建率** | `path.rebuilt` / `outline.built` | 反复重建 ⇒ 生成不满意 |
| **缺口率** | `gap.detected` / `outline.built` | 覆盖不足的频率 |

## 五、验收测试

| ID | 用例 | 覆盖 |
| --- | --- | --- |
| TC-N1 | `build` 返回 `coverage`，字段齐全 | INV-56 |
| TC-N2 | 选中来源未被任何模块用上 → `missing` 含它、`coverage_ratio<1` | INV-57 |
| TC-N3 | `reported=false` → 不把未用来源展开为 `missing` | INV-56 |
| TC-N4 | 含环的前置 → `acyclic=false` | INV-57 |
| TC-N5 | `eval` 对低于 `min-coverage` 的用例报不达标并非零退出 | INV-57 |
| TC-N6 | 同一用例两次运行确定性指标一致（可复现） | INV-57 |

## 六、阈值与开放项（见 `00` §四）

- `coverage_ratio ≥ 0.9`、`grounding_ratio = 1.0`、`acyclic = true`：⚠️ 暂定。
- 语义匹配阈值（0.8）、嵌入模型（bge-m3）：⚠️ 暂定。
- golden set 素材：优先用仓库内 `docs/` 与示例资料构造（需产品方提供 2–3 个真实样例更佳）。
