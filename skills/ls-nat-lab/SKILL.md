---
name: ls-nat-lab
description: >
  Use when a co-op or path-layer test needs two games (or the game-free player lsprobe) behind NATs on this PC with
  no sudo: hole punching, STUN, "no direct path", direct versus relay fallback, symmetric or carrier NAT, a relay
  behind a router forward, coop_stun_public, coop_direct, conntrack or iptables counters, labctl.py check/probe/report,
  a [lab] case table, net steps, unshare -Urn, or the before/after of a path-layer change. Read before testing one on
  the internet, the Windows laptop or the LAN relay.
---

# Two games behind NATs on this PC

The lab puts two games (or two `lsprobe` players), a relay and a STUN server in network namespaces behind simulated
routers, with delay, jitter, loss and rate on each access link: no sudo, router, phone, Windows laptop or LAN relay. It
answers "what does the path layer do behind this NAT?" in seconds, before a hold or an internet session
(`skill://ls-relay-lan`, `skill://ls-windows-laptop`). `R` is the reports folder, defined in `skill://ls-relay-lan`.

```sh
N=$R/NatLab2-files                         # newest lab runner, cases, readers and game-free player
L="python3 -I -B $N/runner/labctl.py"      # $R/NatLab-files/README.md is the first quick start
```

The lab is **not** in the harness's `coop-play`: use `$N/runner/` (it has the `[lab]` table, the `net` step and the
`from = "menu"` anchor). `unshare -Urn` makes you root of a user and network namespace; `nsenter -n` into one of its
namespaces works only from inside that user namespace, so the lab is the whole runner re-executed under `unshare -Urn`
(`coopplay.py inner`), never a game entering a namespace. Inside it `/dev/nvidia*`, the render node, `nvidia-smi`,
`journalctl -k` and the run files work; this PC's own network is untouched (`nlab.py` refuses to run outside).

## 1. Cheapest level first

