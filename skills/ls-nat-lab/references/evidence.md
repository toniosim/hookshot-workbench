# What the lab counts, and what it does not model

`N` and `L` are defined in `skill://ls-nat-lab`.

## The `lab/` folder of a lab session

`<session>/lab/` holds `counters.csv` (every 5 s), `summary.json` (the deltas, the classes, the facts the case's
`file_json` expectations read), `routers.json`, `flows-<router>.txt`, `what-the-stun-servers-saw.json`, `inet.json`
(forwarding counters of the internet namespace) and `relay.log`. `$L report <session>` prints one page from them;
`$N/read_hold.py <hold>` one table per hold.

- `counters.csv`: every link end (a game's `eth`, a router's WAN, the internet's end, the carrier and phone links), and
  per game namespace the datagrams sent and received by class: `relay` (the relay's address, or the hosting game's own
  relay port), `private` (RFC 1918, shared address space or link-local: a LAN candidate nobody outside can reach, a "dead
  candidate"), `public` (anything else that is not the relay: a direct path), `loopback`.
- `summary.json`: `unsolicited_dropped_packets` per router (packets in that no pinhole admitted), `relay_log_addresses`
  (the addresses the relay saw), `relay_drops`, `relay_rejoins`, `stun` (what each side's STUN server named),
  `direct_path_bytes` per side and `joiner_direct_share_out`.
- Where the numbers come from, each read inside the lab's own namespaces: `iptables-save -c` (per-rule packets and
  bytes: what a router dropped as unsolicited, what its forward admitted); `/proc/net/nf_conntrack` (that namespace's
  table; it carries bytes only with `sysctl net.netfilter.nf_conntrack_acct=1`, which the lab sets); `ip -j -s link`
  (the per-namespace link counters: `/sys` shows the wrong namespace's devices).
- With a LAN relay the joiner's direct path goes to the relay's address (the router's forward) and counts as `relay`;
  the routers' conntrack tables (`flows-<router>.txt`) carry the direct flow's exact packets and bytes.

## Not modelled

Linux conntrack and netem stand in for a router and a link. A pass means the product's logic and the game's whole path
run correctly behind these NAT behaviours, not that it works on every router. Absent: real routers' port allocation
(Linux masquerade keeps the source port when it is free, many routers do not), mapping and filtering timeouts (30 s
unreplied, 120 s after a reply here), hairpinning, carrier port blocks, ICMP handling, IPv6, UPnP/PCP/NAT-PMP (no
responder: `coop_portmap=1` logs `gateway mapping timed out`), the PC's and the relay host's firewalls, bufferbloat,
bursty loss, asymmetric links unless set, Wi-Fi, path-MTU limits, Windows, the real relay's wrapper. Both games, the
relay and the lab share this PC's CPU, memory, one GPU and one clock; a loaded PC shows as round trips above the
netem delay. `$R/NatLab.md` section 6 has the full list.
