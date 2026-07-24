# Panes, routes, and lifecycle

This reference owns TARGET resolution, the live pane name, the with-agents route, the per-pane lock, the `launch`/`wait`/`close` lifecycle, and self-target as the only hard stop. Input stages and partial results belong to [operation-states.md](operation-states.md); message and reply flow belong to [messaging.md](messaging.md).

## Contents

- [One TARGET for every command](#one-target-for-every-command)
- [The live pane name](#the-live-pane-name)
- [The route](#the-route)
- [route, list, and list --detail](#route-list-and-list---detail)
- [The pane lock](#the-pane-lock)
- [Launch](#launch)
- [Wait](#wait)
- [Close](#close)
- [Self-target: the only hard stop](#self-target-the-only-hard-stop)
- [Reference routing](#reference-routing)

## One TARGET for every command

`read`, `wait`, `send`, `key`, `close`, and `route TARGET` share one `TARGET` grammar. A route occupies the target position itself; there is no `--route` flag. Resolution runs in a fixed order:

1. any input beginning with `with-agents:` is parsed as a route first — it never falls through to a native tmux target or a bare-name branch, and a route that fails to parse never falls back to a bare target;
2. a `%pane-id` or an explicit `session:window.pane` resolves through native tmux target handling;
3. any other bare string matches only a live tmux `window_name` — exactly one match succeeds, zero matches returns `target_not_found`, and more than one returns `target_ambiguous`.

A bare unknown name that matches nothing is **never** retried as the tmux active pane. A pane ID identifies a pane precisely; a bare name may be ambiguous because split panes in one window share a name.

A bare name, a `%pane-id`, and a `session:window.pane` are convenience forms resolved against the current command's tmux server; only a `with-agents:` route carries its own socket and stays valid across servers. When any of these convenience forms is rendered into a route, the controller fills in the canonical socket.

## The live pane name

A pane's public `name` is its live tmux `window_name`, read fresh on every command from `#{window_name}`. tmux emits that field vis-escaped (for example a literal backslash comes back doubled), so the controller decodes it back to the real name before it displays the value, matches a bare name, or renders a route; display, bare-name lookup, and route generation all share the same decoded value, so the name you see is the name you can type. The header, the route, and `list`/`read` all use that value. Rename a window with `C-b ,` (or `rename-window`) and the next command naturally reports the new name — there is no second name stored on the pane, and `pane_title` is never treated as the name. Split panes in one window share the name, so pane IDs carry precise location and a bare name may resolve ambiguously.

When a window name is empty or holds a character that cannot sit on a single-line header — a Unicode `Cc` control, or a `Zl`/`Zp` line/paragraph separator such as U+2028/U+2029 — the route falls back to `pane-<decimal-pane-id>` so the header stays exactly one line.

## The route

Parse a route with the with-agents text grammar below; URI parsing does not apply:

```text
with-agents:tmux?name=foo&pane_id=75&socket=/tmp/tmux-1000/default
```

The field order is fixed: `name`, `pane_id`, `socket`, optional `params`. `name`, `pane_id`, and `socket` are all required — a canonical route always carries its own absolute socket, so it addresses the same pane from any caller regardless of the current server. On the wire the pane ID is decimal digits; the controller adds the `%` when it calls tmux.

`name` and `socket` use minimal backslash escaping — never URL percent-encoding:

```text
\\  -> a literal backslash
\&  -> a literal &
\]  -> a literal ]
```

The parser treats only an unescaped `&` as a field separator and an unescaped `]` as the header terminator. A missing `socket`, an unknown escape, a duplicated field, an unknown field, a non-decimal pane ID, a non-absolute socket, or a CR/LF/NUL all return `route_invalid`. A `with-agents:` input that omits `socket` never resolves against the current server; the socket-qualified route is the only route form. The controller never runs `name` or `socket` through `urllib.parse` URL encode/decode.

The route connects to the absolute path in `socket`. The `name` is only a hint: after parsing, the controller finds the live pane by socket + pane ID, and does not reject it because the name has since changed, the pane process respawned, or the tmux server was rebuilt on the same socket path. A pane that no longer exists returns `target_not_found`.

A route parser also accepts an optional `params` field, so a receiving Agent can paste a route straight out of a message header into `send TARGET`. The resolver reads only the address fields and never propagates the old params; there is no implicit reply behavior. `route TARGET` strips any `params` from its output.

## route, list, and list --detail

`route [TARGET]` always prints a portable route qualified with an absolute socket:

```bash
"$wa" route cx-worker    # the target's portable, socket-qualified route
"$wa" route              # the caller's own route, derived from $TMUX/$TMUX_PANE
```

With no argument it derives the caller from `$TMUX`/`$TMUX_PANE` and fails `caller_identity_unavailable` when it cannot. With an argument it resolves the target by socket + pane ID; a pane still present under `remain-on-exit` resolves and prints its route, and only a pane that no longer exists returns `target_not_found`. Any `params` in an input route is stripped from the output.

`list`, `route`, and every ordinary pane result return the same canonical, socket-qualified route — the address never changes meaning with the caller's current socket, so a route you read from one result stays valid when you feed it back to a later command from any server. `list --detail` adds the repair fields — server PID, pane PID, and dead status — that the compact result omits; it does not change the route.

## The pane lock

A per-pane advisory lock (`flock`) serializes input and lifecycle on one pane: `send`, `key`, and `close` take it so their body-and-key sequences cannot interleave. The controller releases the lock before post-action observation, so concurrent sends all queue and each returns a latest snapshot that may already include a later send. `lock_timeout` and `tmux_timeout` bound controller operations against a hung backend; Agent task deadlines remain outside this contract.

A `launch --split TARGET` also takes the split **target** pane's lock and only then runs `split-window`, so a cooperating with-agents action cannot race the new pane onto a moved target (raw tmux, which bypasses the lock, is not covered). A non-split launch opens a fresh window or session and takes no existing pane's lock.

## Launch

`launch` creates a pane and starts an exact argv (see [presets.md](presets.md) for `--preset`/`--name-suffix` naming). Task text never goes in the argv; the controller serializes it to an internal helper that calls `execvp` — no shell reinterpretation. `--session` and `--split` are mutually exclusive.

`launch` blocks by default until it has a readable startup screen to return; `--no-wait` returns immediately, and `--ready-timeout SECONDS` bounds the wait (default 120). The wait saves a baseline before sending the argv, then polls:

1. still blank or no material change from baseline — keep waiting;
2. first material change — the process has produced an observable screen;
3. a short stability window with no further change — return the latest screen immediately;
4. no material change by the timeout — return `launch_timeout` with the latest snapshot;
5. still changing at the timeout — return the latest screen marked `stable=false`.

A settled screen confirms a readable startup observation: a splash, a folder-authorization prompt, a login prompt, or a composer. The calling Agent determines composer readiness from that screen and decides whether to send Enter, answer a prompt, or keep waiting.

`launch --preset PRESET` is the normal path; `launch --name NAME -- ARGV...` is the one-off direct-argv path. The naming rule differs by form: a preset auto-names from its `pane_name` or a generated `<prefix>-NNNN` when no name is given, a non-split direct argv requires an explicit `--name` because there is no preset to fall back to, and a split launch takes no name of its own. A `launch --split TARGET` does not create a window: the new pane's public name is simply the live `window_name` of the target's window, and the controller does not rename that window or reserve a pane alias. Combining `--split` with `--name`/`--name-suffix` is rejected before the pane is created. The pane stays alive with `remain-on-exit` after the process exits so you can read its final screen.

## Wait

`wait --timeout SECONDS --interval SECONDS` samples a bounded screen capture until the screen first changes, the pane's process exits or disappears, or the timeout expires. It watches the visible screen and whether the pane is still alive. `--interval` sets the sampling period; `--timeout` bounds this observation window. On timeout the stage is `unchanged` (the others are `changed`, `process_exit`). Cosmetic redraws can register as a change. Keep a working, waiting, or auto-retrying Agent alive; do not impose an arbitrary total-task retry cap or kill or duplicate it over brief silence, rate limits, or transient upstream errors.

## Close

`close` captures a final screen under the pane lock, then closes the one non-self pane it resolves. If the `kill-pane` itself fails it reports stage `close_state_unknown` — the pane may already be gone, so do not retry; resolve and read it instead. Any uniquely resolved non-self pane can be closed, so close a pane only after the enclosing task finishes, the user asks, or the process cannot recover within scope. Never close a pre-existing user pane without explicit direction, and never use a broad `kill-server`/`kill-session`/`kill-window` as a shortcut.

## Self-target: the only hard stop

Any uniquely resolved, non-self pane accepts `send`/`key`/`close`. Any CLI works the same way — an explicit `send` to a plain shell pane types the text and presses Enter, possibly running a command, so read the target first.

The one exception is self-targeting, decided by normalized socket + pane ID. `list`, `read`, and `route` may observe the caller freely; a mutating `send`/`key`/`close` refuses to drive the caller's own pane. A destructive action fails closed when it cannot prove a same-`%id` target lives on a different server; a target proven to be on another server is allowed.

## Reference routing

- [cli.md](cli.md) — the command index, global options, the JSON envelope, and representative error codes.
- [messaging.md](messaging.md) — the send header grammar that carries a route, params, and replying.
- [operation-states.md](operation-states.md) — the send input stages, lifecycle state-unknown results, and the no-blind-replay rule.
- [presets.md](presets.md) — preset schema, pane naming, and the private Agent registry.
- [adapters.md](adapters.md) — per-CLI clear-input and new-conversation differences.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an action.
