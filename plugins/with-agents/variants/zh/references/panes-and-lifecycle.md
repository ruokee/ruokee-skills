# Pane、路由与生命周期

本参考文档涵盖 TARGET 解析、实时 pane 名称、with-agents 路由、per-pane 锁、`launch`/`wait`/`close` 生命周期，以及自目标作为唯一硬性禁止。输入阶段和部分结果属于 [operation-states.md](operation-states.md)；消息和回复流属于 [messaging.md](messaging.md)。

## 目录

- [所有命令使用同一 TARGET](#所有命令使用同一-target)
- [实时 pane 名称](#实时-pane-名称)
- [路由](#路由)
- [route、list 与 list --detail](#routelist-与-list---detail)
- [Pane 锁](#pane-锁)
- [启动](#启动)
- [等待](#等待)
- [关闭](#关闭)
- [自目标：唯一的硬性禁止](#自目标唯一的硬性禁止)
- [参考导航](#参考导航)

## 所有命令使用同一 TARGET

`read`、`wait`、`send`、`key`、`close` 和 `route TARGET` 共享同一 `TARGET` 语法。路由本身直接占据目标位置；没有 `--route` 标志。解析按固定顺序进行：

1. 任何以 `with-agents:` 开头的输入先被解析为路由——它永不会回退到原生 tmux 目标或裸名称分支，且解析失败的路由绝不回退到裸目标；
2. `%pane-id` 或显式的 `session:window.pane` 通过原生 tmux 目标处理解析；
3. 任何其他裸字符串仅匹配实时 tmux `window_name`——恰好一个匹配成功，零个匹配返回 `target_not_found`，多于一个返回 `target_ambiguous`。

匹配不到任何内容的裸未知名称**绝不**作为 tmux 活动 pane 重试。Pane ID 精确定位 pane；裸名称可能因同一窗口中的拆分 pane 共享名称而产生歧义。

裸名称、`%pane-id` 和 `session:window.pane` 是便利形式，针对当前命令的 tmux server 解析；只有 `with-agents:` 路由携带自己的 socket，跨 server 保持有效。当任何便利形式被渲染为路由时，控制器填入规范 socket。

## 实时 pane 名称

Pane 的公开 `name` 是其实时 tmux `window_name`，在每次命令时从 `#{window_name}` 新鲜读取。tmux 以 vis-escaped 形式输出该字段（例如字面反斜杠会加倍返回），因此控制器在显示值、匹配裸名称或生成路由前解码回真实名称；显示、裸名称查找和路由生成均使用同一解码值，因此你看到的名称就是可键入的名称。头部、路由和 `list`/`read` 均使用该值。用 `C-b ,`（或 `rename-window`）重命名窗口后，下一个命令自然报告新名称——pane 上没有存储第二个名称，且 `pane_title` 从不被视为名称。同一窗口中的拆分 pane 共享名称，因此 pane ID 携带精确位置，而裸名称可能解析歧义。

当窗口名称为空或包含无法放入单行头部的字符——Unicode `Cc` 控制字符，或 `Zl`/`Zp` 行/段落分隔符如 U+2028/U+2029 时，路由回退到 `pane-<decimal-pane-id>`，使头部保持恰好一行。

## 路由

按下面的 with-agents 文本语法解析路由；URI 解析不适用：

```text
with-agents:tmux?name=foo&pane_id=75&socket=/tmp/tmux-1000/default
```

字段顺序是固定的：`name`、`pane_id`、`socket`、可选的 `params`。`name`、`pane_id` 和 `socket` 均为必填——规范路由始终携带自身的绝对 socket，因此无论 caller 当前位于哪个 server，都能定位同一 pane。在传输中 pane ID 为十进制数字；控制器在调用 tmux 时添加 `%`。

`name` 和 `socket` 使用最小反斜杠转义——绝不使用 URL 百分号编码：

```text
\\  -> a literal backslash
\&  -> a literal &
\]  -> a literal ]
```

解析器仅将未转义的 `&` 视为字段分隔符，未转义的 `]` 视为头部终止符。缺少 `socket`、未知转义、重复字段、未知字段、非十进制 pane ID、非绝对 socket 或 CR/LF/NUL 均返回 `route_invalid`。`with-agents:` 输入一旦省略 `socket` 就直接判为非法，不按当前 server 解析——含 socket 的路由是唯一的路由形式。控制器从不对 `name` 或 `socket` 执行 `urllib.parse` URL 编码/解码。

路由连接到 `socket` 中的绝对路径。`name` 仅为提示：解析后，控制器通过 socket + pane ID 查找实时 pane，不会因名称已更改、pane 进程已 respawn 或 tmux server 在同一 socket 路径上重建而拒绝它。不存在的 pane 返回 `target_not_found`。

路由解析器还接受可选的 `params` 字段，因此接收 Agent 可以将消息头部中的路由直接粘贴到 `send TARGET`。解析器仅读取地址字段，从不传播旧的 params；没有隐式的回复行为。`route TARGET` 从其输出中剥离任何 `params`。

## route、list 与 list --detail

`route [TARGET]` 始终打印附带绝对 socket 的便携式路由：

```bash
"$wa" route cx-worker    # the target's portable, socket-qualified route
"$wa" route              # the caller's own route, derived from $TMUX/$TMUX_PANE
```

无参时从 `$TMUX`/`$TMUX_PANE` 推导 caller，无法推导时失败 `caller_identity_unavailable`。有参时通过 socket + pane ID 解析目标；仍在 `remain-on-exit` 下的 pane 会解析并打印其路由，只有不存在的 pane 返回 `target_not_found`。输入路由中的任何 `params` 会从输出中剥离。

`list`、`route` 和每个普通 pane 结果均返回同样的含规范化 socket 的完整路由——地址不会随 caller 的当前 socket 改变含义，因此你从一个结果中读取的路由从任何 server 重新传入后都保持有效。`list --detail` 添加紧凑结果省略的修复字段——server PID、pane PID 和死亡状态；它不改变路由。

## Pane 锁

per-pane advisory 锁（`flock`）串行化一个 pane 上的输入和生命周期操作：`send`、`key` 和 `close` 持有它，使它们的正文加按键序列不会穿插。控制器在操作后观察前释放锁，因此并发 send 全部排队，每个返回可能已包含后续 send 的最新快照。`lock_timeout` 和 `tmux_timeout` 限制控制器操作，防止故障后端挂起；Agent 任务截止时间不在本合同范围内。

`launch --split TARGET` 也会获取拆分**目标** pane 的锁，且仅在此之后运行 `split-window`，因此遵守同一 with-agents 锁的协作操作无法将新 pane 竞争到已移动的目标上（原生 tmux 绕过此锁，不在保护范围内）。非 split 的 launch 打开新窗口或新 session，不获取任何现有 pane 的锁。

## 启动

`launch` 创建一个 pane 并启动精确 argv（`--preset`/`--name-suffix` 命名规则参见 [presets.md](presets.md)）。任务文本绝不在 argv 中；控制器将其序列化给内部 helper，由其调用 `execvp`——无 shell 重解释。`--session` 和 `--split` 互斥。

`launch` 默认阻塞，直到有可读的启动画面返回；`--no-wait` 立即返回，`--ready-timeout SECONDS` 限制等待时间（默认 120）。等待过程在发送 argv 前保存基线，然后轮询：

1. 仍为空白或与基线无实质变化——继续等待；
2. 首次实质变化——进程已产生可观察的画面；
3. 短稳定窗口内无进一步变化——立即返回最新画面；
4. 超时前无实质变化——返回 `launch_timeout` 及最新快照；
5. 超时时仍在变化——返回标记为 `stable=false` 的最新画面。

稳定画面确认了一项可读的启动观察结果：启动画面、文件夹授权提示、登录提示或 composer。调用 Agent 根据该画面判断 composer 是否就绪，并决定发送 Enter、回答提示或继续等待。

`launch --preset PRESET` 是常规路径；`launch --name NAME -- ARGV...` 是一次性直接 argv 路径。命名规则因形式而异：未指定名称时 preset 从自己的 `pane_name` 或生成的 `<prefix>-NNNN` 自动命名；非 split 直接 argv 需要显式 `--name`，因为没有 preset 可回退；split launch 不拥有自身名称。`launch --split TARGET` 不创建窗口：新 pane 的公开名称就是目标窗口的实时 `window_name`，且控制器不重命名该窗口或保留 pane 别名。将 `--split` 与 `--name`/`--name-suffix` 结合使用会在 pane 创建前被拒绝。进程退出后 pane 以 `remain-on-exit` 保持存活，以便读取其最终画面。

## 等待

`wait --timeout SECONDS --interval SECONDS` 采样有界的画面捕获，直到画面首次变化、pane 的进程退出或消失，或直到超时到期。它观察可见画面以及 pane 是否仍然存活。`--interval` 设置采样周期；`--timeout` 限制本次观察窗口。超时时阶段为 `unchanged`（其他阶段为 `changed`、`process_exit`）。装饰性重绘也可算作变化。保持正在工作、等待或自动重试的 Agent 存活；不要设置任意的总任务重试上限，也不要因为短暂静默、速率限制或瞬态上游错误就杀死或重复启动 Agent。

## 关闭

`close` 在 pane 锁下捕获最终画面，然后关闭它解析到的非自身 pane。如果 `kill-pane` 本身失败，报告阶段 `close_state_unknown`——pane 可能已经消失，因此不要重试；解析并读取它。任何唯一解析的非自身 pane 都可以关闭，因此仅在外层任务完成、用户要求或进程在范围内无法恢复时才关闭 pane。未经明确指示绝不要关闭用户预先存在的 pane，也绝不要使用宽泛的 `kill-server`/`kill-session`/`kill-window` 作为 shortcut。

## 自目标：唯一的硬性禁止

任何唯一解析的非自身 pane 都接受 `send`/`key`/`close`。所有 CLI 的工作方式相同——显式 `send` 到普通 shell pane 会键入文本并按下 Enter，可能运行一条命令，因此先读取目标。

唯一的例外是自目标，通过规范化 socket + pane ID 判断。`list`、`read` 和 `route` 可以自由观察 caller；变更操作 `send`/`key`/`close` 拒绝驱动 caller 自身的 pane。当无法证明同一 `%id` 的目标位于不同 server 时，破坏性操作保守拒绝；被证明位于另一 server 的目标则允许。

## 参考导航

- [cli.md](cli.md) — 命令索引、全局选项、JSON 信封和代表性错误码。
- [messaging.md](messaging.md) — 携带路由、params 和回复的发送头部语法。
- [operation-states.md](operation-states.md) — 发送输入阶段、生命周期 state-unknown 结果和禁止盲重放规则。
- [presets.md](presets.md) — preset schema、pane 命名和私有 Agent 注册表。
- [adapters.md](adapters.md) — 各 CLI 的清输入和开始新对话差异。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成操作时的原生 tmux 恢复。
