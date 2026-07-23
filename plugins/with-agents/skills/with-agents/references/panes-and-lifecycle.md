# Panes, identity, and lifecycle

This reference owns pane identity, caller-scoped observation credentials, ownership, the foreign/self-target rules, the per-pane and per-request locks, the `create`/`launch`/`wait`/`restart`/`close` lifecycle, and runtime state with its garbage collection. Input stages and partial results belong to [operation-states.md](operation-states.md); message and event flow belong to [messaging.md](messaging.md).

## Contents

- [Targets and identity](#targets-and-identity)
- [Observation credentials](#observation-credentials)
- [Ownership and foreign panes](#ownership-and-foreign-panes)
- [Locks](#locks)
- [Create, launch, and restart](#create-launch-and-restart)
- [Wait](#wait)
- [Close](#close)
- [Runtime state and garbage collection](#runtime-state-and-garbage-collection)

## Targets and identity

A target may be an exact `%pane-id`, a native `session:window.pane`, a unique `@with_agents_name`, or an owned `run_id`. Names are discovery aids only. The controller binds every operation to the tuple `socket_path + server_pid + pane_id + pane_pid`, plus `run_id` for owned panes. An ambiguous name is rejected rather than guessed (`target_ambiguous`); a target that resolves to nothing is `target_not_found`.

Owned panes carry short, non-secret tmux options: `@with_agents_owner`, `@with_agents_run_id`, `@with_agents_name`, `@with_agents_preset`. Exact argv and observation/request state live in the private runtime root, never in pane options.

## Observation credentials

`read`, `wait`, `create`, `launch`, and a successful `restart` record an observation. `send`, `request`, and `key` consume one; foreign writes also require `--allow-foreign`. The credential is keyed by both the caller and the target:

- a tmux caller contributes its own server, pane, pane PID, and owned run ID;
- callers outside tmux should pass distinct stable `--caller-id` values when running concurrent independent controllers; the default is shared per OS user;
- an unresolvable tmux caller fails with `caller_identity_unavailable` rather than forging an unverified credential.

An observation is an operational interlock, not proof that a TUI is idle — it only attests that this caller last saw the same pane identity. Ordinary screen output does not invalidate it. A change in socket path, server PID, pane ID, or pane PID (or the owned `run_id`) invalidates it: the next consuming command fails with `observation_expired`, and a missing one with `observation_required`. `read` itself fails with `target_identity_changed` if the pane identity shifts between capture and re-resolution.

## Ownership and foreign panes

Existing panes are foreign. `list` and `read` are read-only and always allowed. `send`, `request`, and `key` require a current observation plus `--allow-foreign` for a non-owned pane (`foreign_write_denied` otherwise). `restart` and `close` require ownership unless `--force-foreign` is explicit (`foreign_restart_denied` / `foreign_close_denied`). The controller refuses to mutate the caller's own pane even with `--allow-foreign` (`self_target_denied`); if it cannot prove a same-ID target is a different pane, it fails `self_target_unverified`. A dead target process fails `target_process_exited`.

## Locks

Two kernel advisory locks (`flock`) serialize concurrent controllers:

- a per-pane lock guards input and lifecycle: `send`, `request` dispatch, `key`, `restart`, `close`, and each notification attempt take it, so they cannot interleave on one pane.
- a per-request lock guards event allocation and request state. Its lock file lives outside the request directory (under `runtime/locks`) so `reply`, `inbox`, and `gc` synchronize on the same inode even while GC removes the ticket.

Lock ordering is one-way: a path that needs both finishes and releases the request lock before taking a pane lock; the two are never nested. Lock acquisition and each tmux subprocess have finite operational timeouts (`lock_timeout`, `tmux_timeout`) that guard against a hung backend — they are not Agent task timeouts.

## Create, launch, and restart

`create` makes an owned shell pane and records an observation:

```bash
"$wa" create --name scratch --cwd "$PWD"
"$wa" create --name sidecar --split %3 --cwd "$PWD"
```

`launch` creates an owned pane and starts an exact argv (see [presets.md](presets.md) for `--preset`/`--name-suffix` naming). Task text never goes in the argv; the controller serializes it to an internal helper that calls `execvp` — no `eval`, no shell reinterpretation. `--session` and `--split` are mutually exclusive (`layout_source_conflict`). With no resolvable caller session, a single existing session is reused; multiple sessions require `--session` or `--split`; no session at all yields a minimal detached `with-agents` session.

A launch result returns the actual argv, the state-record path, an initial screen, and a `readiness` assessment (`unknown` for generic adapters or an unrecognized composer). A failed launch keeps the pane alive with `remain-on-exit` so you can read the final screen and correct it in place:

```bash
"$wa" restart reviewer -- agent-cli --corrected-option
"$wa" restart reviewer --preset corrected-preset
```

`restart` kills the current process and assigns a new `run_id`, which invalidates old observations bound to that pane. It rotates the identity before replacing the process, so a partial restart still fails an ownership or observation check closed. Notification route identity is intentionally narrower (canonical socket + server PID + pane ID only), so a restart in the same pane on the same server does not by itself disqualify a later callback — the current foreground-Agent check at callback time decides eligibility (see [adapters.md](adapters.md)). See [operation-states.md](operation-states.md) for `restart_state_unknown` and process-exit results.

## Wait

`wait --timeout SECONDS --interval SECONDS` samples a bounded screen capture and the process identity every `--interval` seconds until the first change, process exit, or identity replacement, or until the `--timeout` deadline expires. `--interval` is only the sampling period, not a deadline; on timeout expiry the result stage is `unchanged` (the other stages are `changed`, `process_exit`, `identity_changed`). Cosmetic redraws can register as a change. It records a fresh observation but does not define task completion, and must not be wrapped in an arbitrary total-task retry cap. Keep a working, waiting, or auto-retrying Agent alive; do not kill or duplicate it over brief silence, rate limits, or transient upstream errors.

## Close

`close` captures a final screen, then kills an owned pane and clears its runtime records. Close a pane only after the enclosing task finishes, the user asks, or the process cannot recover within scope. Never close a pre-existing user pane without explicit direction. Broad tmux kills (`kill-server`, `kill-session`, `kill-window`) are never a recovery shortcut.

## Runtime state and garbage collection

The runtime root is `${XDG_RUNTIME_DIR}/with-agents/` (mode-`0700` dirs, mode-`0600` files) holding owned launch records, observations, locks, requests, events, notifications, and managed results. It never stores full task prompts or transcripts. Removing the runtime dir — logout that clears it, or reboot — invalidates in-flight tickets. Without `XDG_RUNTIME_DIR` (typical on macOS) state falls back to `${XDG_STATE_HOME:-~/.local/state}/with-agents/`, which shifts the lifetime from session scratch to persistent user state; in fallback mode the controller auto-removes terminal requests older than seven days and never ages out pending ones.

`gc` removes terminal requests (a v2 stream with a terminal event, a v1 replied ticket, or a dispatch-aborted request) immediately. `gc --stale [DAYS]` reports pending requests older than the given age (default 30) and only deletes them with `--delete-stale` (`--delete-stale` requires `--stale`). Pending streams — no event, only nonterminal events, or an expired TTL — are never auto-deleted; they are reported and removed only on explicit request.

`WITH_AGENTS_RUNTIME_DIR` and `WITH_AGENTS_CONFIG_DIR` (or `--runtime-dir` / `--config-dir`) override the roots for isolated testing. Do not point them at a shared or untrusted directory.
