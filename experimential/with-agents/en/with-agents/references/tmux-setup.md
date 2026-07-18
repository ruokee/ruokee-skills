# Initialize a tmux Environment

Read this reference only when:

- the `tmux` command is missing;
- no tmux server is running;
- no suitable session exists for an external Agent CLI; or
- the user explicitly requests tmux initialization.

## 1. Inspect tmux

```bash
command -v tmux
tmux -V
```

When tmux is missing, report the dependency and handle installation according to the current system, harness permissions, and user intent. Do not download a complete personal tmux configuration or overwrite `~/.tmux.conf` or `~/.config/tmux/tmux.conf` merely for this Skill.

## 2. Select or Create a Session

When the current Agent already runs inside tmux, reuse the current server and session:

```bash
session="$(tmux display-message -p '#{session_name}')"
caller="${TMUX_PANE:-}"
```

When the current Agent runs outside tmux, inspect existing sessions first:

```bash
tmux list-sessions
```

Reuse a suitable session when one exists. Otherwise create a minimal detached session:

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

This session supplies a terminal container for the external Agent CLI.

## 3. Create a Target Window

Confirm the requested executable and its local arguments:

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

Create a shell window and capture its pane ID:

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

When side-by-side observation is more useful, create a split instead:

```bash
target="$(
  tmux split-window -d -P -F '#{pane_id}' \
    -t "$caller" \
    -c "$working_directory"
)"
```

`split-window` requires an existing target pane. Default to `new-window` when the caller is outside tmux.

Continue with [tmux.md](tmux.md) to start the CLI by entering a `launch_command` built only from the executable and arguments confirmed by local `--help`.

## 4. Verify the Environment

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
tmux capture-pane -p -J -t "$target" -S -50
```

Confirm that the target shell is ready in the expected working directory, then continue with the interaction workflow in [tmux.md](tmux.md).

## 5. Hand Off for Manual Attachment

When the user wants to observe or take over, provide:

```bash
tmux attach-session -t "$session"
```

Do not run this blocking attach command from an Agent outside the session. Continue using `capture-pane` and `send-keys` for automated interaction.

## Environment Boundaries

- When the caller is outside tmux, it has no `$TMUX_PANE` reply address. Read the target pane directly.
