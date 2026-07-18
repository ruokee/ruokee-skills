# tmux Operations for Agent Panes

Use this reference for raw tmux operations performed by `with-agents`. It covers the complete pane workflow; use [tmux-setup.md](tmux-setup.md) only for missing tmux, initial server setup, or session initialization.

## Contents

- [Operating Rules](#operating-rules)
- [Targets and Discovery](#targets-and-discovery)
- [Session, Window, and Pane Creation](#session-window-and-pane-creation)
- [Pane Reuse and Identity](#pane-reuse-and-identity)
- [Launching an Agent CLI](#launching-an-agent-cli)
- [Reading Pane Output](#reading-pane-output)
- [Sending Literal Single-Line Input](#sending-literal-single-line-input)
- [Sending Multiline Input](#sending-multiline-input)
- [Sending Special Keys](#sending-special-keys)
- [Reply Addresses and Pane Labels](#reply-addresses-and-pane-labels)
- [Monitoring and Persistent Waiting](#monitoring-and-persistent-waiting)
- [Clearing Screen, History, and Conversation Context](#clearing-screen-history-and-conversation-context)
- [Manual Attachment and Handoff](#manual-attachment-and-handoff)
- [Safe Cleanup](#safe-cleanup)
- [Troubleshooting](#troubleshooting)
- [Command Summary](#command-summary)

## Operating Rules

- Read a pane immediately before every interaction.
- Send literal text separately from Enter and other special keys.
- Read again after typing or pasting to verify that input reached the intended field.
- Use `%N` pane IDs as stable targets within the current tmux server lifetime.
- Treat titles, names, commands, and working directories only as identity hints.
- Keep executing, waiting, or retrying panes alive. Do not apply a fixed timeout unless the user sets one.
- Close only panes created for the current interaction, and only after the enclosing user task or goal fully completes.

Set a target only after discovery:

```bash
target="%3"
```

Never copy an example target without resolving it in the current server.

## Targets and Discovery

Check tmux and list sessions:

```bash
command -v tmux
tmux -V
tmux list-sessions \
  -F '#{session_name}\t#{session_windows}\t#{session_attached}'
```

List all panes with fields useful for identification:

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\tdead=#{pane_dead}\tpid=#{pane_pid}'
```

Common target forms are:

- pane ID: `%3`;
- session, window, and pane: `agents:1.0`;
- window target: `agents:1` where a window command is expected.

Prefer pane IDs for automation. Numeric window or pane indexes can change after layout changes or cleanup.

When the caller is already inside tmux, capture its address:

```bash
caller="${TMUX_PANE:-}"
session="$(tmux display-message -p '#{session_name}')"
```

Outside tmux, `$TMUX_PANE` is empty. Do not infer a caller address from the most recently active client.

## Session, Window, and Pane Creation

When the caller is already inside tmux, use its current session by default:

```bash
caller="${TMUX_PANE:-}"
session="$(tmux display-message -p '#{session_name}')"
```

Create new Agent windows or splits in that session unless the user explicitly selects a different session. This keeps the panes directly reachable through mouse, window, or pane selection instead of requiring a session switch such as `C-b s`. Do not create a separate session merely to isolate an Agent.

An existing pane explicitly selected by the user remains a valid target when it belongs to another session. Reuse it in place.

When the caller is outside tmux, prefer a user-selected session or a suitable existing session. Create a minimal detached session only when none is suitable:

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

Create a window and capture its pane ID:

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

Create a split when an existing pane should remain visible beside the new pane:

```bash
target="$(
  tmux split-window -d -P -F '#{pane_id}' \
    -t "$caller" \
    -c "$working_directory"
)"
```

Use `new-window` when the caller is outside tmux or when a separate window within the same session is clearer. Record whether the current interaction created the pane and window; cleanup depends on that fact.

## Pane Reuse and Identity

Before reusing a pane, capture its latest screen and inspect its process state:

```bash
tmux capture-pane -p -J -t "$target" -S -80
tmux display-message -p -t "$target" \
  '#{pane_id}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\tdead=#{pane_dead}\tpid=#{pane_pid}'
```

Attempt reuse when the pane is related to the current conversation or enclosing task, explicitly selected by the user, or clearly idle. A pane whose Agent is executing, waiting, or retrying is active, not idle. Continue that interaction instead of launching a duplicate.

Do not repurpose unrelated active work unless the user explicitly requests it. If pane identity or state remains uncertain, create a new pane.

Optionally assign a pane title for discovery without changing global tmux configuration:

```bash
tmux select-pane -t "$target" -T "$label"
```

Pane titles may not be visible in every layout and remain hints rather than authoritative identity.

## Launching an Agent CLI

Confirm the executable and arguments locally:

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

Build `launch_command` from the confirmed executable and launch arguments only. Keep task text out of the shell command. Then follow read, literal input, verify, and Enter:

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$launch_command"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

Wait for the CLI input UI to appear and read it before sending the task.

## Reading Pane Output

Read recent joined output:

```bash
tmux capture-pane -p -J -t "$target" -S -200
```

Useful options are:

- `-p`: print captured content to stdout;
- `-J`: join wrapped lines and preserve logical terminal lines;
- `-S -200`: start 200 lines above the visible pane;
- `-E <line>`: set an explicit end line when a bounded range is needed;
- `-e`: preserve escape sequences only when the consumer actually needs them.

Captured text is a terminal screen snapshot. It can contain stale scrollback, overwritten progress lines, pending input, or a completed result beside an active process. Interpret the TUI state instead of treating the last line as a structured completion flag.

## Sending Literal Single-Line Input

Use this complete cycle for every single-line message:

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$message"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

`send-keys -l` sends literal characters instead of interpreting key names. Keep `Enter` separate so the intermediate capture can confirm the target, input field, and pending text.

Terminal updates may arrive asynchronously. If the intermediate capture shows only part of the pending text, read again until the complete input is visible. Do not retype the message or send Enter while verification is incomplete.

Do not put untrusted task text inside a shell command string. Type it only after the Agent CLI is ready.

## Sending Multiline Input

Use a unique named tmux buffer and bracketed paste:

```bash
buffer="with-agents-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer" -
tmux paste-buffer -p -b "$buffer" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -30
tmux send-keys -t "$target" Enter
```

`paste-buffer -p` wraps the payload in bracketed-paste control codes when the target application has requested that mode. `-d` deletes the named buffer after a successful paste.

After pasting, verify that the entire request is one pending input before sending Enter. Do not use a fixed buffer name across concurrent interactions. Do not inject raw line breaks with repeated `send-keys`; compatible TUIs may interpret them as multiple submissions.

When the target does not support bracketed paste, inspect its local help and use its documented multiline editor or file-input mechanism.

## Sending Special Keys

Send special keys without `-l`:

```bash
tmux send-keys -t "$target" Enter
tmux send-keys -t "$target" Escape
tmux send-keys -t "$target" C-l
```

Before any special key, read the pane and confirm the intended effect. Treat `C-c`, `C-d`, process termination, and TUI quit keys as destructive controls:

```bash
tmux send-keys -t "$target" C-c
```

Use them only when the user requests termination or strong evidence shows that the process cannot continue and cannot recover within scope. Do not interrupt short-term errors, automatic retries, or temporary silence.

## Reply Addresses and Pane Labels

When the caller is inside tmux, frame requests with a reply address:

```bash
caller="${TMUX_PANE:-}"
if [ -n "$caller" ]; then
  message="[with-agents from:${caller}] ${request}"
else
  message="$request"
fi
```

When receiving a message such as `[with-agents from:%3]`, resolve `%3`, read it, type the reply literally, verify it, and send Enter separately.

When the caller is outside tmux, do not invent a reply target. Read the Agent pane at moderate intervals to collect responses.

## Monitoring and Persistent Waiting

Read both the pane screen and tmux process metadata:

```bash
tmux capture-pane -p -J -t "$target" -S -120
tmux display-message -p -t "$target" \
  'dead=#{pane_dead}\tstatus=#{pane_dead_status}\tcommand=#{pane_current_command}\tpid=#{pane_pid}'
```

Use moderate observation intervals. Distinguish these states:

- active output or live progress: keep waiting;
- automatic retry after a transient error: allow retry and keep the pane;
- Agent question or authorization prompt: answer it or ask the user while preserving the pane;
- goal blocker: supply context or recover within scope before reporting it;
- completed Agent request with an interactive CLI still open: preserve the pane for follow-up work;
- exited process or dead pane: capture final output and status before deciding whether recovery is possible.

Do not use a fixed timeout or retry count unless the user sets one. Temporary silence is not proof of failure.

## Clearing Screen, History, and Conversation Context

These operations have different meanings:

```bash
tmux send-keys -t "$target" C-l
tmux clear-history -t "$target"
```

- `C-l` commonly redraws or clears a shell/TUI screen; behavior belongs to the foreground application.
- `clear-history` removes tmux scrollback for the pane.
- Neither operation clears an Agent CLI conversation, model context, or persisted session.

For a fresh Agent context, use only a clear, reset, or new-conversation mechanism confirmed by that CLI's local `--help` or command UI. Read the pane before and after the operation. If no safe reset exists, exit the completed CLI normally and relaunch it in the same reusable pane.

## Manual Attachment and Handoff

Give the user a session target for observation or takeover:

```bash
tmux attach-session -t "$session"
```

Attachment is blocking for a caller outside tmux. Do not run it as an automated observation method; continue using `capture-pane` and `display-message`.

For a specific target, also report the pane ID and `session:window.pane` address from `list-panes`.

## Safe Cleanup

Before cleanup, capture final output and verify ownership:

```bash
tmux capture-pane -p -J -t "$target" -S -200
tmux display-message -p -t "$target" \
  '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\tdead=#{pane_dead}'
```

Close a pane only when all of these are true:

- the current interaction created it;
- the enclosing user task or goal fully completed, or the user explicitly requested termination;
- no handoff, follow-up, revision, review, or recoverable retry remains.

Then target the recorded pane ID explicitly:

```bash
tmux kill-pane -t "$target"
```

Killing the last pane also removes its window. Never close a pre-existing user pane without an explicit request. Use `kill-window`, `kill-session`, or `kill-server` only when the user explicitly requests that broader scope and ownership is certain.

## Troubleshooting

### `can't find pane`

Refresh `list-panes -a`; the pane may have exited or its server may have restarted. Do not reuse a stale `%N` target.

### Text reached the wrong pane or field

Stop before Enter. Capture the pane, correct the target, and remove pending text only through keys appropriate to the visible TUI. Do not assume shell editing shortcuts apply everywhere.

### Multiline text submitted as several requests

Confirm `paste-buffer -p` was used and that the target supports bracketed paste. Use the CLI's documented multiline mechanism when it does not.

### A retry appears stuck

Read recent output and process metadata at moderate intervals. Supply requested feedback or authorization. Do not kill or duplicate a live process solely because it is quiet.

### Screen clearing did not reset the Agent

Expected: tmux screen and history controls do not reset model context. Use the Agent CLI's confirmed conversation command.

## Command Summary

| Intent | Command |
| --- | --- |
| List sessions | `tmux list-sessions` |
| List all panes | `tmux list-panes -a -F '<format>'` |
| Read output | `tmux capture-pane -p -J -t "$target" -S -200` |
| Inspect pane state | `tmux display-message -p -t "$target" '<format>'` |
| Type literal text | `tmux send-keys -t "$target" -l -- "$message"` |
| Submit input | `tmux send-keys -t "$target" Enter` |
| Paste multiline text | `tmux paste-buffer -p -b "$buffer" -d -t "$target"` |
| Create a window | `tmux new-window -d -P -F '#{pane_id}' ...` |
| Create a split | `tmux split-window -d -P -F '#{pane_id}' ...` |
| Label a pane | `tmux select-pane -t "$target" -T "$label"` |
| Clear tmux history | `tmux clear-history -t "$target"` |
| Attach manually | `tmux attach-session -t "$session"` |
| Close an owned pane | `tmux kill-pane -t "$target"` |
