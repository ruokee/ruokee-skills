# tmux-bridge 参考

本文根据 smux 的 [`tmux-bridge.md`](https://github.com/ShawnPana/smux/blob/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f/skills/smux/references/tmux-bridge.md) 参考文件改编，供 `with-agents` 使用。上游版本为 `70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f`，依据 MIT License 发布。参见[许可证](#许可证)。

## 目录

- [范围与兼容性](#范围与兼容性)
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

仅在以下情况使用 `tmux-bridge`：命令已安装且用户请求使用它；已有工作流已经使用它；或它强制执行的读取保护和 pane 标签有用：

```bash
command -v tmux-bridge
tmux-bridge --help
```

本 Skill 仅包含参考文件，不包含 `tmux-bridge` 可执行文件或安装程序。以本地安装版本为准确认实际语法。当命令不可用且用户没有明确要求使用它时，使用原生 tmux，并阅读 [tmux.md](tmux.md)。

当发送方和接收方都是支持 bridge 的 Agent pane 时，bridge relay 约定效果最好。当调用方在 tmux 外部、目标不支持 bridge，或回复没有返回调用方 pane 时，以适中的间隔读取目标 pane。

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
$ tmux-bridge type codex "hello"
error: must read the pane before interacting. Run: tmux-bridge read codex
```

## 命令参考

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `tmux-bridge list` | 显示带有 target、进程、大小和标签的 pane | `tmux-bridge list` |
| `tmux-bridge read <target> [lines]` | 读取最近的输出；上游默认读取 50 行 | `tmux-bridge read codex 100` |
| `tmux-bridge type <target> <text>` | 输入不带 Enter 的字面文本 | `tmux-bridge type codex "hello"` |
| `tmux-bridge keys <target> <key>...` | 发送特殊按键 | `tmux-bridge keys codex Enter` |
| `tmux-bridge name <target> <label>` | 为 pane 设置标签 | `tmux-bridge name %3 codex` |
| `tmux-bridge resolve <label>` | 将标签解析为原生 pane target | `tmux-bridge resolve codex` |
| `tmux-bridge id` | 打印当前 pane ID | `tmux-bridge id` |

将此表视为所导入版本的接口。版本不同时，优先使用本地 `--help`。

## 目标解析

可以使用以下任一形式：

- 原生 tmux target，例如 `shared:0.1` 或 `%3`；
- 之前通过 `tmux-bridge name` 分配的标签。

标签让回复地址更易读：

```bash
tmux-bridge name "$(tmux-bridge id)" coordinator
tmux-bridge name %3 worker
tmux-bridge resolve worker
```

依赖标签操作前，先读取解析后的 target。pane 退出或复用后，标签仍可能只是过期的发现提示。

## 消息约定

bridge 会原样输入收到的文本。使用发送方地址包装 Agent 消息：

```text
[tmux-bridge from:coordinator] Please review src/auth.ts
```

该地址告诉接收方 Agent 回复位置。不要虚构标签或 pane ID；从 `tmux-bridge id`、`tmux-bridge list` 或用户明确指定的 target 中取得它。

原子地发送包装后的请求：

```bash
tmux-bridge read worker 20
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Please review src/auth.ts'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

## 接收与回复

当提示包含 `[tmux-bridge from:<sender>]` 时，通过 bridge 向 `<sender>` 发送回复。只在当前 pane 中输入回复不会到达发送方：

```bash
tmux-bridge read <sender> 20
tmux-bridge type <sender> \
  '[tmux-bridge from:worker] Review complete; one issue remains.'
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
tmux-bridge read worker 20
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Run the focused tests and report failures.'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

对于需要回复的非 Agent pane：

```bash
tmux-bridge read worker 10
tmux-bridge type worker "y"
tmux-bridge read worker 10
tmux-bridge keys worker Enter
tmux-bridge read worker 20
```

## Agent 间工作流

当调用方在 tmux 内运行时，为其设置标签：

```bash
tmux-bridge name "$(tmux-bridge id)" coordinator
```

发现并检查目标：

```bash
tmux-bridge list
tmux-bridge read worker 20
```

带回复地址发送请求：

```bash
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Continue the task and report any blocker.'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
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
