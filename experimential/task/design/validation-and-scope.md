# 验证与范围

Task 的验收目标是 Agent 能从真实宿主稳定使用，而不只是 Core 函数或 CLI 单元测试通过。本文件区分已验证主链路、仍缺直接证据的 implementation gaps 和明确不在当前范围的能力。

## 支持范围

MVP 面向个人 Linux x86_64 环境：

- Python Core 和 CLI；
- Nuitka standalone runtime；
- Codex 与 Claude Code stdio MCP；
- Pi native extension 调用 `task-core invoke`；
- embedded 与 detached project storage；
- Markdown/YAML Task files 和 append-only WAL。

macOS、Windows、daemon、Web UI、数据库和跨设备一致性不属于当前正式支持范围。

## 测试层次

1. **Core contract tests**：配置、发现、读写、关系、生命周期、WAL、并发与文件边界。
2. **CLI tests**：init/check/rename 和 JSON invoke 的 exit/envelope 语义。
3. **Generated contract tests**：请求模型与发布 Schema 一致，package 版本 lockstep。
4. **MCP/Pi adapter smoke**：工具注册、输入结构和真实 Core 调用。
5. **Standalone smoke**：构建产物的 invoke、并发与 MCP。
6. **Installed host smoke**：从宿主真实安装入口调用五个高频契约。
7. **Skill forward-test**：Agent 能按 `SKILL.md` 路由到正确 reference，并在复杂场景遵守边界。

开发检查入口：

```bash
cd experimential/task/core
uv lock --check
uv run --frozen ruff check src tests
uv run --frozen mypy src
uv run --frozen pytest
```

构建脚本在生成 standalone 前执行相同检查并刷新 `package/contracts/task-tools.schema.json`。

## 纵向验收场景

当前规范至少覆盖：

1. Git project 中 init embedded + ignore，创建第一个顶层 Task。
2. detached init 写入 canonical project path → slug registry，并能从 project cwd 找回 root。
3. 新会话按 ID、名称、目录或 branch 找到唯一 Task，读取 summary；歧义时停止。
4. parent 下批量创建 subtasks，按目录推导 topology，并支持多个 Agent 分工。
5. 更新 branch、关系、extra 与 lifecycle，自动写 WAL；正常/force close 语义不同。
6. WAL 跨日增长后，metadata/summary/detailed 和双预算工作正常。
7. 并发创建得到不同槽位，不同 top Task 可以并行修改。
8. rename 保留身份和分区，更新确定引用，unresolved 需要用户确认。

Core 源码测试已经直接覆盖这些主链路。真实宿主与 standalone 证据仍按下节追踪。

## Implementation gaps

以下是当前已知差距，不应在 runtime Skill 或 references 中写成已经交付：

1. `tests/test_binary_smoke.py` 已存在，但普通源码测试未选择 `TASK_CORE_BINARY`，因此 standalone 构建产物尚缺本轮直接 smoke 证据。
2. Pi adapter 尚无自动 smoke test 证据。
3. Claude 已安装插件和 Codex 已安装插件尚无真实宿主入口 smoke 证据；源码 stdio MCP 五工具链路已通过，但不能替代安装后验证。
4. 当前 `task-core check` 只检查 duplicate UUID、invalid candidates、staging 和发现 warning，没有通用 repair 或独立 `doctor`。

design 可以描述已经决定但尚未实现的目标；新增 gap 时集中追加到这里，并从相关专题链接。实现和测试闭合后移除 gap，再同步 runtime reference 和必要的 `SKILL.md` 高频投影。

## 已决定的技术表面

研究阶段曾保留的多数实现问题已经由代码确定：

- Python distribution、module 和 `task-core` executable 已落地；
- CLI 命令树包含 init/check/rename/invoke/mcp/version；
- 当前 data schema 是 `2026-07-21`；
- 三宿主 manifests 和 0.x lockstep version 已落地；
- rename 和基础 check 已实现。

完整错误码表不作为手写 design artifact；错误由实现定义，文档只维护调用方需要区分的类别。

## 明确延后

以下内容不是遗漏：

- global Task root、跨 project 结构化关系；
- capture/backlog、issue/看板同步、宿主 todo 集成；
- Task 数据同步协议、分布式锁和冲突解决；
- current/active Task、assignee、lease 或 session mapping；
- 数据库、全文检索、daemon、TUI/Web；
- schema migration、embedded/detached migration、Git policy migration；
- 通用事务日志、强崩溃恢复和审计链；
- Core enforcement of Agent assignment；
- Windows/macOS 正式支持；
- 自动 Git commit、branch 存在性和代码快照；
- 固定 handoff/checkpoint 模板；
- 路径 alias、旧路径 symlink 和永久路径保证；
- 穷尽人工移动和手工损坏的边缘恢复。

## 扩展门槛

只有真实使用证明当前边界不足时才增加能力。任何扩展先回答：

- 它是否属于 Task，而不是宿主、Git、同步层或外部待办系统；
- 是否需要 Core 不变量，还是 Agent reference 足够；
- 是否会引入新的持久身份、权威状态或迁移责任；
- 如何在三个宿主保持一致降级；
- 能否用纵向场景和真实入口验证。

设计变更先进入本目录并登记 gap，完成实现、生成契约、测试和 runtime 文档后才视为交付。
