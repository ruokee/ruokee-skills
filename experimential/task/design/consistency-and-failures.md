# 一致性与失败边界

Task 面向个人 Linux 环境和本机多 Agent 并发。Core 保证单个领域操作的确定性校验、锁内重解析和原子文件替换，但不承诺分布式一致性、通用事务恢复或外部编辑器协作锁。

## 锁域

MVP 使用目录 inode 上的 `flock`，不创建持久锁文件：

- project 级操作锁 project root；
- detached registry 额外锁 registry 所在目录；
- Task 树操作锁 top-level Task 目录，所有后代共享这把锁；
- 不同 top-level Task 可以并行修改；
- project-wide rename 获取 project lock 和全部 top Task locks，并按稳定顺序获取。

project lock 保护顶层目录槽位分配和 project-wide 操作；top Task lock 保护同一 Task 树中的状态、关系和 WAL。

## 写入协议

每个写操作遵循：

1. 解析 project 和目标；
2. 完成无需锁的初步校验；
3. 获取适当锁；
4. 在锁内重新解析并重新校验；
5. 基于最新状态应用变更；
6. 使用同目录 staging 和 atomic replace 写文件；
7. 追加必要 WAL；
8. 返回 committed 状态和 warning。

调用方不传 revision/etag。关系使用 add/remove delta，使 Core 能在锁内合并最新列表，避免基于旧 read 覆盖并行写入。

## 原子性范围

单个 frontmatter 或 WAL 文件使用 atomic replace。批量 subtask 创建先在同一 partition staging，正常校验错误路径下全有或全无。

单个领域操作不等于跨文件事务：

- Task 状态与自动 WAL 不是一个 crash-safe transaction；
- project-wide rename 涉及多个文件和路径，不建立通用 journal；
- 强杀、断电、磁盘错误或异常 OS failure 仍可能留下 staging 或部分现场。

系统不实现通用事务日志、恢复状态机或跨独立 Task 的多对象事务。诊断负责发现可见异常，用户和 Agent 根据现场决定恢复。

## 状态先于自动 WAL

Core 先提交结构化状态，再尝试自动 WAL。WAL 失败时返回 success、`committed: true` 和 warning。

这一顺序避免无法追加活动日志时丢失已校验的领域变更，但要求调用方不要自动重试整个操作。正确恢复方式是重新 read，确认状态，再修复或补充 WAL。

## 外部写竞态

用户编辑器和其他不使用 Core 的进程不会遵守 locks。Core 在写入前比较能够观察到的目标 bytes/stat；发生变化时返回 `external_write_race`，避免用旧状态覆盖可见外部编辑。

该机制不能捕获所有人工竞态，也不提供 merge。Agent 重新读取最新文件，理解双方变化后再决定是否重试或请求用户处理。

锁目标在获取前消失或改变时返回显式失败。目录 symlink 不参与 Task 发现，WAL 目标必须是普通文件，避免通过链接写到意外位置。

## 人工编辑与损坏

文件是事实来源，因此人工编辑是支持的，但不等于所有文本都可安全自动修复：

- unknown frontmatter fields 透明保留；
- managed fields 类型或 schema 非法时 Task 可读但不可修改；
- 重复 YAML key、不安全 tag 和无法可靠解析的 frontmatter 不覆盖；
- name/slug 或非规范路径产生 warning，通常不阻止普通操作；
- duplicate UUID、跨 project 路径和身份歧义阻止修改；
- WAL 非 UTF-8、symlink 或非普通文件时拒绝追加。

## `task-core check`

当前 check 汇总：

- project 与 Task root；
- Task candidate 数量；
- invalid candidates；
- duplicate UUID；
- 残留 staging 文件；
- 发现过程中产生的 path/name warnings。

它不自动 repair，不是 schema migration，也不承诺枚举所有关系或 WAL 语义异常。read 某个 Task 时才能得到 topology、缺失关系和 WAL parsing warnings。

完整 runtime 处理顺序见 [diagnostics reference](../package/skills/task/references/diagnostics-and-repair.md)。更强诊断能力属于 [implementation gaps](validation-and-scope.md#implementation-gaps)。

## 调用方失败处理

Agent 根据失败性质行动：

- 不存在/歧义：收集候选或向用户确认；
- 未初始化/配置冲突：加载 project setup，先决定 storage 与 policy；
- 关系/lifecycle blocked：展示违反的不变量，不绕过；
- 需要显式授权：只在当前用户确认后传 confirmation/force/unresolved flag；
- managed data 非法：停止写入，保存现场，诊断最小修复；
- external race：重新读取，不用旧请求盲重试；
- committed warning：确认状态，只补缺失 WAL；
- process/transport failure：先判断是否提交过，再决定恢复。

## 不承诺

MVP 不保证：

- 分布式锁和多设备冲突解决；
- 外部编辑器事务；
- 跨平台 locking；
- crash-safe 多文件事务；
- 自动回滚或 repair；
- 不可篡改审计；
- 穷尽手工改坏文件的恢复。
