# MasteryPath Web（M7 · 对齐 DeepTutor）

Next.js（App Router）+ React + TypeScript + Tailwind 的三模式学习工作区，页面构成对齐 DeepTutor：
`AppShell` + 侧栏、mastery 三页（图集 / 仪表盘 / 学习工作区）、设置中心（Providers / Language models / Task models / Embedding / General）。

**未验收**：本环境无 Node，代码未运行 `npm install` / `next build`。

## 运行

```bash
cd web
npm install
npm run dev          # http://localhost:3000  → /learning/mastery
```

后端：`NEXT_PUBLIC_API_BASE`（默认 `http://127.0.0.1:8001`）。先启动后端（见仓库根 `USAGE.md`）。

## 结构

```
app/
  layout.tsx                        根布局 + i18n
  (workspace)/layout.tsx            AppShell + 侧栏
  (workspace)/page.tsx              → /learning/mastery
  (workspace)/learning/mastery/page.tsx                     图集（TopicAtlas）
  (workspace)/learning/mastery/[pathId]/page.tsx            仪表盘
  (workspace)/learning/mastery/[pathId]/sessions/page.tsx   学习工作区
  (settings)/layout.tsx             AppShell + SettingsNav
  (settings)/settings/[section]/page.tsx
components/
  layout/AppShell · sidebar/WorkspaceSidebar
  common/{I18nProvider,Tooltip,Modal,ConfirmDialog}
  learning/{LearningShell,TopicAtlas,TopicMapCard,ModuleOutline,StudyOutline,
            ProgressRing,ReviewTrail,SessionCamp,LearnerProfileCard,ModeSwitch,
            MasteryComposer,QuestionCard,LevelUpCelebration,
            CreateTopicWizard,EditTopicRouteDialog}
  settings/{SettingsShell,SettingsNav,SettingsPageContent,WorkspaceShell,
            ProviderCatalog,AddProviderPanel,ProvidersWorkspace,
            AddModelPanel,ModelsWorkspace,SettingsOverview,shared}
lib/{api,ws,types,mastery-mode,learning-routes,i18n}
i18n/{zh,en}.json
```

## 与后端的对应

- 图集/仪表盘 ← `GET /learning/paths`、`GET /learning/paths/{id}`（`map/counts/next/reviews/review_settings/sources/learner_profile`）
- 三模式 ← `PUT /learning/paths/{id}/sessions/{sid}/mode`
- 大纲编辑 ← `PUT /learning/paths/{id}/map`（需 outline 模式）
- 声明掌握 ← `POST .../objectives/{kp}/override`；重置/删除 ← `POST .../redo`、`DELETE`
- 复习目标 ← `PUT .../review-settings`
- 接资料 ← `POST .../sources`
- 学习工作区 ← `WS /ws`（对话）与 `POST .../quiz|grade|assess|skip-question`（**无 LLM 也能判分**）
- 设置中心 ← `GET/PUT /settings/{section}`

## 说明

- 状态语言用**形态**（filled→ring→outline），不靠颜色（`globals.css` 的 `mastery-*`）。
- 学习者内部调度量（S₀/D₀/公式）**不暴露**；`ungrounded` 知识点显示「来源」标记。
- 对话回合需要已配置的模型提供方；未配置时输入框旁给出提示（出题/判分走 REST，不依赖模型）。
