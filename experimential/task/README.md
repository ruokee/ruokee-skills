# Task

`Task` 是面向 Codex、Claude Code 和 Pi 的持久化项目任务模块。它用 Markdown/YAML 文件保存 Task 当前状态和工作活动，用一个不调用模型的 Python Core 统一处理发现、校验、生命周期、关系、WAL、锁与路径解析。

## Workspace

```text
task/
├── core/       # uv packaged application、CLI、MCP 与测试
├── package/    # 三个宿主共同安装的自包含 package root
└── scripts/    # contract 生成与 Nuitka package 构建
```

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
claude plugin marketplace add /path/to/ruokee-skills
claude plugin install task@ruokee-skills

# Pi
pi install /path/to/ruokee-skills/experimential/task/package
```

三套 adapter 与 Core 在 `0.x` 阶段按同一个模块版本发布。可用 `package/bin/task-core --version` 核对模块版本、进程协议版本和数据 schema 版本。

本地迭代时，Codex manifest 可在模块版本后添加 `+codex.<cachebuster>` 构建元数据以刷新插件缓存；其 `+` 前缀仍须与另外两套 adapter 和 Core 版本一致。
