# Operation states and partial results

This reference owns the three technical states an action can land in — a completed tmux action, a partial action, and post-action observation — plus the no-blind-replay rule. These outcomes describe only tmux input. This reference defines no higher protocol state machine, and other references link here for stage definitions.

## Contents

- [Three technical states](#three-technical-states)
- [Why partial stages exist](#why-partial-stages-exist)
- [send input stages](#send-input-stages)
- [Lifecycle state-unknown results](#lifecycle-state-unknown-results)
- [Post-action observation](#post-action-observation)
- [Interruption](#interruption)
- [The no-blind-replay rule](#the-no-blind-replay-rule)
- [Recovery](#recovery)
- [Reference routing](#reference-routing)

## Three technical states

Every action resolves to one of three technical states:

1. **Completed tmux action** — tmux accepted the paste, key, or lifecycle command and the controller confirmed the resulting screen. This is success at the tmux layer only; it never claims the target TUI accepted, parsed, or acted on the input.
2. **Partial action** — text or a key may already have reached the pane, but the controller could not confirm the next step (a write timed out, a submit key failed, a post-action capture failed). The exact stage directs your inspection.
3. **Post-action observation** — the latest screen captured after the action, for you to judge. Use `changed` and `unchanged` as display-change diagnostics; neither reports success or failure.

## Why partial stages exist

tmux acceptance confirms only that tmux received bytes or a key. Target TUI acceptance, parsing, and action remain unknown. Writing text, submitting it, and capturing the result are three separate tmux operations, and any of them can fail or time out independently. The controller reports the exact stage it reached and never collapses these into a single boolean "delivered".

## send input stages

`send` runs the input sequence under one pane lock: re-check the target identity, capture a baseline, load the body into a buffer (`load-buffer`), paste it (`paste-buffer -p`), and send the submit key (`Enter`). The controller then releases the lock before capturing the bounded post-action screen. The reported stage:

| stage | meaning | safe to replay? |
| --- | --- | --- |
| `text_not_written` | `load-buffer` failed before any pane paste was confirmed; text presumed not delivered | yes — nothing reached the pane |
| `text_written_not_submitted` | the paste may already have reached the pane but submission is unconfirmed. Covers a failed or timed-out `paste-buffer`, and a non-timeout submit-key failure | no |
| `submitted_state_unknown` | the submit key may have reached the pane: the submit-key command timed out, or the post-action capture failed after the key was sent | no |
| `submitted` | tmux accepted the paste and submit key and a post-action screen was captured after the lock released; TUI acceptance is still not claimed | n/a (succeeded) |

All bodies take the same paste path regardless of length or newlines — there is no separate multiline gate.

## Lifecycle state-unknown results

`launch`, `key`, and `close` each have a state-unknown outcome when tmux acted but the controller could not confirm the resulting state (typically a capture failure or timeout after the mutation):

| command | state-unknown stage | meaning |
| --- | --- | --- |
| `launch` | `launch_state_unknown` | the pane may exist but the launch state could not be confirmed. When pane creation itself timed out, even the pane's existence is unknown |
| `key` | `key_state_unknown` | the key event may have reached the pane; the result could not be captured |
| `close` | `close_state_unknown` | the `kill-pane` command failed or timed out; the pane may already be closed |

In each case resolve and read the pane before another mutation.

`launch` also distinguishes a cleanly exited process: `executable_not_found` (exit 127) and `launch_process_exited` at stage `process_exited`, detected when the launched process exits during startup. The pane stays alive with `remain-on-exit`, so its final screen is inspectable. A launch that produces no material screen change before the ready timeout fails with `launch_timeout`.

## Post-action observation

`send` and `key` return the pane's latest screen after releasing the lock. The snapshot may already include a concurrent later send and cannot isolate the effect of one action. Judge it as an observation; use `changed` and `unchanged` only for display-change diagnostics.

## Interruption

A `KeyboardInterrupt` during a mutation is reported as a stable `interrupted` error mapped to the correct partial stage — an interrupt after text is written but before submit reports `text_written_not_submitted`; an interrupt after the submit key reports `submitted_state_unknown`; interrupts during launch/key/close report the matching `*_state_unknown`.

## The no-blind-replay rule

Never automatically resend a message or repeat a mutation after any stage where the effect may already have happened — `text_written_not_submitted`, `submitted_state_unknown`, any `*_state_unknown`, or an `interrupted` result. The text may already sit in the composer, or the key/submit may already have landed. Resolve and read the pane first; at most send the submit key alone if the intended text is positively present (see [tmux-recovery.md](tmux-recovery.md)).

## Recovery

Start from the returned `screen` tail and the `recovery` field. Run `doctor` when the backend or socket is in doubt. Only when the controller cannot safely finish an action, or a partial input needs manual inspection, fall back to [tmux-recovery.md](tmux-recovery.md) — raw tmux bypasses the pane lock and this stage reporting, so it is a deliberate last resort.

## Reference routing

- [cli.md](cli.md) — the command index, the JSON envelope, and how a stage differs from an error code.
- [messaging.md](messaging.md) — the `send` header grammar, params, and the input queue that produces these stages.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET resolution, the pane lock, and launch/wait/close.
- [presets.md](presets.md) — preset schema, pane naming, and the private Agent registry.
- [adapters.md](adapters.md) — per-CLI clear-input and new-conversation differences.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an action.
