# Agent detection and notification adapters

This reference owns how the controller detects a caller Agent, the best-effort notification policy, composer recognition, `Enter` semantics, and version diagnostics. It is read only when adding or debugging an Agent, or when analyzing why a callback did or did not inject. The event model and `reply` outcomes belong to [messaging.md](messaging.md); config registration belongs to [presets.md](presets.md).

## Contents

- [Best-effort principle](#best-effort-principle)
- [Detecting the caller Agent](#detecting-the-caller-agent)
- [Route identity for callbacks](#route-identity-for-callbacks)
- [Notification strategy](#notification-strategy)
- [Composer recognition and danger vetoes](#composer-recognition-and-danger-vetoes)
- [The doorbell](#the-doorbell)
- [Version diagnostics](#version-diagnostics)

## Best-effort principle

Outcome persistence and caller wake-up are two separate facts. When `reply` publishes an event, the outcome is durably spooled (`outcome_persisted`); the doorbell only ever claims an *attempt* and the underlying tmux acceptance. A notification is a wake-up preference, never a delivery guarantee and never a dispatch gate.

A doorbell deliberately injects into the verified caller route — that route is the caller pane the request registered, and waking it is the whole point. The controller keeps only the restrictions that map to real destructive or identity risk: it will not inject into a pane whose route identity no longer matches, into a foreground process that is not a registered Agent, or into a screen showing a clear danger state. "Unverified", "newer version", and "presentation-style change" are **not** reasons to refuse. (The separate rule that a caller and child must not be the *same* pane is enforced at `request` dispatch, not here; see [messaging.md](messaging.md).)

## Detecting the caller Agent

The adapter kind is always resolved by executable, not by scanning task text, but the two contexts that need a kind resolve it from different evidence. The `send`/readiness detector (`detect_agent`) trusts the owned pane's recorded launch `argv[0]` first and only falls back to a live process scan, because it is describing the process this controller itself started. The callback detector (`notification_strategy`) deliberately ignores the owned launch record — a record can be stale after a respawn — and requires the *current live foreground process* to match a capability or registry definition; it never injects on the strength of a launch record alone. In either context the executable is taken from the process's own path or its immediate launcher's first non-option argument for `env`, `node`, `nodejs`, `python`, `python3`, and a task argument that merely mentions `codex`, `pi`, or `claude` cannot register a type.

Built-in definitions (also the built-in `pane_prefix`):

| agent_type | pane_prefix | executables |
| --- | --- | --- |
| `codex` | `cx` | `codex` |
| `claude` | `cc` | `claude` |
| `pi` | `pi` | `pi` |

Users may register more agent types in `config.json` (see [presets.md](presets.md)). Registration has exactly two effects: `preset save/update` can record the new `agent_type` and generate a suffix pane name, and a callback whose live foreground process matches the registered executable may use **generic** best-effort notification. Registration never grants the Codex/Pi specialized recognizer, multiline safety, or any TUI-acceptance claim.

## Route identity for callbacks

At callback time the controller re-resolves the caller route. Notification identity is deliberately narrower than the observation identity in [panes-and-lifecycle.md](panes-and-lifecycle.md): it compares the canonical socket path, server PID, and pane ID only. A replaced server or a vanished pane stops the attempt (`caller_identity_mismatch` / `caller_unreachable`); the same pane ID on the same server is allowed even if its process was respawned, because the foreground-process check below decides whether it is still an Agent. Pane PID and run ID are still recorded for diagnostics but are not a callback upper bound.

## Notification strategy

After the route matches, the controller inspects the current foreground process under the caller's pane lock and picks one mode:

| Current foreground | Mode | Behavior |
| --- | --- | --- |
| Codex or Pi (built-in specialized adapter) | `capability` | Use the specialized recognizer, settle delay, and submit strategy |
| Any other registered Agent — user-added *or* built-in Claude — with no specialized adapter | `generic` | Best-effort opt-in: one line of text plus `Enter`, marked TUI-unverified |
| Not a registered Agent (e.g. back to a shell) | `skip` | Keep the spool, `caller_not_agent`, no injection |

Generic mode covers every registered Agent that has no specialized adapter, which includes the built-in `claude` definition, not only user-added types. If `config.json` is invalid, the built-in definitions remain usable — built-in Agents are still recognized and still reach `capability` (Codex/Pi) or `generic` (Claude) mode. Only a callback that would depend on a *user-registered* executable degrades to spool with an `invalid_agent_config` diagnostic; that degradation never makes `reply` fail and never re-becomes a dispatch gate.

In `capability` mode the controller captures an escape-preserving screen and classifies the composer:

| State | Action |
| --- | --- |
| `idle` | Type one doorbell, wait the settle delay, send `Enter` (`submit_key`) |
| `busy_queueable` | Type one doorbell, send `Enter` (`busy_key`); delivered at the next safe boundary, not on task completion |
| `unsafe` | Keep the spool, `unsafe_callback_state`, no injection |
| `unknown` | Keep the spool, `unknown_callback_state`; missing danger text is not proof of readiness |

Generic mode sends one line of text plus `Enter` without composer classification; the target silently swallowing or non-destructively interpreting that `Enter` is an acceptable quiet failure.

## Composer recognition and danger vetoes

Recognition is positive per adapter, never a danger-pattern complement:

- **Codex** accepts an empty composer only from an exactly empty prompt row or its dim-styled placeholder row, parsed from SGR *semantics* (dim vs. real text), not a fixed escape-byte profile. Foreground/background color and reset changes that do not change input semantics are tolerated — including the Codex 0.145 background-color placeholder. A prompt row with real typed text is `unsafe`. A nearby busy marker labels `busy_queueable`.
- **Pi** recognizes the empty composer as a blank line inside the final horizontal border pair. A nonempty bordered composer is `unsafe`; a nearby `Working` spinner above the border labels `busy_queueable`.

Danger patterns (permission confirmations, single-key selects, "press Enter", existing real input) are **vetoes only**: they can force `unsafe`, never promote `unknown` to safe.

## The doorbell

The controller-managed doorbell is a single control-free line:

```text
[with-agents reply request=<id> seq=<n> status=<status>] <message> [file=<managed-path>]
```

Each published event makes at most one doorbell attempt. A failed callback, an interrupted process, or a missing notification diagnostic does not retry and does not block later events from each making their own attempt. Concurrent doorbells may display out of `seq` order; the authoritative order is always the spooled event `seq` — read `inbox <request-id>` when exact order matters. A child that chooses its own transport (direct pane message, CLI-native notification) may use free text and need not copy this format.

## Version diagnostics

CLI `--version`, the forward-tested version, and tmux extended-key state are diagnostic only, surfaced by `doctor` (`checks.notification`) with `version_gate: false`. A failed or unknown version query never blocks dispatch or callback, and an on-disk executable update is not the same as the running pane process changing. The current forward-tested references are Codex `0.145.x` and Pi `0.80.x`, but a higher version is not rejected on version grounds.

Version gating also cannot detect a user-customized `Enter` keymap. The adapters assume default ordinary-`Enter` steering. `Enter` does not interrupt an in-flight tool byte-for-byte: tmux writes it to the caller's PTY and the caller consumes it at its next safe tool-call or turn boundary, without waiting for the enclosing goal to finish. Completion-delayed follow-up keys (Codex `Tab`, Pi `Alt+Enter`/`M-Enter`) are not used because they can be delayed through goal completion — too late for a prompt doorbell. If a specific build's `Enter` is proven to cause a clear wrong action, record a narrow `known_incompatible` note in code with evidence; there is no "reject everything above the last tested version" ceiling.
