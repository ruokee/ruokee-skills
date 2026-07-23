# Context 与 WAL

Task 持久化工作对象，不持久化 Agent 的当前绑定。Context 由当前会话根据 Task 当前状态、普通材料、WAL 和代码现场重建；WAL 记录有持续价值的工作活动，但不是审计日志。

## 新会话与连续对话

每个新会话都从未绑定状态开始。系统不保存 current Task、active Task、最近 Run、session ownership 或 worktree binding。

用户显式给出 ID、名称、路径、目录名或 branch 时，Agent 解析唯一 Task。用户只说“继续”时，可以使用 cwd、当前 branch、worktree、Git 变更和 `task_find` 作为发现证据；多个合理候选必须确认。

同一会话中语义连续的后续消息可以自然延续已解析 Task，不需要机械重复 ID。这只是会话 Context，不写入持久状态；主题切换或指代歧义时重新解析。

## 恢复顺序

1. 解析 project 和当前绝对 cwd。
2. 使用显式引用直接 read，或通过 find 缩小候选。
3. 唯一解析后先读 `summary`。
4. 根据 `TASK.md` 当前事实、recent WAL、branch 和代码现场判断下一步。
5. 只有需要更早/完整历史时才使用 `detailed` 或增加 WAL 预算。
6. 根据正文中的入口读取普通材料，不预先遍历整个 Task 目录。

`metadata` 适合关系、状态和诊断检查；`summary` 是常规恢复入口；`detailed` 只在摘要不足时加载。Core 不为普通材料建立 inventory。

## `TASK.md` 与普通材料

`TASK.md` 正文描述当前真相：目标、范围、当前状态和重要材料入口。它不保存过程叙述。

计划、分析、研究、决策详情、handoff、checkpoint、输出和其他持续材料是 Task 目录下的普通文件。Task 不规定固定文件名或 schema；用户和 Agent根据实际工作组织，并从正文或 WAL 指向真正需要恢复的入口。

代码事实保留在代码仓库和 Git 中。Task 可以记录 branch、commit、worktree、dirty state 或关键文件引用，但不复制完整 diff 或源码作为备份。

## Assignment

assignment 是 runtime Context，不写入 Task，也不由 Core enforcement：

- 分配到 Task X 的 Agent 可以写 X 和全部后代 Task 数据；
- parent 和 sibling Task 数据只读；
- 分配到顶层 Task 的 Agent 可以写整棵 Task 树；
- 这项边界只约束 Task 数据，不限制正常 project 工作文件；
- 分配到 subtask 的 subagent 不写 parent WAL，parent Agent 观察结果后记录父级必要事实。

subagent 与 subtask 没有一一对应。一个 Agent 可以顺序处理多个 subtask，多个 subagent 也可以在同一顶层 Task 的不同工作面并行。

## WAL 定位

WAL 是 work activity log，回答“工作推进过程中发生了什么”。它不是 Task 当前状态的替代品，也不提供 hash chain、签名、不可篡改审计或事件重放。

文件按系统本地日期拆分：

```text
<task-dir>/wal/YYYY-MM-DD.md
```

规范条目：

```markdown
## 2026-07-21T15:04:05.123+08:00 · codex:gpt-5.6-sol

完成 Task 发现与引用解析的设计。

可选的多行补充正文。
```

只有严格 H2 header 被识别为条目。message 是非空单行摘要；extra body 可以自由换行；actor 不含换行或分隔符 ` · `。

## Core 与 Agent 的写入边界

Core 自动记录结构化机械事实：

- 创建；
- branch、关系和 extra 更新；
- lifecycle 与 archive；
- rename。

Agent 记录需要跨会话保留的工作活动：

- 一轮调研或分析形成的有持续价值结论，或被排除的方案；
- 用户确认、纠正或改变范围的决定及其影响；
- 可恢复的实现里程碑和验证结果；
- 外部工具、用户或其他 Agent 造成的重要现场变化；
- 已核实的 subagent 或 handoff 结果；
- 改变下一步的阻塞。

形成上述 durable event 后，Agent 在进入后续实现、验证、handoff、final response、下一个独立工作分支或下一个实质问题前立即调用 `task_log`。只合并同一语义事件内共同形成的事实；稍后才完成的实现里程碑或验证结果是新的事件，不能为了减少调用回并到旧记录。密度由语义事件决定，不使用固定分钟数、工具调用数或条目配额。

不记录每次读取、每条命令、临时计划、tool chatter、“仍在工作”状态或 Core 已自动写出的同一机械事实。参考日志密度只提供行为方向，不要求复制固定数量。

## 只追加与纠错

WAL 只追加。发现历史错误时追加更正，说明旧结论、修正依据和当前结论，不改写或删除旧条目。

用户可以手工编辑 WAL。无法解析的人工文本在 read 时产生 warning；只要目标是普通 UTF-8 文件且可写，Core 仍可在末尾追加规范条目。closed 或 archived Task 也可以补充后续事实。

## 读取预算

summary 返回每条 WAL 的 header 和正文第一段；detailed 返回完整条目。字符数与条目数是独立预算，Core 从最新条目向前选取，再按时间正序返回。

预算截断不是数据丢失。Agent 需要更旧历史时提高预算或直接读取 WAL 文件；不要为避免截断把整个 WAL 复制到 `TASK.md`。

## 状态提交与 WAL 失败

结构化状态先提交，自动 WAL 后追加。如果状态已成功写入、WAL 因文件异常失败，结果仍为 success，并带 `committed: true` warning。

调用方必须先重新读取状态，不能把该结果当作整体失败后重试，否则可能重复 lifecycle 或关系修改。修复 WAL 后只补充缺失活动记录；不回滚已经提交的正确状态。

## Handoff 与 Context 压缩

会话结束且工作未完成时，检查本轮是否还有尚未记录的完成内容、当前阻塞或决定和下一步，并只追加缺失现场。session-end 是补漏，不把已经及时记录的整轮历史重复压成唯一一条；如果它将成为本轮唯一记录，先检查调研/纠正、实现里程碑和验证结果之间是否漏掉了本应及时落盘的边界。细节超过一条有用日志时创建普通 handoff/checkpoint 文件，并从 `TASK.md` 或 WAL 指向它。

宿主能感知即将压缩时可以尽力写 checkpoint；不能感知不构成强制要求。恢复不依赖固定模板，而依赖当前事实、入口清楚的材料和足够解释现场的 WAL。
