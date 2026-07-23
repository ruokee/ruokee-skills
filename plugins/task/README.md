# Task

`Task` 是面向 Codex、Claude Code 和 Pi 的持久化项目任务模块。它用 Markdown/YAML 文件保存 Task 当前状态和工作活动，用一个不调用模型的 Python Core 统一处理发现、校验、生命周期、关系、WAL、锁与路径解析。

## Workspace

```text
plugins/task/
├── core/       # uv packaged application、CLI、MCP 与测试
├── design/     # 当前规范设计与验证范围
├── package/    # 三个宿主共同安装的自包含 package root
├── scripts/    # contract 生成与 Nuitka package 构建
├── variants/   # 相对英文 Skill base 的语言 overlay
└── meta.toml   # 仓库安装器的 meta-v2 变体入口
```

当前设计权威和维护入口见 [`design/`](design/README.md)。runtime Agent 的高频规则位于 `package/skills/task/SKILL.md`，完整操作说明按需放在其 `references/` 中。

`package/skills/task/` 是完整英文 base，也是 plugin 默认携带的唯一规范 Skill 源；`variants/zh/` 只保存可翻译文件的中文 overlay。仓库安装器将 overlay 覆盖到英文 base 上物化完整中文 Skill，Core、adapter、schema 和其他 package 文件不进入语言变体。

开发检查：

```bash
cd core
uv lock --check
uv run --frozen ruff check src tests
uv run --frozen mypy src
uv run --frozen pytest
```

生成 Linux x86_64 standalone package：

```bash
uv run --project core scripts/build-package.py
```

构建结果位于 `package/runtime/linux-x86_64/task-core.dist/`，不纳入 Git。`package/bin/task-core` 是宿主使用的稳定入口。

## 本地安装

先完成 standalone package 构建，再从仓库根目录注册各宿主：

```bash
# Codex
codex plugin marketplace add /path/to/ruokee-skills
codex plugin add task@ruokee-skills

# Claude Code
claude plugin marketplace add /path/to/ruokee-skills --scope user
claude plugin install task@ruokee-skills --scope user

# Pi
pi install /path/to/ruokee-skills/plugins/task/package
```

三套 adapter 与 Core 在 `0.x` 阶段按同一个模块版本发布。可用 `package/bin/task-core --version` 核对模块版本、进程协议版本和数据 schema 版本。

本地迭代时，Codex manifest 可在模块版本后添加 `+codex.<cachebuster>` 构建元数据以刷新插件缓存；其 `+` 前缀仍须与另外两套 adapter 和 Core 版本一致。

default 是完整英文 base。选择中文变体时，从仓库根目录运行：

```bash
uv run scripts/install.py setup task --scope user --variant zh
```

安装器会先验证或完成所选宿主的原生 Task 安装，再只替换其中的 Skill 变体；Core、MCP 和宿主 adapter 仍来自上面的 plugin/Pi package 安装流程。`update` 会在宿主更新后重放已记录变体，`reset` 恢复 default，但都不会卸载 Task。

## 项目 local Skill

项目 scope 只把 Task Skill 物化到消费项目，不复制 Core、MCP 或 Pi extension：

```bash
uv run scripts/install.py setup task --scope project --project /path/to/project --variant zh
```

因此，执行前必须已为所选宿主完成上面的用户级原生安装并具备可用 runtime；缺少 runtime 时安装器会在写入项目前拒绝。
