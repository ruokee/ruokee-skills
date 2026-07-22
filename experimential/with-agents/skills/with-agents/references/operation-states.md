# Operation states and partial results

This reference owns every atomic-operation stage, the `*_state_unknown` results, the no-blind-replay rule, and the recovery boundary shared across commands. Other references link here instead of restating stages.

## Contents

- [Why stages exist](#why-stages-exist)
- [send and request input stages](#send-and-request-input-stages)
- [Lifecycle state-unknown results](#lifecycle-state-unknown-results)
- [Interruption](#interruption)
- [The no-blind-replay rule](#the-no-blind-replay-rule)
- [Recovery](#recovery)

## Why stages exist

tmux accepting bytes or a key is not proof that the target TUI accepted, parsed, or acted on them. Writing text, submitting it, and capturing the result are three separate tmux operations, and any of them can fail or time out independently. The controller therefore reports the exact stage it reached and never collapses these into a single boolean "delivered". Every input result also carries `tui_acceptance: "unverified"`.

## send and request input stages

`send` (and the dispatch half of `request`) runs under one pane lock: revalidate the observed identity, write literal text or an adapter-gated bracketed paste, consume the observation, wait the adapter settle delay, send the submit key, and capture a bounded post-submit screen. The reported stage:

| stage | meaning | safe to replay? |
| --- | --- | --- |
| `text_not_written` | the literal/paste write failed; text presumed not delivered | yes — nothing was written |
| `text_written_not_submitted` | text may already have reached the pane; submit not confirmed. Covers a failed submit-key command **and** a timed-out write (a timed-out write is reported conservatively here, not as `text_not_written`) | no |
| `submitted_state_unknown` | submit delivery is unknown — tmux accepted the submit key but the post-submit capture failed, or the submit-key command itself timed out | no |
| `submitted` | tmux accepted text and submit key and a post-submit screen was captured; `tui_acceptance` stays `unverified` | n/a (succeeded) |

Multiline text on an adapter without verified bracketed-paste support fails early with `multiline_not_safe` at `text_not_written`, before anything is written.

For `request`, a dispatch failure maps the ticket phase: `text_written_not_submitted` or `submitted_state_unknown` become `dispatch_unknown` (the child may hold the request ID and the task may have arrived, so replies are still accepted); other failures become `aborted` (replies rejected). The reply TTL origin uses `dispatched_epoch`, then `dispatch_finished_epoch`, then `created_epoch`.

## Lifecycle state-unknown results

`create`, `launch`, `restart`, `key`, and `close` each have a state-unknown outcome when tmux acted but the controller could not confirm the resulting state (typically a capture failure or timeout after the mutation):

| command | state-unknown stage | meaning |
| --- | --- | --- |
| `create` | `create_state_unknown` | the pane exists but its initial screen/observation could not be confirmed |
| `launch` | `launch_state_unknown` | the pane and process exist but the launch state could not be confirmed |
| `restart` | `restart_state_unknown` | the pane identity or process may have changed; a new run may or may not be live |
| `key` | `key_state_unknown` | the key event may have reached the pane; the result could not be captured |
| `close` | `close_state_unknown` | the pane may already be closed |

In each case the pane exists (or may already be gone for `close`); resolve and read it before another mutation rather than repeating the command.

`launch`/`restart` also distinguish a cleanly exited process: `executable_not_found` (exit 127) and `launch_process_exited` at stage `process_exited`. The owned pane stays alive with `remain-on-exit`, so its final screen is inspectable and it can be corrected in place with `restart`.

## Interruption

A `KeyboardInterrupt` during a mutation is reported as a stable `interrupted` error mapped to the correct partial stage — e.g. an interrupt after text is written but before submit reports `text_written_not_submitted`; an interrupt after the submit key reports `submitted_state_unknown`; interrupts during create/launch/restart/key/close report the matching `*_state_unknown`. The observation is consumed wherever text may already have landed. During a v2 `reply`, once the event file is published an interrupt cannot roll it back: the event stays, and only the notification diagnostic records the interruption.

## The no-blind-replay rule

Never automatically resend a message or repeat a mutation after any stage where the effect may already have happened — `text_written_not_submitted`, `submitted_state_unknown`, any `*_state_unknown`, or an `interrupted` result. The text may already sit in the composer, or the key/submit may already have landed. Resolve and read the pane first; at most send the submit key alone if the intended text is positively present (see [tmux-recovery.md](tmux-recovery.md)).

## Recovery

Start from the returned `screen` tail and the `recovery` field. Run `doctor` when the backend or socket is in doubt. Only when the controller cannot safely finish an event, or a partial input needs manual inspection, fall back to [tmux-recovery.md](tmux-recovery.md) — raw tmux bypasses observations, ownership, the pane lock, and this stage reporting, so it is a deliberate last resort.
