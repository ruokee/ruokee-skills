# Agent 契约

Task 向 Agent 暴露五个高频、互不重叠的语义操作。完整输入结构由 `core/src/task_core/contracts.py` 定义，并生成到 `package/contracts/task-tools.schema.json`；本文只维护跨字段语义、操作边界和调用方责任。

## 共同约定

每个请求都应携带当前 workspace 的绝对 `cwd`。package/MCP 进程从 plugin 目录启动，因此进程 cwd 不是 project context。切换 worktree 或目录后重新解析 cwd。

成功结果：

```json
{
  "ok": true,
  "data": {},
  "warnings": []
}
```

领域失败：

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

`task-core invoke` 只在 transport/process 失败时返回非零退出码。调用方不能把 `ok: false` 依赖为 shell failure，也不能把带 `committed: true` warning 的成功结果自动重试。

## Task 引用

唯一 Task 操作接受完整 UUIDv7、绝对路径、相对 project root 的明确路径、精确名称或精确目录名。不支持 UUID 前缀。

`task_find.query` 是搜索入口，可以按 exact、prefix、substring 返回候选；`task_read`、update、log 和低频 CLI 需要唯一精确解析。歧义时 Core 返回候选，Agent 向用户确认。

branch 使用独立精确参数，不混入通用 query 的模糊匹配。

## Actor

修改和 WAL 操作可以携带 actor，推荐形式：

- `codex:<model>`；
- `claude:<model>`；
- `pi:<model>`；
- `codex:<subagent-name>:<model>`。

actor 的解析顺序是显式参数、adapter/环境上下文、`<host>:unknown`。actor 只帮助理解工作现场，不用于认证、授权或 assignment enforcement；不得包含换行或分隔符 ` · `。

## `task_find`

`task_find` 搜索已有 Task，不加载完整正文和 WAL。

主要语义：

- `query` 匹配 UUID、名称、目录名或路径；空 query 列出候选；
- `branch` 是大小写敏感的精确过滤；
- status、archive 与其他条件使用 AND；
- 默认包含 open、paused、closed，但排除 archived；
- 文本 query 使用 Unicode casefold，按 exact、prefix、substring 排序；
- 返回完整 ID、名称、状态、archive、绝对 `task_dir`、parent、branch、匹配证据和整体截断状态。

普通搜索不会穿透 closed parent；完整 UUID 或明确路径可以定位其后代。无效 candidate 不作为正常结果，但可以作为 warning 返回。

## `task_read`

`task_read` 读取一个唯一 Task：

- `metadata`：managed metadata、绝对路径、topology、关系和 warnings；
- `summary`：metadata、正文、每条 WAL 的 header 和第一段；
- `detailed`：metadata、正文和完整 WAL 条目。

Core 不返回普通材料清单，只返回 `task_dir`。Agent 按需使用宿主文件工具读取 Task 目录。

WAL 同时受字符数与条目数预算约束。默认来自合并配置；显式 `null` 只对请求中的条目预算表示不限制，`0` 表示不返回。Core 从最新条目向前选择，最终按时间正序返回；最新单条超限时可以截断并标记。

显式按路径读取非法 candidate 时返回 `managed_valid: false`、错误、可读取的 metadata/body，而不是把目录完全隐藏。非法 Task 不提供合法 topology，也不能修改或写 WAL。

## `task_create`

`task_create` 使用 tagged union 区分一个顶层 Task 和同一 parent 下的一批 subtasks。

顶层创建：

- `strict` project 要求当前用户明确确认，并由请求携带 `user_confirmed: true`；
- `permissive` project 可以由 Agent 为明显持续、多阶段或跨会话工作创建；
- 未初始化 project 返回错误，create 不隐式 init。

subtask 创建：

- parent 必须能唯一解析且为 open 或 paused；
- 一批包含 1..50 个 sibling；
- 正常校验错误路径下全有或全无；
- batch 内不能引用尚未创建的 sibling；
- parent 追加批量创建摘要，每个 child 写自己的创建 WAL。

Core 生成 schema version、UUIDv7、open 状态、`archived: false`、目录和时间。普通创建省略 `created_at`；只有迁移历史 Task 且原始带时区 instant 可靠时才显式传入。显式时间控制 managed `created_at`、UUIDv7 和顶层日期分区，创建 WAL 仍使用实际迁移时间。

## `task_update`

`task_update` 使用领域 patch，不是通用 JSON Merge Patch。一次请求可以组合：

- branch 设值或删除；
- `depends_on` add/remove delta；
- `related_to` add/remove delta；
- shallow `extra` set/remove；
- 最多一个 lifecycle action。

lifecycle action 包括状态 transition、archive 或 unarchive。所有 transition 要 reason；force 只允许 close；unarchive 还要求当前用户确认。

Core 在锁内基于最新状态应用 delta，校验关系目标、self relation、依赖环和 close 条件。无实际变化时返回 `changed: false` 且不写 WAL。

update 不修改 name、正文、parent 或普通材料。name 走 rename CLI；正文和普通材料由宿主文件工具维护。

## `task_log`

`task_log` 一次追加一条活动记录，接收唯一 Task、非空单行 message、可选多行 extra body 和 actor。

它用于有持续价值的工作活动，不用于每次命令或临时 todo。closed/archived Task 仍可补充事实；managed fields 非法时不允许写 WAL。

完整语义见 [Context 与 WAL](context-and-wal.md) 和 runtime [WAL reference](../package/skills/task/references/wal.md)。

## 低频 CLI

以下操作不占用高频 tool schema：

- init：选择 project、storage 和 Git policy；
- check：汇总 Task candidate、重复 UUID、staging 和发现 warning；
- rename：扫描 project 引用、dry-run、授权后写入；
- version：核对模块、protocol 和 data schema。

调用 Agent 根据 Skill 的条件路由加载对应 reference，不从本文推断尚未发布的参数。

## 错误分类

完整错误码来自实现，不在文档中手写同步。维护者按调用方动作关注以下类别：

- project/config/storage 不能解析；
- Task 不存在、歧义或跨 project；
- managed fields / YAML / WAL 非法；
- 关系或 lifecycle 不变量阻止修改；
- 用户确认或 unresolved rename 授权缺失；
- 外部写竞态、锁目标变化或部分提交 warning。

只有当不同类别需要 Agent 采取不同动作时，runtime 文档才引用具体 code。