- `$L check PRESET` (12 to 25 s, no game): tests the lab itself (each router against the NAT tests, what each side's STUN
  answers name, the forward, the links' delay and loss, counters); exit 0 holds, 1 a check failed, 2 preset invalid. Run
  it after any `--set`. `$L presets` / `$L show PRESET [--set key=json ...]` list the topologies, `$L matrix` checks all.
- `$L probe PRESET --secs 45` (25 to 65 s, no GPU): two `lsprobe` players (the product's own session and path layer) join
  one room. Prints who joined, path events with times on both sides, datagram counters per class, what the routers
  dropped, what the relay saw; exit 0 only when the outcome equals the preset's `expect`. `lsprobe` has no menu, consent,
  chat, events or bodies and cannot host a relay.
- `python3 -I -B $R/NatLab-files/fake-game/rehearse.py PRESET [--out DIR]` (about 40 s): the hold's whole runner path
  (`hs-run.sh --inner` under `nsenter`, bridge, steps, pictures, counters) with a stand-in game, no GPU. It finds a broken
  `nsenter`, environment, control socket or counter; it says nothing about the game's network logic.
- A hold with two real games (section 4): 190 to 260 s a session.

## 2. A path-layer change before and after (seconds)

```sh
CHECKOUT=<worktree> OUT=<new dir>/fix nice -n 15 bash $N/probe-build/build-lsprobe.sh   # host/coop*.c + libjuice of THAT checkout
$L probe home-carrier-lanrelay --secs 45 --probe-bin <new dir>/fix/lsprobe --set expect=direct
```

Build the old head's `lsprobe` the same way, run both on the same presets and `--set`s: that table is the A/B. The
compile line names the host sources: add a file your checkout has, drop one it lacks. Probes use the pinned relay script
(`nlab.DEFAULT_RELAY_SCRIPT`): if the relay changed, copy `$N/runner/` and point it and the cases' `[lab] relay_script`
at the checkout's copy.

## 3. Read the presets right

- A preset's `expect` is what an older head did (relay behind a LAN relay). A head with the public-STUN fallback ends
  **direct** there and `probe` exits 1: not a fault. Pass `--set expect=direct|relay|any` in every probe and case.
- `coop_stun_public` must name the lab's STUN server (`INET['stun']`, `STUN_PORT` in `nlab.py`) in every case and probe
  against a head with the fallback, or the fallback asks a public server the lab cannot reach and the real case looks like
  the old failure. `probe` sets it (`--no-stun-public` removes it); a case sets it in `[sides.A.settings]` and
  `[sides.B.settings]`. `coop_direct = "on"` is a room setting; the default, off, sends only relay datagrams.
- The lab's "public" side must be addresses the game calls public: `pm_public()` in `host/coop_portmap.c` refuses 10/8,
  100.64/10, 172.16/12, 192.168/16, 169.254/16, 198.18/15 and the documentation ranges (192.0.2, 198.51.100, 203.0.113);
  `private4()` in `host/coop_path.c` (the fallback) treats the private ones as unreachable. A lab there makes a correct
  head look broken; `nlab.py` uses two ordinary public blocks. Read both functions in your checkout first.
- A LAN relay makes the joiner's direct path to the maker's router carry the relay's address, so the per-class counters
  count it as `relay`: use a public-relay preset when counters are the evidence, or `lab/flows-<router>.txt`.
- Access links are `tc netem` per site (`delay_ms` per direction). Not `coop_netsim.py` (some co-op branches only): a
  proxy in front of one game's relay address, it touches no direct path and hides the game from the relay.

## 4. Two real games in the lab (a hold)

A lab case is an ordinary runner case (`skill://ls-scripted-play`) plus a `[lab]` table; start from
`$N/case/gen_cases.py` (writes `nat2-*.toml` from its `BASE`, `HEAD`, `RELAY_SCRIPT` constants).

- `[lab] preset = "..."` plus overrides: `maker_kind joiner_kind` (`full restricted portres symmetric cgnat-cone
  cgnat-sym`), `relay` (`public lan host`), `forward`, `delay_ms jitter_ms loss_pct rate_kbit dup_pct reorder_pct` (a
  number for both sites or `{maker = 5, joiner = 60}`), `maker_lan joiner_lan maker_host joiner_host`, `expect`
  (`direct` or `relay` makes the path on both sides an expectation, `any` none), `relay_script`.
- Step `{do = "net", side = "B", action = "block"|"unblock"|"shape"|"rebind", seconds = .., delay_ms = ..}` changes that
  side's access link while the game runs.
- Two **separate** game copies (the games rewrite their options file): `setsid nohup cp -a --reflink=always SRC DST >
  log 2>&1 &` (a `( cmd & )` in a tool call dies with it; `ls -a` shows the dot-folders); delete their `coopplay-runs`.
- `[room] consent = "auto"` for a path-layer case (`bodies` at about 100 to 130 s; the two-press consent much later).
  Menu steps (`chat`, `accept`, `leave`) run on the game's menu clock, which starts at its first presented frame (5 to
  29 s after launch, not the runner's assumed 6): a pause, link cut or picture that must stand in a fixed relation to a
  typed line takes `from = "menu"` on the maker's side; otherwise menu steps use `from = "start"` only. A chat typed
  before the joiner is in the room, or while the other is dropped, reaches nobody. The trace (`HOS_COOP_TRACE=1`, set by
  the runner) shows a chat line as a 120-byte `tx DATA to <member>` repeated every 0.2 s until acknowledged; `rx message
  kind 17` on the sender dates the receipt.
- `[run] shot_every = 120` for a case that must show a chat line or a name label: only the periodic overlay pictures show
  them, a line is on screen about 8 s and the default 900 presents is about 15 s. `$N/auto_times.py <session>` lists
  when each picture was written. Look at every picture you cite.

```sh
python3 -I -B $N/runner/coopplay.py plan CASE.toml            # 0 REFUSED, 0 WARNING before you queue anything
python3 -I -B $N/runner/mkplan.py --name NAME --hold 1090 --out plan.json CASE.toml:225 ...   # :min_s of the hold
setsid --wait nohup env --default-signal=HUP python3 -I -B <frozen runner>/multihold.py queue plan.json --out <NEW dir> > queue.out 2>&1 < /dev/null &
$L report <OUT>/<item>/session           # verdict, path lines per side, counters, what the routers dropped
python3 -I -B $N/read_hold.py <OUT>      # one table per hold
```

- Queue under `skill://ls-hold-chain` (one waiter per gate: a lab hold and an internet hold run one after the other).
  Copy `$N/runner/` to a new folder and queue from the copy: `multihold.py queue` resolves its own path and snapshots its
  folder at admission, while the plan and case files are read again then. Its lock waits are 43,200 s (older copies
  14,400). Each item starts with `lab_prestep.py`: a broken lab skips that item in 12 s, not a session of two games.
- `coopplay.py inner` asserts the gate's marker variable, which only the gate sets: never set it by hand. Only a program
  that opens no GPU (the rehearsal's stand-in) may call `hs-run.sh --inner` without the gate.
- Kernel evidence: count only `NVRM`, `Xid` and `kmemsysDoCacheOp` lines of `session/kernel.txt` as the games'. A
  `segfault` line belongs to the program it names (compare its pid with the games'); `read_hold.py` also counts
  `segfault` and `general protection` and over-reports.

## 5. Evidence and clean-up

- Counters (`<session>/lab/`, `iptables-save -c`, conntrack, `ip -j -s link`) and what the lab does not model:
  `references/evidence.md`. A pass means the product's logic and the game's path hold behind these NATs, not every router.
- This runner's holders end with their process (`PR_SET_PDEATHSIG`) and its servers run under `timeout`; the first lab's
  `natlab.py` has no such protection. `coop_relay.py` processes of earlier labs (parent pid 1, a lab's bind address)
  may still run in namespaces nobody holds: not yours, harmless to a new lab; tell Main, never `pkill -f`.
