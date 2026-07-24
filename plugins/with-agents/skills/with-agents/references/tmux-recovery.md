# tmux Recovery for with-agents

Read this only after the bundled controller cannot finish an action, `doctor` reports a backend problem, or a partial input needs manual recovery. Raw tmux bypasses the per-pane lock and the structured partial-stage reporting, so reserve it for deliberate fallback.

## Contents

- [Diagnose the server and socket](#diagnose-the-server-and-socket)
- [Resolve and inspect a pane](#resolve-and-inspect-a-pane)
- [Recover a partial send](#recover-a-partial-send)
- [Create a minimal backend by hand](#create-a-minimal-backend-by-hand)
- [Paste a body by hand](#paste-a-body-by-hand)
- [Close panes safely](#close-panes-safely)
- [Reference routing](#reference-routing)

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
```

`$TMUX` has the form `socket_path,server_pid,session_index`. The socket path itself may contain commas, so split the two trailing numeric fields off the right. Cutting at the first comma silently truncates a comma socket to a wrong path. When `$TMUX` names the intended live server, use that exact socket. Do not infer one from another client:

```bash
rest="${TMUX%,*}"          # drop session_index
socket_path="${rest%,*}"   # drop server_pid, keep the full socket path
tmux -S "$socket_path" list-sessions
tmux -S "$socket_path" display-message -p '#{socket_path}|#{pid}'
```

Every raw tmux command against this existing server carries this same `-S "$socket_path"`. Dropping it sends the command to tmux's default server, which may hold a different pane under the same `%id` — a silent wrong target for a capture, a paste, an Enter, or a `kill-pane`. If `$TMUX` is stale, do not silently redirect an input operation onto the default server. Find the intended server with the user or from a known exact socket, then rerun the controller command with `--socket PATH`.

## Resolve and inspect a pane

List authoritative identities alongside discovery hints. A pane is located by socket + pane ID; the public name is the live `window_name`, and the pane PID and dead status are diagnostic fields only:

```bash
tmux -S "$socket_path" list-panes -a \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|name=#{window_name}'
```

Capture the real screen before any input:

```bash
target="%3"
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -120
tmux -S "$socket_path" display-message -p -t "$target" \
  '#{pane_id}|#{pane_pid}|#{window_name}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|status=#{pane_dead_status}'
```

Names, titles, commands, paths, and window indexes are hints only; split panes in one window share a `window_name`. Locate a pane by its socket and `%pane-id`; treat the PID and dead status as diagnostics, and refresh them after any server restart, respawn, or layout change.

## Recover a partial send

When `send` reports `text_written_not_submitted`, the text may be sitting in the target composer. Do not send the whole message again.

1. Capture the pane and positively confirm the pending composer text.
2. If the full intended text is present and the target CLI's ordinary submit key is known, send only that key.
3. If the text is partial, wrong, or the pane is in a confirmation or menu state, stop and let the user inspect it or use a target-specific editing action confirmed by that CLI.

Submit-only recovery after a positive inspection:

```bash
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -40
tmux -S "$socket_path" send-keys -t "$target" Enter
```

`submitted_state_unknown` means tmux may already have delivered both the text and the submit key. Read the pane; never replay automatically.

To place fresh input into a plain shell or a positively confirmed empty Agent composer, use the same buffer-paste mechanism as [Paste a body by hand](#paste-a-body-by-hand). The `send-keys -l` path can truncate a long body. Any such manual step is outside the normal Skill workflow and holds no shared pane lock. Do not run it concurrently with `with-agents`.

## Create a minimal backend by hand

`launch` normally starts a missing detached server for you. When tmux itself must be diagnosed separately, make a minimal test session on its own explicit socket so it never mixes with the server under investigation, and leave personal configuration unchanged:

```bash
recovery_socket="/tmp/with-agents-recovery-$$.sock"
session="with-agents-recovery"
tmux -S "$recovery_socket" new-session -d -s "$session" -n shell -c "$PWD"
tmux -S "$recovery_socket" list-panes -t "$session" \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_current_path}'
```

Drive every command for this recovery backend with the same `-S "$recovery_socket"`; do not fall back to the default server.

Do not download or overwrite `~/.tmux.conf` for this Skill. The controller never changes server-level options or the pane key mode, and submission is a plain buffer paste plus ordinary `Enter`, so nothing depends on `extended-keys`, `extended-keys-format=csi-u`, or `pane_key_mode=Ext 2`. `doctor` does not read or report these options; if you want to inspect them yourself:

```bash
tmux -S "$socket_path" show-options -s -v extended-keys
tmux -S "$socket_path" show-options -s -v extended-keys-format
```

## Paste a body by hand

`send` always pastes through a buffer, so manual recovery uses the same mechanism with a unique buffer name:

```bash
buffer_name="with-agents-recovery-$$-$(date +%s)"
printf '%s' "$message" | tmux -S "$socket_path" load-buffer -b "$buffer_name" -
tmux -S "$socket_path" paste-buffer -p -b "$buffer_name" -d -t "$target"
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -40
```

Inspect the pending composer before sending its submit key. Bracketed-paste support comes from the target CLI's behavior; `paste-buffer -p` provides no runtime evidence of it.

## Close panes safely

Capture final output and confirm the exact identity before closing anything:

```bash
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -200
tmux -S "$socket_path" display-message -p -t "$target" \
  '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{window_name}|dead=#{pane_dead}'
```

Close only the exact pane the current task created or that the user explicitly selected:

```bash
tmux -S "$socket_path" kill-pane -t "$target"
```

Never reach for `kill-server`, `kill-session`, or `kill-window` as a broad recovery shortcut. Preserve live, waiting, retrying, and user panes until their enclosing task and any review work are complete.

## Reference routing

- [cli.md](cli.md) — the command index, global options, the JSON envelope, and representative error codes.
- [messaging.md](messaging.md) — the send header grammar, params, and replying.
- [operation-states.md](operation-states.md) — the send input stages and the no-blind-replay rule this recovery follows.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET resolution, the live window name, the route grammar, and self-target.
- [presets.md](presets.md) — preset schema, pane naming, and the private Agent registry.
- [adapters.md](adapters.md) — per-CLI clear-input and new-conversation differences.
