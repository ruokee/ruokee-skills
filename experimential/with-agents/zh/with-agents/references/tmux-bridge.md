# tmux-bridge 参考

本文根据 smux 的 [`tmux-bridge.md`](https://github.com/ShawnPana/smux/blob/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f/skills/smux/references/tmux-bridge.md) 参考文件改编，供 `with-agents` 使用。上游版本为 `70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f`，依据 MIT License 发布。参见[许可证](#许可证)。

## 目录

- [范围与兼容性](#范围与兼容性)
- [附带脚本与环境](#附带脚本与环境)
- [原子命令与读取保护](#原子命令与读取保护)
- [命令参考](#命令参考)
- [目标解析](#目标解析)
- [消息约定](#消息约定)
- [接收与回复](#接收与回复)
- [读取-操作-读取循环](#读取-操作-读取循环)
- [Agent 间工作流](#agent-间工作流)
- [等待与生命周期语义](#等待与生命周期语义)
- [操作提示](#操作提示)
- [许可证](#许可证)

## 范围与兼容性

当用户请求 `tmux-bridge`、已有工作流已经使用它，或它强制执行的读取保护和 pane 标签有用时，使用该命令。存在已安装命令时，先检查它：

```bash
command -v tmux-bridge
tmux-bridge --help
```

本 Skill 还附带一个相对于已安装 Skill 根目录的改编可执行文件 `scripts/tmux-bridge`。没有已安装的命令时，可以直接运行它。将其安装到 `PATH`、覆盖已有可执行文件或修改 shell 配置，都需要用户明确授权；遵循 [tmux-setup.md](tmux-setup.md)。根据所选可执行文件的 `--help` 确认实际语法。如果没有可用的 bridge 且用户没有明确要求使用它，则使用原生 tmux，并阅读 [tmux.md](tmux.md)。

当发送方和接收方都是支持 bridge 的 Agent pane 时，bridge relay 约定效果最好。当调用方在 tmux 外部、目标不支持 bridge，或回复没有返回调用方 pane 时，以适中的间隔读取目标 pane。

## 附带脚本与环境

附带脚本源自上方固定修订版中的 smux `tmux-bridge` 2.0.0，并将自身标识为 `2.0.0-with-agents.1`。本地改动包括：

- 让生成的消息提示接收方加载 `with-agents` Skill；
- 按用户、tmux socket 和 pane 身份为读取保护文件设置命名空间；
- 当 pane 被重新生成或复用时，使读取保护失效；
- 要求可选的 `read` 行数为正整数；
- 在 `doctor` 中正确报告空标签数量。

该命令会读取以下可选环境变量：

| 变量 | 用途 |
| --- | --- |
| `TMUX_BRIDGE_SOCKET` | 选择一个具有 `tmux -L` 语义的 tmux socket |
| `TMUX_BRIDGE_RUNTIME_DIR` | 覆盖用于读取保护文件的私有目录 |

未设置 `TMUX_BRIDGE_RUNTIME_DIR` 时，保护文件位于当前用户拥有、权限为 `0700` 的 `tmux-bridge-<uid>` 目录中；该目录位于 `XDG_RUNTIME_DIR`、`TMPDIR` 或 `/tmp` 下。保护记录当前 pane ID、PID、session ID 和 window ID。身份发生变化后，必须再次 `read` 才能交互。

## 原子命令与读取保护

`tmux-bridge` 暴露原子操作：

- `type`：输入不带 Enter 的字面文本；
- `keys`：发送特殊按键；
- `read`：捕获 pane 内容。

它有意不提供复合发送操作。保留这种分离，以便在提交前验证输入。

CLI 强制执行先读后操作：

1. `tmux-bridge read <target>` 将 pane 标记为已读取。
2. `tmux-bridge type <target> ...` 或 `tmux-bridge keys <target> ...` 要求存在该标记。
3. 每次成功的 `type` 或 `keys` 操作都会清除该标记。
4. 下一次操作前再次读取。

跳过读取时应像这样失败：

```text
$ tmux-bridge type cc-review "hello"
error: must read the pane before interacting. Run: tmux-bridge read cc-review
```

## 命令参考

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `tmux-bridge list` | 显示带有 target、进程、大小和标签的 pane | `tmux-bridge list` |
| `tmux-bridge read <target> [lines]` | 读取最近的输出；上游默认读取 50 行 | `tmux-bridge read cc-review 100` |
| `tmux-bridge type <target> <text>` | 输入不带 Enter 的字面文本 | `tmux-bridge type cc-review "hello"` |
| `tmux-bridge message <target> <text>` | 输入不带 Enter 的带框 Agent 消息 | `tmux-bridge message cc-review "Review this change"` |
| `tmux-bridge keys <target> <key>...` | 发送特殊按键 | `tmux-bridge keys cc-review Enter` |
| `tmux-bridge name <target> <label>` | 为 pane 设置标签 | `tmux-bridge name %3 cc-review` |
| `tmux-bridge resolve <label>` | 将标签解析为原生 pane target | `tmux-bridge resolve cc-review` |
| `tmux-bridge id` | 打印当前 pane ID | `tmux-bridge id` |
| `tmux-bridge doctor` | 检查 tmux、服务器、pane 和 bridge 状态 | `tmux-bridge doctor` |
| `tmux-bridge version` | 打印可执行文件版本 | `tmux-bridge version` |

将此表视为所导入版本的接口。版本不同时，优先使用本地 `--help`。

## 目标解析

可以使用以下任一形式：

- 原生 tmux target，例如 `shared:0.1` 或 `%3`；
- 之前通过 `tmux-bridge name` 分配的标签。

对于刚刚由 `with-agents` 创建的 pane，为其分配所选名称作为标签：

```bash
tmux-bridge name "$caller_target" cx-lead
tmux-bridge name "$target" cc-review
tmux-bridge resolve cc-review
```

由 `with-agents` 创建的每个 pane 都使用匹配 `^[a-z]{2}-[a-z]{1,6}$` 的唯一标签。两字母前缀标识 Agent CLI：Claude Code 使用 `cc`，Codex 使用 `cx`，Pi 使用 `pi`。后缀是一个长度不超过六个字母的小写单词。除非用户明确请求，否则不要重命名复用或预先存在的 pane。

依赖标签操作前，先读取解析后的 target。pane 退出或复用后，标签仍可能只是过期的发现提示。

## 消息约定

bridge 的 `type` 命令会原样输入收到的文本。使用发送方地址包装 Agent 消息：

```text
[tmux-bridge from:cx-lead] Please review src/auth.ts
```

该地址告诉接收方 Agent 回复位置。不要虚构标签或 pane ID；从 `tmux-bridge id`、`tmux-bridge list` 或用户明确指定的 target 中取得它。

当调用方在 tmux 内部运行时，`message` 会自动生成该包装，并添加提示，让接收方在回复前加载 `with-agents`：

```bash
tmux-bridge read cc-review 20
tmux-bridge message cc-review 'Please review src/auth.ts'
tmux-bridge read cc-review 20
tmux-bridge keys cc-review Enter
```

当调用方在 tmux 外部运行，或需要不同的明确发送方地址时，使用下面的手动 `type` 形式。

原子地发送包装后的请求：

```bash
tmux-bridge read cc-review 20
tmux-bridge type cc-review \
  '[tmux-bridge from:cx-lead] Please review src/auth.ts'
tmux-bridge read cc-review 20
tmux-bridge keys cc-review Enter
```

## 接收与回复

当提示包含 `[tmux-bridge from:<sender>]` 时，通过 bridge 向 `<sender>` 发送回复。只在当前 pane 中输入回复不会到达发送方：

```bash
tmux-bridge read <sender> 20
tmux-bridge type <sender> \
  '[tmux-bridge from:cc-review] Review complete; one issue remains.'
tmux-bridge read <sender> 20
tmux-bridge keys <sender> Enter
```

在 `type` 和 `keys` 之前都要读取；每个操作都会消耗读取保护标记。

## 读取-操作-读取循环

使用以下完整顺序：

1. 读取 target，确认身份、状态和输入字段。
2. 输入不带 Enter 的消息。
3. 再次读取，以验证待输入文本并恢复读取保护标记。
4. 单独发送 Enter。
5. 在需要结果且不会有回复转发到调用方 pane 时，稍后读取。

示例：

```bash
tmux-bridge read cc-review 20
tmux-bridge type cc-review \
  '[tmux-bridge from:cx-lead] Run the focused tests and report failures.'
tmux-bridge read cc-review 20
tmux-bridge keys cc-review Enter
```

对于需要回复的非 Agent pane：

```bash
tmux-bridge read cc-review 10
tmux-bridge type cc-review "y"
tmux-bridge read cc-review 10
tmux-bridge keys cc-review Enter
tmux-bridge read cc-review 20
```

## Agent 间工作流

当调用方在 tmux 内部运行时，保留其既有地址：

```bash
caller="$(tmux-bridge id)"
tmux-bridge list
```

如果调用方由 `with-agents` 创建，则使用创建时分配的合规标签。否则保留其原生 pane ID；不要仅为让回复地址更美观而重命名预先存在的调用方。`message` 命令会在当前调用方存在 `@name` 标签时自动使用它，否则回退到其 pane ID。

发现并检查目标：

```bash
tmux-bridge list
tmux-bridge read cc-review 20
```

带回复地址发送请求：

```bash
tmux-bridge message cc-review \
  'Continue the task and report any blocker.'
tmux-bridge read cc-review 20
tmux-bridge keys cc-review Enter
```

如果接收方 Agent 支持 bridge，则让它回复到调用方 pane。否则以适中的间隔捕获其 pane。两种模式下都不要忙等循环。

## 等待与生命周期语义

上游参考说无需等待或轮询，因为它假设另一个 Agent 会直接回复到发送方 pane。应将这句话严格解释为 relay 优化，而不是放弃 Agent 或关闭其 pane 的许可。

应用 `SKILL.md` 中的生命周期规则：

- 保持正在执行、等待和自动重试的 Agent 存活，不设置固定超时；
- 回复反馈、澄清、授权和 goal 阻塞；
- 当直接回复不可用或结果成为必要时，以适中的间隔观察；
- 在外层用户任务或 goal 完全结束前，保留已创建的 pane 以便后续工作；
- 仅在完全完成、用户明确终止或授权范围内无法恢复的条件下结束。

## 操作提示

- 每次 `type` 和 `keys` 操作前都要读取；每个操作完成后都会消耗读取保护。
- 使用标签提高可读性，但交互前要验证解析出的 pane。
- 保持文本与 Enter 分离。
- 使用 bridge `type` 输入字面单行文本。
- 当调用方有 tmux pane ID 时，使用 bridge `message` 输入带框的单行 Agent 请求。
- 对于安全的多行输入，解析出原生 target，并遵循 [tmux.md](tmux.md) 中的 bracketed-paste 流程，除非已安装的 bridge 文档说明了等价支持。
- 读取非 Agent pane 来收集输出，因为它们不会发送带地址的回复。
- 不要随意混用原生 tmux 和 bridge；原生命令会绕过 bridge 的读取保护。

## 许可证

MIT License

Copyright (c) 2026 shawn pana

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
