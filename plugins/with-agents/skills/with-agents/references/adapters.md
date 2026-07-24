# Per-CLI input differences

This reference collects the little input knowledge an Agent needs when driving a CLI: how to submit, which key clears its composer, and how it starts a fresh conversation. The controller drives every CLI the same generic way — paste the body, press Enter, return the latest screen. The notes below give common defaults; confirm each against the actual screen because the controller has no per-CLI verification. Config registration belongs to [presets.md](presets.md); the message flow belongs to [messaging.md](messaging.md).

## Contents

- [What the controller knows about a CLI](#what-the-controller-knows-about-a-cli)
- [Submitting input](#submitting-input)
- [Clearing the current input](#clearing-the-current-input)
- [Starting a new conversation](#starting-a-new-conversation)
- [Reference routing](#reference-routing)

## What the controller knows about a CLI

`send` and `key` drive every CLI identically: they paste the body, press Enter, and return the latest screen. Whether the input landed the way you intended is something **you** judge from the returned screen — read it and decide, exactly as you would over raw tmux.

The only per-CLI knowledge that matters is what an Agent needs to act correctly: which key clears a CLI's composer, and how it resets a session. The controller does not track this per CLI, so treat the notes below as common defaults to try, and confirm against the actual screen.

## Submitting input

Ordinary Enter submits for Codex, Pi, and Claude in their default keymaps. For every body, `send` runs one `load-buffer` + `paste-buffer -p` and presses one Enter. A single-line body submits once. Whether a multi-line body stays one composer value depends on the target CLI's bracketed-paste support: Codex, Pi, and Claude hold a pasted multi-line body as one value in their default keymaps, but a generic or unknown CLI may treat an embedded newline as its own submit, so read the returned screen and confirm the body was not split. See [messaging.md](messaging.md).

`send` presses Enter unconditionally; it does not know or check which CLI is running. If a user has remapped Enter, read the returned screen — the controller cannot detect a custom keymap and reports only that tmux accepted the key.

## Clearing the current input

To clear a composer before typing, `read` first, then send the CLI's own clear key with `key`, then `read` again to confirm it is empty:

- most line-editing composers clear the current line with `C-u`;
- to abandon a running turn, `C-c` interrupts many CLIs;
- some CLIs clear or cancel the composer with `Escape`.

```bash
"$wa" read cx-worker
"$wa" key cx-worker -- C-u
"$wa" read cx-worker
```

Confirm from the screen — a key the CLI does not bind is silently swallowed.

## Starting a new conversation

To start a fresh conversation or clear context, use the CLI's own reset command with `send --no-header`; the slash command then reaches the CLI verbatim without a with-agents header:

```bash
"$wa" send cx-worker --no-header -- /new
"$wa" send cx-worker --no-header -- /clear
```

Read the resulting screen before sending the next task. A reset usually returns to a splash or empty composer, so confirm composer readiness from the screen.

## Reference routing

- [cli.md](cli.md) — the command index, global options, the JSON envelope, and representative error codes.
- [messaging.md](messaging.md) — the send header grammar, params, the input queue, and replying.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET resolution, the live window name, the route, and launch/wait/close.
- [presets.md](presets.md) — preset schema, pane naming, and the private Agent registry.
- [operation-states.md](operation-states.md) — the send input stages and the no-blind-replay rule.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an action.
