---
name: with-agents
description: Use external Agent CLIs through tmux when the user explicitly requests a particular external CLI, an existing Agent pane, tmux-based interaction, or this Skill. Prefer native harness subagents for ordinary delegation when available. Cover control-interface discovery, pane reuse and lifecycle, atomic literal input, multiline prompts, persistent waiting and retries, feedback handling, and safe termination.
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
tmux -V
tmux list-sessions
command -v tmux-bridge || true
```

Replace `<requested-cli>` with the actual executable. Confirm launch arguments from the installed CLI's `--help` output instead of relying on remembered syntax.

Read [tmux-setup.md](references/tmux-setup.md) only when tmux is missing, no server is running, no suitable session exists, the bundled bridge needs inspection or authorized installation, or the user explicitly requests tmux initialization.

## Choose the tmux Control Interface

Use raw tmux commands by default. Read [tmux.md](references/tmux.md) before creating, inspecting, operating, handing off, or closing panes with raw tmux.

When the user requests `tmux-bridge`, an existing workflow already uses it, or its read guard and labels are useful, first inspect any command available on `PATH` and read [tmux-bridge.md](references/tmux-bridge.md). This Skill also bundles an optional `scripts/tmux-bridge` executable that can be run directly from the installed Skill directory. Installing it into `PATH`, overwriting an existing command, or changing shell configuration requires the user's explicit authorization; follow [tmux-setup.md](references/tmux-setup.md). If no bridge is available and the user did not require it specifically, use raw tmux.

Keep one control interface for an interaction unless a documented limitation requires raw tmux. Preserve the read, literal-input, confirm, and Enter sequence with either interface.

## Discover and Reuse an Agent Pane

Inspect existing panes before creating one. Prefer attempting reuse when a pane belongs to the current conversation or enclosing task, the user explicitly identifies it, or it is clearly idle.

Read the pane first. Treat names, titles, current commands, and paths only as discovery hints. A pane whose Agent is executing, waiting, or retrying is active rather than idle; continue observing or interacting with that Agent instead of launching a duplicate. Do not repurpose a pane that contains unrelated active work unless the user explicitly directs it.

When the existing Agent context remains relevant, continue the same CLI conversation. When a fresh context is needed, use only a clear, reset, or new-conversation mechanism confirmed by the target CLI's local help or command UI. Clearing the terminal screen or tmux history does not clear conversation context. If safe reuse cannot be confirmed, create a new pane.

## Start an Agent CLI

When no suitable pane exists, follow the selected control-interface reference to create a shell pane in the intended session and working directory. Name every pane created by this Skill `<agent_type>-<name>`, where `agent_type` is exactly two lowercase letters and `name` is one lowercase word of no more than six letters. Use `cc` for Claude Code, `cx` for Codex, and `pi` for Pi; choose an equivalent two-letter code for another CLI. Keep the name unique within the tmux server. Do not rename a reused or pre-existing pane unless the user explicitly requests it.

When the caller is already inside tmux and the user has not selected another session, create the new window or split in the caller's current session. This keeps panes reachable through ordinary mouse, window, or pane selection without requiring a session switch. An explicitly selected pane or session elsewhere takes precedence. When the caller is outside tmux, prefer a user-selected or suitable existing session and create a new session only when none is suitable. Capture a stable pane target and read it before sending input.

Build the launch command from the executable and only arguments confirmed by local `--help`. Keep task text out of the shell launch command. Start the CLI through the same read, literal-input, confirm, and Enter sequence used for later messages.

## Send Requests

For every single-line request, follow this atomic sequence:

1. Read the target pane and confirm its identity and input state.
2. Type literal text without Enter.
3. Read again and confirm that the text reached the intended input field.
4. Send Enter separately.

When the caller runs inside tmux, include its pane ID or bridge label as a reply address. When the caller runs outside tmux, do not invent a reply pane; capture the target pane to collect responses.

For multiline requests through raw tmux, use the unique-buffer and bracketed-paste procedure in [tmux.md](references/tmux.md). Do not inject raw line breaks as separate key presses. If the selected bridge does not provide safe multiline input, resolve the native target and use the raw tmux procedure.

## Read, Reply, and Continue

Treat captured output as a terminal screen, not as a structured result, reliable progress record, or completion signal. Interpret the actual screen state before following up, supplying context, or reporting to the user.

When an incoming message contains a reply address, respond to that address through the selected control interface instead of replying only in the current pane. Apply the same read, literal-input, confirm, and Enter sequence.

Avoid high-frequency polling. Continue non-conflicting work and read the pane at moderate intervals or when its result becomes necessary.

## Wait and Recover Persistently

Keep the target pane while the Agent is running, waiting, or retrying:

- Treat a live Agent process that is executing, awaiting a response, or automatically retrying as still active. Do not impose a fixed timeout or retry limit unless the user explicitly sets one.
- Prefer the Agent's own retry for transient API, network, rate-limit, or upstream errors. Do not send `C-c`, kill the pane, or launch an equivalent duplicate solely because of a short-term error, temporary silence, or a long wait.
- Read the pane at a moderate frequency to distinguish automatic retries, input requests, task completion, and process exit. Perform only non-conflicting work while waiting.
- When the Agent requests feedback, clarification, or authorization, read the question and respond through the same atomic interaction sequence. If it requires a user decision or new authority, explain that need to the user and keep the pane waiting.
- When the Agent reports a goal blocker, inspect the cause. Supply missing context, answer questions, or address recoverable conditions first. If recovery requires user input or an external-state change, report the blocker while preserving any live or waiting Agent.
- End the Agent only after the enclosing user task or goal fully completes, the user explicitly requests termination, or strong evidence shows that it cannot continue and cannot recover within the authorized scope. Capture final output and process state before ending it.

Keep panes created for the current interaction until the enclosing user task or goal fully completes, even when an individual Agent request has returned. Reuse them for follow-up questions, revisions, review, or additional Agent steps. After full completion, capture the final state and clean up only panes created for the current interaction when no handoff or further review is needed. Do not close a pre-existing user pane unless the user explicitly requests it.
