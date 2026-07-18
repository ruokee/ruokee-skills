---
name: with-agents
description: Use external Agent CLIs through tmux when the user explicitly requests a particular external CLI, an existing Agent pane, tmux-based interaction, or this Skill. Prefer native harness subagents for ordinary delegation when available. Cover CLI discovery, pane lifecycle, literal input, multiline prompts, persistent waiting and retries, feedback handling, and safe termination.
---

# With Agents

Treat each external Agent CLI as an ordinary interactive terminal program. Start, observe, and interact with it through tmux.

## Choose the Invocation Path

1. Inspect the tools exposed by the current harness.
2. Use native subagent, delegation, or parallel-Agent tools for ordinary delegation when the harness provides them.
3. Use this Skill only when the user explicitly requests an external Agent CLI, an existing Agent pane, tmux interaction, or `with-agents`.

Choose the CLI, model, working directory, and task from the current request.

## Discover the Environment

Inspect the requested CLI and tmux before starting anything:

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
command -v tmux
tmux list-sessions
```

Replace `<requested-cli>` with the actual executable. Confirm launch arguments from the installed CLI's `--help` output instead of relying on remembered syntax.

Read [tmux-setup.md](references/tmux-setup.md) only when tmux is missing, no server is running, no suitable session exists, or the user explicitly requests tmux initialization.

## Discover an Agent Pane

List panes in the current tmux server:

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
```

Use the `%N` pane ID as the `target` for later commands. Treat window names, pane titles, and current commands only as discovery hints. Read the pane immediately before sending input to confirm its identity and TUI state:

```bash
tmux capture-pane -p -J -t "$target" -S -50
```

## Reuse an Existing Pane

Inspect existing panes before creating one. Prefer attempting reuse when a pane belongs to the current conversation or enclosing task, the user explicitly identifies it, or it is clearly idle.

Read the pane first. A pane whose Agent is executing, waiting, or retrying is active rather than idle; continue observing or interacting with that Agent instead of launching a duplicate. Do not repurpose a pane that contains unrelated active work unless the user explicitly directs it.

When the existing Agent context remains relevant, continue the same CLI conversation. When a fresh context is needed, use only a clear, reset, or new-conversation mechanism confirmed by the target CLI's local help or command UI. Clearing the terminal screen does not clear conversation context. If safe reuse cannot be confirmed, create a new pane.

## Start a New Agent CLI

When no suitable pane exists, create a shell window in the selected session and capture its pane ID:

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

Build `launch_command` from the executable and only arguments confirmed by local `--help`. Keep task text out of this shell command. Start the CLI with the same read, literal-input, confirm, and Enter discipline used for Agent messages:

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$launch_command"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

Use `new-window` or `split-window` according to the interaction layout.

## Send a Single-Line Request

Follow read, input, confirm, then Enter:

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$message"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

Use `-l` to send literal text. Send text separately from `Enter`, `C-c`, or other special keys. The intermediate read confirms that the text reached the intended input field.

When the caller is already inside tmux, prepend its reply address:

```bash
caller="${TMUX_PANE:-}"
if [ -n "$caller" ]; then
  message="[with-agents from:${caller}] ${request}"
else
  message="$request"
fi
```

When the caller is outside tmux, do not invent a reply pane. Read the target pane to collect the response.

## Send a Multiline Request

Use a buffer name unique to the current interaction:

```bash
buffer="with-agents-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer" -
tmux paste-buffer -p -b "$buffer" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

Use `-p` so tmux wraps the content in bracketed-paste control codes when the target application requests that mode. This prevents compatible TUIs from treating embedded line breaks as separate submissions. After pasting, confirm that the entire request appears as one pending input before sending `Enter`.

Do not reuse a fixed buffer name across concurrent interactions. When the target TUI does not support bracketed paste, discover its safe multiline-input mechanism instead of injecting raw line breaks as key presses.

## Read, Reply, and Continue

Read recent pane output:

```bash
tmux capture-pane -p -J -t "$target" -S -200
```

Treat captured output as a terminal screen, not as a structured result, reliable progress record, or completion signal. Interpret the actual screen state before following up, supplying context, or reporting to the user.

When a request includes a reply address such as `[with-agents from:%3]`, use `%3` as the reply target and apply the same read, literal-input, confirm, and Enter sequence.

Avoid high-frequency polling. Continue non-conflicting work and read the pane at moderate intervals or when its result becomes necessary.

## Wait and Recover Persistently

Keep the target pane while the Agent is running, waiting, or retrying:

- Treat a live Agent process that is executing, awaiting a response, or automatically retrying as still active. Do not impose a fixed timeout or retry limit unless the user explicitly sets one.
- Prefer the Agent's own retry for transient API, network, rate-limit, or upstream errors. Do not send `C-c`, kill the pane, or launch an equivalent duplicate solely because of a short-term error, temporary silence, or a long wait.
- Read the pane at a moderate frequency to distinguish automatic retries, input requests, task completion, and process exit. Perform only non-conflicting work while waiting.
- When the Agent requests feedback, clarification, or authorization, read the question and respond through the same read, input, confirm, and Enter sequence. If it requires a user decision or new authority, explain that need to the user and keep the pane waiting.
- When the Agent reports a goal blocker, inspect the cause. Supply missing context, answer questions, or address recoverable conditions first. If recovery requires user input or an external-state change, report the blocker while preserving any live or waiting Agent.
- End the Agent only after the enclosing user task or goal fully completes, the user explicitly requests termination, or strong evidence shows that it cannot continue and cannot recover within the authorized scope. Capture final output and process state before ending it.

Keep panes created for the current interaction until the enclosing user task or goal fully completes, even when an individual Agent request has returned. Reuse them for follow-up questions, revisions, review, or additional Agent steps. After full completion, capture the final state and clean up only panes created for the current interaction when no handoff or further review is needed. Do not close a pre-existing user pane unless the user explicitly requests it.
