# tmux Recovery for with-agents

Read this only after the bundled controller cannot finish an event, `doctor` reports a backend problem, or a partial input needs manual recovery. Raw tmux bypasses observation credentials, ownership checks, the per-pane lock, argv records, and structured partial-stage reporting, so use it as a deliberate fallback rather than the normal path.

## Contents

- [Diagnose the server and socket](#diagnose-the-server-and-socket)
- [Resolve and inspect a pane](#resolve-and-inspect-a-pane)
- [Recover a partial send](#recover-a-partial-send)
- [Create a minimal backend by hand](#create-a-minimal-backend-by-hand)
- [Recover multiline input](#recover-multiline-input)
- [Inspect owned metadata](#inspect-owned-metadata)
- [Close panes safely](#close-panes-safely)

## Diagnose the server and socket

Start with the controller's read-only diagnostic:

```bash
<skill-root>/scripts/with-agents doctor
```

Then look at tmux without changing anything:

```bash
command -v tmux
tmux -V
printf '%s\n' "TMUX=${TMUX:-<unset>}" "TMUX_PANE=${TMUX_PANE:-<unset>}"
tmux list-sessions
```

`$TMUX` has the form `socket_path,server_pid,session_index`. When it names the intended live server, use that exact socket instead of guessing from another client:

```bash
socket_path="${TMUX%%,*}"
tmux -S "$socket_path" list-sessions
tmux -S "$socket_path" display-message -p '#{socket_path}|#{pid}'
```

If `$TMUX` is stale, do not silently redirect an input operation onto the default server. Find the intended server with the user or from a known exact socket, then rerun the controller command with `--socket PATH`.

## Resolve and inspect a pane

List authoritative identities alongside discovery hints:

```bash
tmux list-panes -a \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|name=#{@with_agents_name}|run=#{@with_agents_run_id}'
```

Capture the real screen before any input:

```bash
target="%3"
tmux capture-pane -p -J -t "$target" -S -120
tmux display-message -p -t "$target" \
  '#{pane_id}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|status=#{pane_dead_status}'
```

Names, titles, commands, paths, and window indexes are hints only. Refresh the pane ID and PID after any server restart, respawn, or layout change.

## Recover a partial send

When `send` reports `text_written_not_submitted`, the text may be sitting in the target composer. Do not send the whole message again.

1. Capture the pane and positively confirm the pending composer text.
2. If the full intended text is present and the target CLI's ordinary submit key is known, send only that key.
3. If the text is partial, wrong, or the pane is in a confirmation or menu state, stop and let the user inspect it or use a target-specific editing action confirmed by that CLI.

Submit-only recovery after a positive inspection:

```bash
tmux capture-pane -p -J -t "$target" -S -40
tmux send-keys -t "$target" Enter
```

`submitted_state_unknown` means tmux may already have delivered both the text and the submit key. Read the pane; never replay automatically.

For a plain shell or a positively confirmed empty Agent composer, literal single-line input is:

```bash
tmux send-keys -t "$target" -l -- "$message"
tmux send-keys -t "$target" Enter
```

This manual pair is outside the normal Skill workflow and holds no shared controller lock. Do not run it concurrently with `with-agents`.

## Create a minimal backend by hand

`create` and `launch` normally start a missing detached server for you. When tmux itself must be diagnosed separately, make a minimal test session rather than editing personal configuration:

```bash
session="with-agents-recovery"
tmux new-session -d -s "$session" -n shell -c "$PWD"
tmux list-panes -t "$session" \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_current_path}'
```

Do not download or overwrite `~/.tmux.conf` for this Skill. The controller never changes server-level options or the pane key mode. Pi and Codex pane notification use ordinary `Enter` for both safe idle and safe busy states, so neither depends on `extended-keys`, `extended-keys-format=csi-u`, or `pane_key_mode=Ext 2`. `doctor` still reports the server's `extended_keys` and `extended_keys_format` values, but only as informational tmux facts, not as a notification prerequisite. If you want to inspect them anyway:

```bash
tmux show-options -s -v extended-keys
tmux show-options -s -v extended-keys-format
```

## Recover multiline input

Unknown adapters deliberately reject multiline `send`. When a target CLI has independently documented bracketed-paste support and manual recovery is in scope, use a unique buffer:

```bash
buffer_name="with-agents-recovery-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer_name" -
tmux paste-buffer -p -b "$buffer_name" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -40
```

Inspect the pending composer before sending its submit key. `paste-buffer -p` is not runtime proof that the application supports bracketed paste; that support must come from the target adapter or the CLI's own documentation.

## Inspect owned metadata

The controller keeps only short, non-secret routing metadata in tmux pane options:

```bash
tmux show-options -p -t "$target" | \
  grep -E '@with_agents_(owner|run_id|name|preset)'
```

Exact argv and observation or request state live in the private runtime root that `doctor` reports. Do not edit those files to bypass an identity or ownership error. A mismatched record usually means the pane was respawned, the server changed, or state expired — establish a new observation or launch a new owned run instead.

## Close panes safely

Capture final output and confirm exact ownership before closing anything:

```bash
tmux capture-pane -p -J -t "$target" -S -200
tmux display-message -p -t "$target" \
  '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|owner=#{@with_agents_owner}|run=#{@with_agents_run_id}|dead=#{pane_dead}'
```

Close only the exact pane the current task owns or that the user explicitly selected:

```bash
tmux kill-pane -t "$target"
```

Never reach for `kill-server`, `kill-session`, or `kill-window` as a broad recovery shortcut. Preserve live, waiting, retrying, and user-owned panes until their enclosing task and any review work are complete.
