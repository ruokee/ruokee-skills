# 架构

Task 使用一个确定性 Core 和多宿主薄适配器。领域规则只实现一次，宿主差异停留在安装、manifest、工具注册和调用方式上。

## 四层结构

| 层 | 职责 | 不承担 |
| --- | --- | --- |
| Core / application service | project 与 Task 发现、读取、校验、创建、更新、关系、生命周期、WAL、锁、路径解析 | 自然语言理解、宿主会话、开放式摘要 |
| CLI | 完整管理面、低频 init/check/rename、统一 JSON 进程入口 | 复制另一套领域规则 |
| Agent contract | 五个高频语义操作 | init、rename、诊断等低频管理功能 |
| Host adapter | 安装、manifest、工具注册、宿主环境与 actor 上下文 | 修改公共领域语义 |

公共 Agent 知识由一份 canonical Skill 及其 references 提供。Codex、Claude Code 和 Pi 不复制或改写这套知识；适配器只暴露相同契约。

## Core

Core 使用 Python 实现，不调用 LLM，也不根据自然语言推断 Task。它接收结构化请求，根据文件系统与配置解析 project 和 Task，执行确定性校验与写入，然后返回结构化结果。

Core 同时支持：

- Python 源码入口，用于开发和测试；
- `task-core` CLI；
- stdio MCP server；
- `task-core invoke <operation>` 的 stdin/stdout JSON 协议；
- Nuitka standalone 构建产物。

领域失败不会依赖宿主异常机制。CLI `invoke` 在进程和 JSON 协议正常时即使领域操作失败也返回零退出码，调用方读取结构化 `ok: false`；只有 transport/process 失败返回非零退出码。

## CLI 与高频契约

CLI 是完整管理面。当前低频命令包括：

- `task-core init`：初始化 embedded 或 detached project；
- `task-core check`：检查当前 project 的 Task 结构；
- `task-core rename`：dry-run 并执行 project-wide rename；
- `task-core --version`：返回模块、进程协议和数据 schema 版本。

五个高频操作是：

- `task_find`；
- `task_read`；
- `task_create`；
- `task_update`；
- `task_log`。

它们的分工与返回语义见 [Agent 契约](agent-contracts.md)。输入字段由 `core/src/task_core/contracts.py` 定义，并生成到 `package/contracts/task-tools.schema.json`；设计文档不维护第二份字段 schema。

## 宿主适配

Codex 和 Claude Code 通过本地 stdio MCP 使用五个工具。package 内的 MCP launcher 从宿主提供的 plugin root 找到稳定入口，并设置 `TASK_HOST`，而不把 MCP server 的进程 cwd 当作用户 project。

Pi extension 注册同名原生工具，通过 `task-core invoke` 启动独立进程：请求从 stdin 输入 JSON，结果从 stdout 输出 JSON，诊断写入 stderr。MVP 每次调用启动一个进程，不使用 daemon。

所有工具请求都应显式传入当前 workspace 的绝对 `cwd`。Agent 切换目录或 worktree 后重新解析 cwd，避免 package/plugin 的启动目录被误当成 project context。

## 调用与结果流

```text
Agent
  │ semantic request + cwd
  ▼
Host adapter / MCP
  │ exact shared contract
  ▼
Core application service
  │ config + filesystem + locks
  ▼
Task files and WAL
```

成功结果使用统一 envelope：

```json
{
  "ok": true,
  "data": {},
  "warnings": []
}
```

可预期领域失败使用：

```json
{
  "ok": false,
  "error": {
    "code": "task_ref_ambiguous",
    "message": "...",
    "details": {}
  }
}
```

当主状态已经提交、自动 WAL 追加随后失败时，操作仍然成功，并以 `committed: true` 和 warning 表达部分提交。调用方不得把它当作整体失败后盲目重试。

## 分发与版本

源码位于 `plugins/task/core/`，可安装 package 位于 `plugins/task/package/`。开发使用 uv packaged application；发布构建用 Nuitka `--mode=standalone` 生成 `package/runtime/linux-x86_64/task-core.dist/`，稳定入口是 `package/bin/task-core`。

`package/runtime/` 是构建产物，不进入 Git。构建保存 `BUILD-INFO`，并在构建前执行锁文件、代码质量、类型检查、测试和契约生成。

0.x 阶段 Core、Codex plugin、Claude plugin 和 Pi package lockstep 发布，但仍区分：

- Task 模块版本；
- Core process protocol version；
- Task data `schema_version`。

安装状态由各宿主原生机制管理，Task 不维护第二套安装数据库。任何 adapter 都必须得到与其模块版本匹配的 Core。

当前真实宿主与 standalone 验证缺口见 [implementation gaps](validation-and-scope.md#implementation-gaps)。
