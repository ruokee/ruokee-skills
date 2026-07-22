# Task 模型

Task 是用户已经决定推进的一项临时性努力的持久载体。它保存当前状态、关系、材料入口和工作活动，不是 backlog、会话 todo 或 Agent runtime ownership。

## 身份与引用

每个 Task 使用不可变 UUIDv7 作为永久身份。路径、名称、目录名和 branch 是可变的人类入口，不是事实身份。

Core 支持以下显式引用：

- 完整 UUIDv7；
- Task 的绝对路径；
- 相对 project root 的明确路径；
- 精确 Task 名称；
- 精确目录名。

不支持 UUID 前缀。引用不唯一时返回 `task_ref_ambiguous`；Agent 必须让用户选择，不能按相似度、最近时间或隐式 current Task 静默决定。

## 顶层 Task 与 subtask

顶层 Task 直接属于 project。subtask 通过物理目录嵌套归属最近合法祖先 Task，不保存 `parent_id`。

父子结构不自动产生依赖，也不级联状态。一个 Agent 可以顺序处理多个 subtask，多个 subagent 也可以在同一 Task 树中并行；subagent 和 subtask 不是一一映射。

顶层创建遵循 `creation_policy`：

- `strict`：当前对话必须有用户明确创建/任务化确认；
- `permissive`：Agent 可以为明显持续、多阶段或跨会话的工作创建，并在同一轮告知用户。

快速修改、一次性回答、尚未开展的想法和普通 TODO 不进入 Task。已分配 Task 树内创建 subtask 不需要新的顶层确认。

## 名称与 slug

Task name 经过 NFC 规范化并去除首尾空白，最多 40 Unicode 显示列和 96 UTF-8 bytes；拒绝空名称、NUL 和换行。中文、大小写、emoji 和可见标点可以保留。

Core 唯一生成目录 slug：`/`、`\`、Unicode 空白和 ASCII 控制字符替换为 `-`，连续 `-` 合并，去掉首尾 `-` 和 `.`。结果为空时拒绝。

调用方不能传入 slug 或目录名。相同分区中的目标目录已存在时返回冲突，不自动加随机后缀。

## `TASK.md`

每个 Task 目录包含一个 `TASK.md`。YAML frontmatter 保存 Core 管理的结构化状态，正文保存用户和 Agent 共同维护的当前事实。

```yaml
---
schema_version: "2026-07-21"
id: 019...
name: 实现任务系统 MVP
status: open
archived: false
created_at: 2026-07-21T14:30:00.123+08:00
branch: feat/task-system
depends_on:
  - 019...
related_to:
  - 019...
last_transition_reason: 等待真实使用反馈
extra:
  owner_note: 先支持 Linux
---

这里呈现任务现在是什么、目标、范围和材料入口。
```

| 字段 | 要求 | 语义 |
| --- | --- | --- |
| `schema_version` | 必填 | 当前数据 schema；MVP 不迁移旧版本 |
| `id` | 必填 | 不可变 UUIDv7 |
| `name` | 必填 | 展示名称 |
| `status` | 必填 | `open`、`paused`、`closed` |
| `archived` | 必填 | boolean；只有 closed 才能为 true |
| `created_at` | 必填 | 带时区的 RFC 3339 时间 |
| `branch` | 可选 | branch 名本身，不保证存在 |
| `depends_on` | 可选 | 同 project 的完整 Task ID 列表 |
| `related_to` | 可选 | 同 project 的完整 Task ID 列表 |
| `last_transition_reason` | 可选 | 最近一次 lifecycle 转移原因 |
| `extra` | 可选 | `dict[str, Any]` 扩展字段 |

不保存可推导或没有稳定语义的 parent、路径、project、Task 类型、assignee、session、active、revision、etag、updated/closed time。

未知 frontmatter 顶层字段透明保留。Core 修改 managed fields 时尽量保留字段顺序、注释、引号、anchor 和未知数据，并保持正文 bytes 不变。重复 key、自定义不安全 YAML tag 或无法可靠解析的内容会阻止修改，不能猜测后覆盖。

schema 或 managed fields 非法的目录仍是 Task candidate。按路径读取返回正文、`managed_valid: false` 和错误；它不进入关系图，也不能 update 或写 WAL。

## 正文与普通材料

正文只写当前事实，不写“从 A 改成 B”之类的过程叙述。过程进入 WAL；分析、计划、研究、handoff、checkpoint 和大型产物使用 Task 目录中的普通文件，正文只提供重要入口。

Core 不枚举普通材料。Agent 从 `task_read` 获得绝对 `task_dir` 后使用宿主文件工具读写材料。

## 关系

| 关系 | 表达 | 约束 |
| --- | --- | --- |
| 父子 | 目录嵌套 | 最近合法祖先；不自动依赖或级联状态 |
| 依赖 | `depends_on` | 有向、同 project、禁止 self 和 cycle；阻塞正常关闭 |
| 关联 | `related_to` | 同 project、禁止 self；不影响生命周期 |

结构化关系只保存完整 Task ID，不保存路径或名称。`related_to` 是单向 outgoing，Core 在 read/check 时反向推导 `related_from`。

人工写入的失联依赖会阻止正常关闭；失联关联只产生 warning 并保留 ID。跨 project 弱关联只能写在正文或普通材料中。

## 生命周期

```text
open ⇄ paused
  │       │
  └───┬───┘
      ▼
    closed ──reopen──> open
```

所有状态转移必须提供 reason，并更新 `last_transition_reason`；Core 自动追加机械 WAL。reopen 固定回到 `open`。

正常关闭前递归检查：

- 所有后代 Task 都是 `closed`；
- 所有 `depends_on` 都能解析且为 `closed`；
- 不存在依赖环。

用户可以显式要求 force close。它只关闭目标，不级联修改后代，并在 WAL 中记录被绕过的检查。关闭 parent 后普通发现不再向下遍历；完整 UUID、明确路径或 check 仍能穿透。

archive 是与三态正交的 boolean，不移动目录。只有 closed Task 能 archive；archived Task 不能 reopen。unarchive 需要 reason 和当前用户明确同意，完成后仍为 closed；继续工作要再单独 reopen。

## Rename

`task_update` 不修改 name。rename 是 project-wide 低频 CLI 操作，同时更新 `TASK.md.name`、leaf slug 和可确定的 project 引用，保留 UUID、日期分区、日内序号、parent 和内容。

rename 先 dry-run。能唯一判断的绝对/相对文本路径和 symlink target 可更新；裸 slug、编码路径和歧义引用进入 `manual_review`。存在 unresolved 时默认拒绝，只有用户同意后才能用 `--allow-unresolved` 继续。

历史 WAL 不改写，旧路径不留 alias 或 symlink；rename 追加包含新旧名称、路径和处理统计的 WAL。完整 runtime 流程见 [rename reference](../package/skills/task/references/rename.md)。
