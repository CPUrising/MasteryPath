# MasteryPath Web（M7 工作区）

Next.js（App Router）+ React + TypeScript 的三模式学习工作区。**尚未验收**：
本环境无 Node/浏览器基线，代码为脚手架，未运行 `npm install` / `next build`。

## 结构

```
app/            路由与布局（page.tsx 读取 ?path=）
components/     Workspace / ModeBar / ProgressRing / OutlineTree /
                Transcript / Composer / ActivityDrawer / SideViewer
lib/            api.ts（REST 客户端）、turn.ts（WS 回合）、types.ts
```

## 运行（需自行验证）

```bash
npm install
npm run dev          # 默认 http://localhost:3000/?path=<pathId>
```

后端地址通过 `NEXT_PUBLIC_API_BASE`（默认 `http://127.0.0.1:8001`）配置。

## 与后端的对应

- 当前主题 / 路标 / 进度环 ← `GET /learning/paths/{id}`（`map` + `next`）
- 三模式按钮 ← `PUT /learning/paths/{id}/sessions/{sid}/mode`
- 大纲树 + 声明掌握 ← `map` / `POST .../objectives/{kp}/override`
- 对话 + 提问卡片 ← `WS /ws`（`text_delta` / `tool_result.question_card`）
- 建议下一问（Tab 采纳）← `GET /learning/paths/{id}/suggest-question`
- 侧边查看器 / 缺口处理 ← `gaps` / `POST .../gaps/{gap}/resolve`
- Activity 抽屉 ← 本轮 WS 事件

## 说明

- 学习者的内部调度量（S₀/D₀/公式）**不暴露**（`INV-19`）；UI 只展示掌握度与目标线。
- `ungrounded` 知识点显示「待补来源」角标（`INV-24`）。
