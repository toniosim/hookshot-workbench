---
name: ls-relay-lan
description: >
  Use before a co-op session or proof that goes through the shared relay on the LAN relay host, and when installing,
  updating, probing or reading that relay: "too many rooms are open from this network", the 2-rooms-per-network rule,
  the 600-second linger, STUN answers, relay.log, the room guard (`<relay>-room-guard.py`), probe-relay.py, SHA256SUMS,
  CHANGES.txt, the user-level systemd unit. Another worker's session can make your Make fail; read this first.
---

# The shared relay on the LAN relay host

One pinned Python co-op relay (`coop_relay.py`, byte for byte from the port's scripts folder) runs on the LAN relay host
as a user-level systemd service for every worker and both PCs. Workers have no sudo there: install, update and restart
happen only on the user's word (both updates so far were), and every change is a line in `~/longshot-relay/CHANGES.txt`
with its undo. `R=/home/tonesi/hookshot-wt/reports`. `<relay>` stands for the host's SSH alias: it is written down
once, in the section "Hosts" of `$H/LOCAL-NOTES.md` (`H` as in `skill://ls-workbench`), together with the install report
and the STUN update report that hold the evidence and the probe scripts (their folders are the "install files" and "STUN
files" below). Live state after 15 November 20:30 was not re-read for this page.

## The rooms rule: why your Make can be refused

- A new room is refused when the sender's IPv4 /24 already has 2. The home LAN is one /24, so **every worker and both PCs
  share two rooms**. The game says `too many rooms are open from this network; wait for one to close (10 minutes) or join
  one`.
- A room that anyone besides its maker joined stays open **600 s after the last member leaves** (log: `closed, empty for
  600 s`); a room nobody joined closes when its maker leaves. Two workers' sessions within ten minutes can refuse each other.
- A **room probe is a shared room**: `probe-relay.py` makes and joins one, so it holds a slot for 600 s. Probe a room only
  at 0 open rooms; for liveness use the STUN probe or read the log.
- Before any session through the relay run the read-only guard as a case `pre_step`:
  `R/Soak4-files/chain/<relay>-room-guard.py OUT.json` (the best copy; others keep an old regex that misses
  `closed, its maker left`). It counts open rooms from the log, sends a STUN probe, waits up to 170 s, and exits 3 so the
  runner stops before the session starts. It reserves nothing: another Make can still race it.
- The cost of ignoring it was a refused Make after a 49-minute queue and an 8.8-minute hold.

## Read it

```sh
ssh <relay> systemctl --user show longshot-relay.service -p MainPID -p ActiveEnterTimestamp
ssh <relay> tail -n 300 ~/longshot-relay/relay.log
```

Lines: `room X created (N rooms)`, `joined as member`, `left`, `dropped`, `closed, empty for 600 s (N rooms)`, `closed, its
maker left before anyone joined`; N counts rooms open on the whole relay. Each timestamp carries its offset (the relay
host is two hours behind this PC). STUN, DATA and addresses are not logged. The relay never answers more than 1.1 times
the request's size (the IPv4 answer is 32 bytes), so a bare 20-byte STUN request gets nothing: add a SOFTWARE attribute
(type 0x8022) as `R/InternetSession-files/probe/laptop_probe.py` does. A fake STUN server (a test fixture's) must answer
with type `0x0101`; `0x0001` is a request and is ignored without a word. The answer budget is 20 per second for the LAN
with a burst of 100. (`ssh` prints "Ran in a copy of the busy session shell" at the end of its output: that is the
tool's note, not the relay's.)

Scripts: `probe-relay.py` in the install files (room probe; `hs-nocore.sh <python> -I -B probe-relay.py --source <any
coop_relay.py>`; its client names are fixed, so two workers' probes differ only by room id and time),
`stun-probe.py` in the STUN files (three answered and four silent STUN cases, no room),
`R/CrossPlay16-files/coop-play-src/cprelayprobe.py` (the room probe with `--script --host --port --timeout`).

## A player outside the LAN (the user's word first)

- The relay host's firewall rule for the relay port admits the LAN /24 only, so a router forward alone cannot work: the
  outside player's packets die at the host. The forward and a firewall rule for the outside player are both the user's to
  add and to remove.
- First sign of a live forward behind a blocking firewall: a `UFW BLOCK` line with `DPT=24680` from the outside player's
  address in the host's kernel journal (`ssh <relay> "journalctl -k --since '10 min ago' --no-pager | grep DPT=24680"`;
  group adm may read it; ignore lines whose `SRC=` is on the LAN). Allow rules are not logged: silence does not prove the
  rule.
- The relay's STUN names the sender's address as the relay sees it: a maker on the relay's own LAN is told its LAN
  address, `coop_direct_lan=0` drops only host candidates, and that private address stays the whole offer, so no
  internet player can go direct to that maker. A head with the public-STUN fallback (`coop_stun_public`) asks a public
  server instead; one without stays on the relay. Reproduce either in `skill://ls-nat-lab`, not on the internet.

## Layout, install and update (the user's word first)

`~/longshot-relay/` is mode 0700 and holds `coop_relay.py`, `run-relay.py` (the wrapper: 8 rooms in all, 2 per network,
addresses not logged), `start.sh`, `longshot-relay.service`, `SOURCE.txt`, `SHA256SUMS` (those five files),
`CHANGES.txt` and `relay.log` (1 MiB, 3 backups). Only the user-unit symlinks sit outside it. Enable with
`systemctl --user enable --now ~/longshot-relay/longshot-relay.service` (lingering is already on). The one firewall
rule (UDP 24680 for the LAN /24) was the user's own; a read-only preflight is `preflight.txt` in the install files.

Update, in order, none of it without the user's word:

1. Confirm 0 open rooms from the log: a restart drops every room.
2. Upload the new script as `coop_relay.py.new`. Keep dated copies `coop_relay.py.<oldsha>-<date>`, `SOURCE.txt.<...>`
   and `SHA256SUMS.<...>`.
3. Move the new file in; rewrite `SOURCE.txt` and `SHA256SUMS`; run `sha256sum -c SHA256SUMS`.
4. Append one `CHANGES.txt` line: time, the user's word, the undo.
5. `systemctl --user restart longshot-relay.service`; probe (STUN first, a room only at 0 rooms).

The wrapper needs no edit for a new relay script; to turn STUN off set `stun=False` in `run-relay.py`. The pinned script's
hash equals the `coop_relay.py` of the co-op branches' scripts folder when the relay is current: compare before a proof that
depends on STUN or the room rules. Open: no receive-loop rate limit, no source allowlist beyond the LAN rule, no probe
`--tag` option, no slot reservation.
