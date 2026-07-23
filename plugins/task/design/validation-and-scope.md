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
cd plugins/task/core
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
9. 默认 create 与显式空关系 create 都使用稀疏 frontmatter；读取时补足 false 和空列表，旧显式默认文件继续合法。
10. 关系从零到一创建字段、从一到零删除字段；archive 写 true、unarchive 删除字段，无关 update 保留旧显式默认节点。
11. Pi 未传 actor 时使用运行时 `model.id`，显式 actor 保持优先；Codex/Claude 缺少模型信息时仍能降级为 host unknown。
12. Skill forward-test 在调研结论、用户纠正、实现里程碑、验证结果和阻塞等 durable event 后观察到即时 WAL，且没有命令流水、重复机械 mutation 或把整轮历史压成唯一 session-end 记录。

Core 源码测试直接覆盖 1–10；adapter、真实宿主和 Agent 行为证据按下节追踪。

## Implementation gaps

以下是当前已知差距，不应在 runtime Skill 或 references 中写成已经交付：

1. `tests/test_binary_smoke.py` 只有显式选择 `TASK_CORE_BINARY` 才执行；普通源码 pytest 的绿色结果不能替代每次发布对实际 standalone 产物的单独 smoke。
2. Pi adapter 尚无自动 host smoke 基础设施；当前验证由直接执行 extension 和隔离 package 安装/RPC 启动两部分组成，发布时仍需保留这项手工检查。
3. 当前用户环境中的 Claude 与 Codex 插件在审查前不自动重装；隔离 HOME 的 marketplace 安装和缓存入口检查可以验证 package，但不能替代审查后对真实已安装宿主的刷新与新会话验证。
4. 当前 `task-core check` 只检查 duplicate UUID、invalid candidates、staging 和发现 warning。通用 repair、默认字段迁移或批量清理明确不进入稳定能力。

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
- 显式默认字段清理 migration、repair 或普通 mutation 顺手规范化；
- 通用事务日志、强崩溃恢复和审计链；
- WAL 计时器、每次 tool-call hook、固定条目数量和 Core 自动自然语言活动日志；
- actor 置信度、推定标记、宿主私有 session 解析和模型目录校验；
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
