# Project 与存储

每个 Task 严格属于一个 project。系统支持 embedded 和 detached 两种存储模式，但不提供脱离 project 的 global Task root。

## 配置层级

有效配置按以下优先级合并：

```text
内置默认值 < 用户配置 < project 配置
```

用户配置：

```text
${XDG_CONFIG_HOME:-~/.config}/task/config.yaml
```

可选 project 配置：

```text
<project-root>/.agents/task.yaml
```

project 配置是纯 YAML override，不是初始化标记；文件可以不存在、为空或是空 mapping。未知字段透明忽略，只有 Core 管理字段会被合并和校验。

| 字段 | 默认值 | 语义 |
| --- | --- | --- |
| `data_dir` | `${XDG_DATA_HOME:-~/.local/share}/task/` | detached 数据根 |
| `mode` | `embedded` | `embedded` 或 `detached` |
| `task_root` | `.task` | project 内的 embedded root |
| `git_policy` | `ignore` | `ignore`、`track` 或 `none` |
| `creation_policy` | `strict` | 顶层 Task 创建策略 |
| `wal_max_length` | `2000` | 默认 WAL 字符预算 |
| `wal_max_entries` | `20` | 默认 WAL 条目预算 |

`data_dir` 展开 `~` 后必须是绝对路径，不展开任意环境变量。`task_root` 必须是 project root 内的相对路径，不能通过 `..` 逃逸。

## Embedded

embedded 把 Task root 放在 project 内，便于 Agent 发现和用户从编辑器访问。解析后的 Task root 目录存在就是初始化证据；系统不写 ROOT marker，用户手工建立该目录也会被视为已初始化。

默认布局：

```text
<project-root>/
├── .agents/task.yaml          # 仅在需要 override 时存在
└── .task/
    ├── .cache/
    └── YYYY-MM/
        └── DD/
            └── NN--<slug>/
```

显式运行 init 是 Agent 工作流约束，用来让用户有机会选择 storage 和 Git policy；目录存在本身无法证明历史上是否运行过 init。

## Detached

detached 把 Task 数据放入全局数据目录，但 Task 仍绑定 project。初始化时写入权威登记：

```text
${XDG_CONFIG_HOME:-~/.config}/task/projects.yaml
```

登记保存 canonical project 绝对路径到 `project_slug` 的映射。Task root 为：

```text
<data_dir>/<project_slug>/
```

`project_slug` 默认使用 project 目录 basename，也可在 init 时指定。同一路径重复初始化复用已有 slug；slug 已被另一 project 使用时返回冲突，不自动增加 hash 或随机后缀。

registry 是可编辑的权威配置，不是可丢弃索引。project 改名或移动后由用户和 Agent 手工修正映射；MVP 没有 Core 迁移命令。

## Project 发现

Core 从请求 `cwd` 向上查找最近的一组初始化证据：

- project config 对应的 embedded root；
- 实际存在的 embedded root；
- detached registry 中的 canonical path 映射。

Git root 是默认 init root 和向上搜索边界，不是初始化证据。发现同一最近 project 上存在冲突的 root 或 mode 时返回 `root_conflict`，不静默猜测。

monorepo 默认绑定整个 repository root。一个 worksite 最终只选择一个 project Task root；父子、依赖和关联关系都不能跨 project。

未初始化时 create 返回 `project_not_initialized`。创建不能顺带静默 init；Agent 需要说明选择并取得用户同意后调用低频 CLI。

## Task 目录

顶层 Task 按创建时间的本地日历日期分区：

```text
<task-root>/YYYY-MM/DD/NN--<slug>/
```

`NN` 是 `01..99` 的日内序号。创建优先使用当前最大序号加一；到达 99 后使用最小空位；没有空位时失败。序号只改善排序和可见性，不是身份。

subtask 的规范位置是：

```text
<parent-task>/subtasks/NN--<slug>/
```

发现不依赖 `subtasks/` 目录名：任何位于合法 Task 下、包含合法 `TASK.md` 的普通目录都是 subtask，parent 是最近合法祖先 Task。系统不跟随目录 symlink，`TASK.md` 必须是普通文件；普通材料中的 symlink 不参与 Task 发现。

层级没有业务深度上限。实现使用迭代遍历，并受操作系统路径和组件长度限制。

## 路径稳定性

状态变化和 archive 不移动目录。UUIDv7 是永久身份，路径只是尽量稳定的人类入口。

用户可以手工移动 Task，Core 会根据当前位置重新推导 parent。`name_slug_mismatch` 和 `noncanonical_task_path` 是 warning，不阻止普通读写；重复 UUID、managed fields 非法、目标冲突和跨 project 路径会阻止修改。

`.cache/` 只保存可丢弃、可重建的数据。它包含 `CACHEDIR.TAG`，不属于规范 Task 状态。

## Git policy

`git_policy` 与 storage mode 独立，但主要影响 embedded：

- `ignore`：默认。Task root 自包含 `.gitignore`，使用 `*` 忽略整个 root；存在 project config 时在 `.agents/.gitignore` 中忽略它。
- `track`：规范 Task 数据可以进入 Git，`.cache/` 始终忽略。
- `none`：Core 不管理 Git ignore 或 tracking 行为。

Core 只做幂等追加，不覆盖已有 ignore 内容，不修改 project root `.gitignore`，不执行 `git add`、`git rm` 或 commit。选择 `track` 与现有 ignore 状态冲突时停止，让用户处理。

MVP 不提供 embedded/detached 或 Git policy 之间的自动迁移。runtime 初始化与故障处理见 [project setup reference](../package/skills/task/references/project-setup.md)。
