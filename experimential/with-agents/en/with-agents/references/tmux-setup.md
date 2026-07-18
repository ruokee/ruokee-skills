# Initialize a tmux Environment

Read this reference only when:

- the `tmux` command is missing;
- no tmux server is running;
- no suitable session exists for an external Agent CLI;
- the bundled `tmux-bridge` script needs inspection or authorized installation; or
- the user explicitly requests tmux initialization.

## Contents

- [1. Inspect tmux](#1-inspect-tmux)
- [2. Select or Create a Session](#2-select-or-create-a-session)
- [3. Inspect or Install the Bundled tmux-bridge](#3-inspect-or-install-the-bundled-tmux-bridge)
- [4. Create a Target Window](#4-create-a-target-window)
- [5. Verify the Environment](#5-verify-the-environment)
- [6. Hand Off for Manual Attachment](#6-hand-off-for-manual-attachment)
- [Environment Boundaries](#environment-boundaries)

## 1. Inspect tmux

```bash
command -v tmux
tmux -V
```

When tmux is missing, report the dependency and handle installation according to the current system, harness permissions, and user intent. Do not download a complete personal tmux configuration or overwrite `~/.tmux.conf` or `~/.config/tmux/tmux.conf` merely for this Skill.

## 2. Select or Create a Session

When the current Agent already runs inside tmux, use the caller's current session by default:

```bash
session="$(tmux display-message -p '#{session_name}')"
caller="${TMUX_PANE:-}"
```

Create new Agent windows or splits in that session unless the user selects a different session or identifies a pane elsewhere. Keeping related panes in one session lets the user move between them through mouse, window, or pane selection. Do not create a separate session merely to isolate an Agent; it would require a session switch such as `C-b s` for manual navigation.

An explicitly selected pane remains valid even when it belongs to another session. Operate on that pane in place rather than moving or replacing it.

When the current Agent runs outside tmux, inspect existing sessions first:

```bash
tmux list-sessions
```

Prefer, in order:

1. the session or pane explicitly selected by the user;
2. a suitable existing session containing related or idle panes;
3. a new minimal detached session only when no existing session is suitable.

Create the fallback session only when necessary:

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

This session supplies a terminal container for the external Agent CLI.

## 3. Inspect or Install the Bundled tmux-bridge

This Skill bundles `scripts/tmux-bridge` relative to its installed Skill root. Resolve that actual root rather than assuming the repository layout:

```bash
bundled_bridge="<skill-root>/scripts/tmux-bridge"
bash -n "$bundled_bridge"
"$bundled_bridge" version
```

The bundled executable can be run directly without installing it. A request to use `tmux-bridge` does not by itself authorize copying it into `PATH`.

Installing the script changes the user's filesystem and requires the user's explicit authorization first. Before asking, report:

- the exact source and destination paths;
- whether the destination already exists and would be overwritten;
- whether the destination directory is already on `PATH`.

A conventional user-local destination is `$HOME/.local/bin/tmux-bridge`. After explicit authorization, and only when the destination does not require separate overwrite approval, install it with:

```bash
install_dir="${HOME}/.local/bin"
install_target="${install_dir}/tmux-bridge"
install -d "$install_dir"
install -m 0755 "$bundled_bridge" "$install_target"
"$install_target" version
```

If `install_target` already exists and differs from the bundled script, obtain explicit authorization to overwrite that exact file. Do not replace it as part of a general installation approval. Do not edit shell startup files or change `PATH` without separate explicit authorization; use the direct script path when the destination is not already discoverable.

When a tmux server is available, verify the installed or direct command against it:

```bash
"$bundled_bridge" doctor
```

Read [tmux-bridge.md](tmux-bridge.md) before using the bridge to interact with panes.

## 4. Create a Target Window

Confirm the requested executable and its local arguments:

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

Create a shell window in the selected session and capture its pane ID:

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

`split-window` requires an existing target pane. When the caller is outside tmux, prefer `new-window` in the selected existing session. Record the created pane and window so cleanup can be limited to resources created for the current interaction.

Continue with [tmux.md](tmux.md) to start the CLI by entering a `launch_command` built only from the executable and arguments confirmed by local `--help`.

## 5. Verify the Environment

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
tmux capture-pane -p -J -t "$target" -S -50
```

Confirm that the target shell is ready in the expected working directory, then continue with the interaction workflow in [tmux.md](tmux.md).

## 6. Hand Off for Manual Attachment

When the user wants to observe or take over, provide:

```bash
tmux attach-session -t "$session"
```

Do not run this blocking attach command from an Agent outside the session. Continue using `capture-pane` and `send-keys` for automated interaction.

## Environment Boundaries

- When the caller is outside tmux, it has no `$TMUX_PANE` reply address. Read the target pane directly.
- Installing the bundled script, overwriting an existing executable, and modifying shell configuration are separate state-changing actions; each requires the applicable explicit authorization.
- A pane explicitly selected by the user may live in another session. Reuse it without forcing a session migration.
