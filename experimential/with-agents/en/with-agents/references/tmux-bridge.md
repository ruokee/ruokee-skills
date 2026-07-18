# tmux-bridge Reference

This document adapts the smux [`tmux-bridge.md`](https://github.com/ShawnPana/smux/blob/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f/skills/smux/references/tmux-bridge.md) reference for `with-agents`. The upstream revision is `70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f` and is distributed under the MIT License. See [License](#license).

## Contents

- [Scope and Compatibility](#scope-and-compatibility)
- [Bundled Script and Environment](#bundled-script-and-environment)
- [Atomic Commands and Read Guard](#atomic-commands-and-read-guard)
- [Command Reference](#command-reference)
- [Target Resolution](#target-resolution)
- [Messaging Convention](#messaging-convention)
- [Receiving and Replying](#receiving-and-replying)
- [Read-Act-Read Cycle](#read-act-read-cycle)
- [Agent-to-Agent Workflow](#agent-to-agent-workflow)
- [Waiting and Lifecycle Semantics](#waiting-and-lifecycle-semantics)
- [Operational Tips](#operational-tips)
- [License](#license)

## Scope and Compatibility

Use `tmux-bridge` when the user requests it, an existing workflow already uses it, or its enforced read guard and pane labels are useful. Inspect an installed command when present:

```bash
command -v tmux-bridge
tmux-bridge --help
```

This Skill also bundles an adapted executable at `scripts/tmux-bridge` relative to the installed Skill root. It can be invoked directly when no command is installed. Installing it into `PATH`, overwriting an existing executable, or changing shell configuration requires the user's explicit authorization; follow [tmux-setup.md](tmux-setup.md). Confirm actual syntax with the selected executable's `--help`. When no bridge is available and the user did not require it specifically, use raw tmux and read [tmux.md](tmux.md).

The bridge relay convention works best when both the sender and receiver are bridge-aware Agent panes. When the caller is outside tmux, the target is not bridge-aware, or replies do not return to the caller pane, read the target pane at moderate intervals instead.

## Bundled Script and Environment

The bundled script is derived from smux `tmux-bridge` 2.0.0 at the pinned revision above and identifies itself as `2.0.0-with-agents.1`. Local adaptations:

- make generated messages tell receivers to load the `with-agents` Skill;
- namespace read-guard files by user, tmux socket, and pane identity;
- invalidate a guard when the pane is respawned or reused;
- require a positive integer for the optional `read` line count;
- report an empty label count correctly in `doctor`.

The command observes these optional environment variables:

| Variable | Purpose |
| --- | --- |
| `TMUX_BRIDGE_SOCKET` | Select a tmux socket with `tmux -L` semantics |
| `TMUX_BRIDGE_RUNTIME_DIR` | Override the private directory used for read-guard files |

Without `TMUX_BRIDGE_RUNTIME_DIR`, guard files live in a mode-`0700`, current-user-owned `tmux-bridge-<uid>` directory under `XDG_RUNTIME_DIR`, `TMPDIR`, or `/tmp`. The guard records the current pane ID, PID, session ID, and window ID. A changed identity requires another `read` before interaction.

## Atomic Commands and Read Guard

`tmux-bridge` exposes atomic actions:

- `type` types literal text without Enter;
- `keys` sends special keys;
- `read` captures pane content.

It deliberately has no compound send operation. Preserve the separation so input can be verified before submission.

The CLI enforces read-before-act:

1. `tmux-bridge read <target>` marks the pane as read.
2. `tmux-bridge type <target> ...` or `tmux-bridge keys <target> ...` requires that mark.
3. Each successful `type` or `keys` action clears the mark.
4. Read again before the next action.

Skipping the read should fail like this:

```text
$ tmux-bridge type codex "hello"
error: must read the pane before interacting. Run: tmux-bridge read codex
```

## Command Reference

| Command | Description | Example |
| --- | --- | --- |
| `tmux-bridge list` | Show panes with target, process, size, and label | `tmux-bridge list` |
| `tmux-bridge read <target> [lines]` | Read recent output; defaults to 50 lines upstream | `tmux-bridge read codex 100` |
| `tmux-bridge type <target> <text>` | Type literal text without Enter | `tmux-bridge type codex "hello"` |
| `tmux-bridge message <target> <text>` | Type a framed Agent message without Enter | `tmux-bridge message codex "Review this change"` |
| `tmux-bridge keys <target> <key>...` | Send special keys | `tmux-bridge keys codex Enter` |
| `tmux-bridge name <target> <label>` | Assign a pane label | `tmux-bridge name %3 codex` |
| `tmux-bridge resolve <label>` | Resolve a label to a native pane target | `tmux-bridge resolve codex` |
| `tmux-bridge id` | Print the current pane ID | `tmux-bridge id` |
| `tmux-bridge doctor` | Check tmux, server, panes, and bridge state | `tmux-bridge doctor` |
| `tmux-bridge version` | Print the executable version | `tmux-bridge version` |

Treat this table as the imported revision's interface. Prefer local `--help` when versions differ.

## Target Resolution

Use either:

- a native tmux target such as `shared:0.1` or `%3`;
- a label previously assigned with `tmux-bridge name`.

Labels make reply addresses easier to read:

```bash
tmux-bridge name "$(tmux-bridge id)" coordinator
tmux-bridge name %3 worker
tmux-bridge resolve worker
```

Read a resolved target before relying on its label. Labels remain discovery aids and may be stale after pane exit or reuse.

## Messaging Convention

The bridge `type` command types exactly the supplied text. Frame Agent messages with a sender address:

```text
[tmux-bridge from:coordinator] Please review src/auth.ts
```

The address tells the receiving Agent where to reply. Do not invent a label or pane ID; derive it from `tmux-bridge id`, `tmux-bridge list`, or an explicit user target.

When the caller runs inside tmux, `message` generates that frame automatically and adds a hint for the receiver to load `with-agents` before replying:

```bash
tmux-bridge read worker 20
tmux-bridge message worker 'Please review src/auth.ts'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

Use the manual `type` form below when the caller is outside tmux or a different explicit sender address is required.

Send the framed request atomically:

```bash
tmux-bridge read worker 20
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Please review src/auth.ts'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

## Receiving and Replying

When a prompt contains `[tmux-bridge from:<sender>]`, send the response to `<sender>` through the bridge. A response typed only in the current pane will not reach the sender:

```bash
tmux-bridge read <sender> 20
tmux-bridge type <sender> \
  '[tmux-bridge from:worker] Review complete; one issue remains.'
tmux-bridge read <sender> 20
tmux-bridge keys <sender> Enter
```

Read before both `type` and `keys`; each action consumes the read guard.

## Read-Act-Read Cycle

Use this full sequence:

1. Read the target to confirm identity, state, and input field.
2. Type the message without Enter.
3. Read again to verify pending text and restore the read guard.
4. Send Enter separately.
5. Read later when the result is needed and no reply will be relayed to the caller pane.

Example:

```bash
tmux-bridge read worker 20
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Run the focused tests and report failures.'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

For a non-Agent pane that requires a response:

```bash
tmux-bridge read worker 10
tmux-bridge type worker "y"
tmux-bridge read worker 10
tmux-bridge keys worker Enter
tmux-bridge read worker 20
```

## Agent-to-Agent Workflow

Label the caller when it runs inside tmux:

```bash
tmux-bridge name "$(tmux-bridge id)" coordinator
```

Discover and inspect the target:

```bash
tmux-bridge list
tmux-bridge read worker 20
```

Send a request with a reply address:

```bash
tmux-bridge type worker \
  '[tmux-bridge from:coordinator] Continue the task and report any blocker.'
tmux-bridge read worker 20
tmux-bridge keys worker Enter
```

If the receiving Agent is bridge-aware, let it reply into the caller pane. Otherwise capture its pane at moderate intervals. Do not busy-loop in either mode.

## Waiting and Lifecycle Semantics

The upstream reference says not to wait or poll because it assumes the other Agent will reply directly into the sender's pane. Interpret that statement narrowly as a relay optimization, not as permission to abandon the Agent or close its pane.

Apply the lifecycle rules from `SKILL.md`:

- keep executing, waiting, and automatically retrying Agents alive without a fixed timeout;
- respond to feedback, clarification, authorization, and goal blockers;
- observe at moderate intervals when direct replies are unavailable or the result becomes necessary;
- keep created panes available for follow-up work until the enclosing user task or goal fully completes;
- end only after full completion, explicit user termination, or an unrecoverable condition within the authorized scope.

## Operational Tips

- Read before every `type` and `keys` action; the guard is consumed after each action.
- Use labels for readability but verify the resolved pane before interacting.
- Keep text and Enter separate.
- Use bridge `type` for literal single-line input.
- Use bridge `message` for a framed single-line Agent request when the caller has a tmux pane ID.
- For safe multiline input, resolve the native target and follow the bracketed-paste procedure in [tmux.md](tmux.md) unless the installed bridge documents equivalent support.
- Read non-Agent panes to collect output because they will not send a framed reply.
- Do not mix raw tmux and bridge operations casually; raw commands bypass the bridge's read guard.

## License

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
