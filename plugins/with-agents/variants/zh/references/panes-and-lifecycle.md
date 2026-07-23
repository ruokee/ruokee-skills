# Pane、身份与生命周期

本参考文档涵盖 pane 身份、caller 作用域的观察凭据、所有权、foreign/self-target 规则、per-pane 和 per-request 锁、`create`/`launch`/`wait`/`restart`/`close` 生命周期，以及运行时状态及其垃圾回收。输入阶段和部分结果属于 [operation-states.md](operation-states.md)；消息和事件流属于 [messaging.md](messaging.md)。

## 目录

- [目标与身份](#目标与身份)
- [观察凭据](#观察凭据)
- [所有权与 foreign pane](#所有权与-foreign-pane)
- [锁](#锁)
- [创建、启动与重启](#创建启动与重启)
- [等待](#等待)
- [关闭](#关闭)
- [运行时状态与垃圾回收](#运行时状态与垃圾回收)

## 目标与身份

目标可以是精确的 `%pane-id`、原生 `session:window.pane`、唯一的 `@with_agents_name` 或 owned `run_id`。名称仅是发现辅助。控制器将每个操作绑定到元组 `socket_path + server_pid + pane_id + pane_pid`，owned pane 还包括 `run_id`。有歧义的名称会被拒绝而非猜测（`target_ambiguous`）；解析不到任何目标时为 `target_not_found`。

Owned pane 携带简短的非机密 tmux 选项：`@with_agents_owner`、`@with_agents_run_id`、`@with_agents_name`、`@with_agents_preset`。精确的 argv 和观察/request 状态位于私有的运行时根目录中，绝不在 pane 选项中。

## 观察凭据

`read`、`wait`、`create`、`launch` 和成功的 `restart` 记录观察凭据。`send`、`request` 和 `key` 消费一个凭据；写入 foreign pane 还需要 `--allow-foreign`。凭据由 caller 和 target 共同键控：

- tmux caller 贡献其自身的 server、pane、pane PID 和 owned run ID；
- tmux 外的并发独立控制器应传递不同且稳定的 `--caller-id` 值；默认值在同一 OS 用户内共享；
- 无法解析的 tmux caller 会以 `caller_identity_unavailable` 失败，而非伪造未验证的凭据。

观察凭据是操作互锁，而非 TUI 空闲的证明——它仅证明此 caller 最近见过同一 pane 身份。普通画面输出变化不使其失效。socket 路径、server PID、pane ID 或 pane PID（或 owned `run_id`）的变化会使凭据失效：下一个消费命令失败并返回 `observation_expired`，缺失凭据则返回 `observation_required`。如果在捕获和重新解析之间 pane 身份发生变化，`read` 本身会以 `target_identity_changed` 失败。

## 所有权与 foreign pane

已有 pane 属于 foreign。`list` 和 `read` 为只读操作，始终允许。`send`、`request` 和 `key` 需要当前观察凭据加 `--allow-foreign` 才能操作非 owned pane（否则 `foreign_write_denied`）。`restart` 和 `close` 需要所有权，除非显式使用 `--force-foreign`（否则 `foreign_restart_denied` / `foreign_close_denied`）。控制器拒绝修改 caller 自身 pane，即使带 `--allow-foreign`（`self_target_denied`）；如果无法证明相同 ID 的目标是不同 pane，则失败 `self_target_unverified`。已退出的目标进程失败 `target_process_exited`。

## 锁

两把内核 advisory 锁（`flock`）串行化并发控制器：

- per-pane 锁守卫输入和生命周期：`send`、`request` 分发、`key`、`restart`、`close` 和每次通知尝试均持有它，因此它们无法在一个 pane 上交错执行。
- per-request 锁守卫事件分配和 request 状态。其锁文件位于 request 目录之外（`runtime/locks` 下），因此 `reply`、`inbox` 和 `gc` 在同一 inode 上同步，即使 GC 移除了 ticket。

锁顺序是单向的：需要两把锁的路径先完成并释放 request 锁，然后获取 pane 锁；两者从不嵌套。锁获取和每个 tmux 子进程都有有限的操作超时（`lock_timeout`、`tmux_timeout`），用于防止故障后端挂起——它们不是 Agent 任务超时。

## 创建、启动与重启

`create` 创建一个 owned shell pane 并记录观察：

```bash
"$wa" create --name scratch --cwd "$PWD"
"$wa" create --name sidecar --split %3 --cwd "$PWD"
```

`launch` 创建一个 owned pane 并启动精确 argv（`--preset`/`--name-suffix` 命名规则参见 [presets.md](presets.md)）。任务文本绝不在 argv 中；控制器将其序列化给内部 helper，由其调用 `execvp`——没有 `eval`，没有 shell 重解释。`--session` 和 `--split` 互斥（`layout_source_conflict`）。当无法解析 caller session 时，如果只有一个现有 session 则复用；多个 session 需要 `--session` 或 `--split`；没有 session 则创建最小的 detached `with-agents` session。

启动结果返回实际 argv、状态记录路径、初始画面和 `readiness` 评估（通用 adapter 或无法识别的 composer 为 `unknown`）。失败的启动以 `remain-on-exit` 保持 pane 存活，以便读取其最终画面并在原地修正：

```bash
"$wa" restart reviewer -- agent-cli --corrected-option
"$wa" restart reviewer --preset corrected-preset
```

`restart` 杀死当前进程并分配新的 `run_id`，使绑定到该 pane 的旧观察凭据失效。它在替换进程之前轮换身份，因此部分 restart 仍会使所有权或观察检查失败关闭。通知路由身份有意识地更窄（仅规范 socket + server PID + pane ID），因此同一 server 上同一 pane 内的 restart 本身不会使后续 callback 失去资格——回调时的当前前台 Agent 检查决定其资格（参见 [adapters.md](adapters.md)）。有关 `restart_state_unknown` 和进程退出结果，参见 [operation-states.md](operation-states.md)。

## 等待

`wait --timeout SECONDS --interval SECONDS` 每 `--interval` 秒采样一次有界的画面捕获和进程身份，直到首次变化、进程退出或身份替换，或直到 `--timeout` 截止时间到期。`--interval` 仅为采样周期，不是截止时间；超时到期时结果阶段为 `unchanged`（其他阶段为 `changed`、`process_exit`、`identity_changed`）。装饰性重绘也可算作变化。它会记录新的观察凭据，但不定义任务完成，也不应被包装在任意的总任务重试上限中。保持正在工作、等待或自动重试的 Agent 存活；不要因为短暂静默、速率限制或瞬态上游错误就杀死或重复启动 Agent。

## 关闭

`close` 捕获最终画面，然后杀死 owned pane 并清除其运行时记录。仅在外层任务完成、用户要求或进程在范围内无法恢复时才关闭 pane。未经明确指示绝不要关闭用户预先存在的 pane。宽泛的 tmux 杀死操作（`kill-server`、`kill-session`、`kill-window`）从不是恢复的 shortcut。

## 运行时状态与垃圾回收

运行时根目录为 `${XDG_RUNTIME_DIR}/with-agents/`（mode `0700` 目录、mode `0600` 文件），包含 owned 启动记录、观察凭据、锁、request、事件、通知和受管结果。它从不存储完整的任务 prompt 或终端 transcript。删除运行时目录——登出时清除它，或重启——会使在途 ticket 失效。缺少 `XDG_RUNTIME_DIR`（典型如 macOS）时，状态回退到 `${XDG_STATE_HOME:-~/.local/state}/with-agents/`，这将使用寿命从 session 临时状态变为持久用户状态；在回退模式下，控制器自动删除超过七天的已终结 request，从不按年龄自动删除 pending 的 request。

`gc` 立即删除已终结的 request（带有终结事件的 v2 流、已回复的 v1 ticket 或分发中止的 request）。`gc --stale [DAYS]` 报告超过指定年龄的 pending request（默认 30 天），仅在添加 `--delete-stale` 时删除它们（`--delete-stale` 需要 `--stale`）。Pending 流——无事件、只有非终结事件或 TTL 已过期——从不自动删除；仅在显式请求时报告和移除。

`WITH_AGENTS_RUNTIME_DIR` 和 `WITH_AGENTS_CONFIG_DIR`（或 `--runtime-dir` / `--config-dir`）覆盖根目录用于隔离测试。不要将其指向共享或不受信任的目录。
