# 为项目设置 Task 存储

在初始化 Task 前、Core 报告项目未初始化时，或项目根目录、存储模式、注册表或 Git 策略证据冲突时，阅读此参考文档。

## 目录

- [写入前先决定](#写入前先决定)
- [配置](#配置)
- [初始化嵌入存储](#初始化嵌入存储)
- [初始化分离存储](#初始化分离存储)
- [理解项目发现](#理解项目发现)
- [处理 Git 策略](#处理-git-策略)
- [解决设置失败](#解决设置失败)
- [尊重迁移边界](#尊重迁移边界)

## 写入前先决定

Task 存储始终属于一个项目。不要创建全局无绑定 Task 根目录，也不要让 `task_create` 静默初始化存储。

在运行 init 前：

1. 解析预期的项目根目录。默认使用 Git 根目录；在单仓库中使用仓库根目录，除非用户有意使用其他工作区边界。
2. 选择 `embedded` 或 `detached`。
3. 对嵌入存储，有意选择 `ignore`、`track` 或 `none`。
4. 检查是否已存在 `.agents/task.yaml`、嵌入的 Task 根目录或分离注册表条目。
5. 解释任何新的跟踪/忽略文件或全局注册表写入，然后获得用户同意。

如果在创建过程中 Core 返回 `project_not_initialized`，停止该创建操作并询问是否初始化。原始的顶层创建确认本身不选择存储模式或 Git 策略。

## 配置

Core 按以下顺序合并配置：

```text
内置默认值 < 用户配置 < 项目配置
```

用户配置：

```text
${XDG_CONFIG_HOME:-~/.config}/task/config.yaml
```

可选的项目配置：

```text
<project-root>/.agents/task.yaml
```

项目文件是覆盖，而非初始化标记。它可能不存在、为空或为空映射。仅当项目需要非默认值时创建它。

受管设置：

| 设置 | 默认值 | 含义 |
| --- | --- | --- |
| `data_dir` | `${XDG_DATA_HOME:-~/.local/share}/task/` | 分离数据根目录 |
| `mode` | `embedded` | `embedded` 或 `detached` |
| `task_root` | `.task` | 嵌入根目录（相对于项目根目录） |
| `git_policy` | `ignore` | `ignore`、`track` 或 `none` |
| `creation_policy` | `strict` | 顶层创建策略 |
| `wal_max_length` | `2000` | 默认 WAL 字符预算 |
| `wal_max_entries` | `20` | 默认 WAL 记录预算 |

Core 忽略未知配置字段。它验证它看到的每个受管值。`data_dir` 展开 `~` 后必须为绝对路径；它不展开任意环境变量。`task_root` 必须保持在项目内且不能包含父级遍历。

在 init 前写入项目覆盖，以便 init 使用自定义 `task_root`、`data_dir` 或 creation 策略。不要手动创建受管 Task 数据作为 init 的替代。

## 初始化嵌入存储

嵌入存储将 Task 根目录放在项目内，使 Task 易于在编辑器中发现和打开。

典型的仅本地设置：

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy ignore
```

跟踪的 Task 状态：

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy track
```

完全用户管理的 Git 行为：

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy none
```

解析后的 Task 根目录是初始化证据。Core 不创建 ROOT 标记；手动创建的目录也被视为已初始化，即使 Core 无法证明其创建方式。

默认布局开始于：

```text
<project-root>/.task/
├── .cache/
└── YYYY-MM/DD/NN--<slug>/
```

初始化后，检查结构化结果和 Git 状态。不要假定成功的过程创建了项目配置文件；Core 仅在需要覆盖时才需要该文件。

## 初始化分离存储

分离存储将 Task 数据放在用户数据目录下，同时通过权威注册表绑定到项目：

```text
${XDG_CONFIG_HOME:-~/.config}/task/projects.yaml
```

使用默认的项目目录 basename 作为 slug 初始化：

```bash
task-core init --project-root /absolute/project --mode detached
```

或选择显式 slug：

```bash
task-core init --project-root /absolute/project --mode detached --project-slug stable-project-name
```

结果根目录为：

```text
<data_dir>/<project_slug>/
```

相同权威项目路径的重新初始化复用其现有 slug。如果另一个项目已拥有请求的 slug，Core 返回 `project_slug_conflict`；选择有意义的替代而非发明隐式哈希。

将 `projects.yaml` 视为权威的用户可编辑配置，而非可丢弃的索引。如果项目移动或重命名，有意更新映射。Core 没有项目注册表迁移命令。

`git_policy` 不会使分离数据成为项目仓库的一部分。将分离根目录及其备份/同步策略分开处理。

## 理解项目发现

在每次 Task 工具调用时传入当前绝对工作区 `cwd`。MCP 和包进程从插件目录启动，这不是项目上下文。

Core 从 cwd 向上遍历到最近的一致证据，在存在 Git 根目录时停止。证据包括嵌入的 Task 根目录和分离注册表映射。Git 本身是搜索边界和默认初始化根目录，而非 Task 已初始化的证明。

当最近的证据在根目录或模式上不一致时，Core 停止而非猜测。一个工作现场解析为一个项目 Task 根目录；层次结构和结构化关系从不跨项目边界。

更改工作树或工作区目录后，传入新的 cwd。不要在宿主状态中持久化项目或 Task 绑定。

## 处理 Git 策略

对于嵌入存储：

- `ignore` 在 Task 根目录自身的 `.gitignore` 中创建或追加 `*`。如果 `.agents/task.yaml` 存在，Core 还会将该文件名和 `.gitignore` 追加到 `.agents/.gitignore`。
- `track` 使规范的 Task 数据对 Git 可见，同时 `.cache/` 保持被忽略。
- `none` 不做任何 Git 管理变更。

Core 不编辑项目根目录的 `.gitignore`、不暂存文件、不移除已跟踪的文件也不提交。它幂等地追加并保留现有内容。

如果 `track` 与现有忽略规则或 Task 根忽略文件冲突，Core 停止。展示冲突让用户决定如何更改 Git 状态。不要静默删除忽略规则或运行 `git rm`。

初始化后检查 Git 状态，确认观察到的跟踪/忽略行为与所选策略匹配。

## 解决设置失败

使用结构化错误并仅检查相关配置和路径：

- `project_not_initialized`：在 init 前确认项目根目录、模式和 Git 策略。
- `root_conflict`：检查最近的项目配置、嵌入根目录和分离注册表条目；不要静默选择其中一个。
- `task_root_missing`：保留分离注册表并确定数据根目录是已移动、已删除还是从未同步。
- `project_slug_conflict`：选择另一个显式 slug 或在用户批准下修正过时的注册表条目。
- `task_root_outside_project` 或配置错误：修正受管设置；不要削弱包含规则。
- `git_policy_conflict`：显式协调 Git 忽略/跟踪状态。

不要编辑 Task ID、生成的 Task 目录或受管 frontmatter 来修复项目发现。项目发现成功后的 Task 数据损坏，请阅读[诊断与修复](diagnostics-and-repair.md)。

## 尊重迁移边界

Core 不迁移：

- 嵌入到分离存储或反向；
- 从一个 `task_root` 到另一个；
- 从一种 Git 策略到另一种；
- 项目移动后的分离注册表条目；
- 数据模式。

将这些计划为显式的、用户批准的迁移。对于 Trellis 数据，阅读[迁移 Trellis Task](migrate-from-trellis.md)；不要手动构建目标 Task 元数据或路径。
