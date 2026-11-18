---
name: ls-windows-laptop
description: >
  Use when a task runs, stages, captures or tests anything on the remote Windows laptop (the second PC of a two-PC
  co-op session, a Windows title run, fixtures on Windows, a cache comparison): the laptop runner, run-one.py,
  hs-run.ps1, window-shot, "stage, warm, run, fetch, restore caches", the 480-second cap, the ssh command-line limit,
  PowerShell quoting, who authorises it. The local Linux workstation stays windowless; this is the only place a real
  window is run.
---

# Windows runs on the Windows laptop

Fifteen reports ran the same machinery and each rediscovered it. There is no README in the tools folder; this is it.
`R=/home/tonesi/hookshot-wt/reports`; `T` is the laptop's tools folder, `R/tools/<win>`. `<win>` stands for the
laptop's SSH alias: it is written down once, in the section "Hosts" of `$H/LOCAL-NOTES.md` (`H` as in
`skill://ls-workbench`), and defined in the SSH client configuration, outside the repository. File names that carry it
are written the same way (`<win>-run.py`). The remote files (`C:\ls\...`) were not re-read for this page.

## Who may use it

The windowless-only rule is for this Linux workstation. A real-window run on the laptop happens only because the task text says
so, and anything beyond the task needs the user's or Main's word each time: a hold over 480 seconds, a change to the
wrapper or to Windows, a firewall rule, a game start or a copy (each separately). Never script a login or unlock, restart
the PC, touch another lane's builds, or replay an uncertain start (the tools refuse a reused tag). Workers never post.
Every change on the laptop goes into the ledger `C:\ls\CHANGES.txt` with its undo; copy `cpwin.install_helpers` in
`reports/Soak4-files/runner/cpwin.py` (ledger line first, dated backup, scp, sha256 read back).

## The tools (`T`)

- `<win>-run.py` (Linux side, library and CLI): `start <copy> <tag> [secs=450] [--window --prepare --no-auto-shots --user
  --input --client --env K=V --output-size --window-size]`, `status|ready|stop|wait|fetch <tag>`, `ctl <tag> <bridge
  cmd>` (`launch` refused), `shot|window-shot <tag> x.png`, `stop-probe <tag> taskkill|console-c|console-close`;
  `remote(code, timeout)` runs a PowerShell script over ssh.
- `hs-run.ps1` (remote entry, `-Action Start|Status|Stop|Wait|Fetch -Tag`) registers the scheduled task
  `<project>-<win>-<tag>`; `run-worker.py` is its body (Job Object kill, quit at deadline minus 10 s, exit 124 on kill);
  `wait-ready.py` only does the control-pipe handshake: after it, require an observed menu or play state and advancing frames.
- Not in `T`: each lane copy-edits `run-one.py`, `cache-state.py`, `stage-windows.py`, `transfer-stage.py`,
  `verify-stage.py`, `stage-save.py` from `reports/Test443-files/` or `reports/Test526-files/`, and the co-op adapter
  `cpwin.py` (newest in `reports/Soak4-files/runner/`). Copy the newest, read it, change the pins. Soak4 patched the live
  wrapper on the laptop for long tags, so the copies in `T` can be behind the machine.

## The procedure

1. **Stage.** Cross-build on Linux with `reports/tools/wincross/wincross.sh <commit>` (writes `receipt.json`; give it a
   version checkout, or the Windows build logs `unknown (source ...)`). `stage-windows.py` writes the payload and
   `MANIFEST.json/.sha256`; `transfer-stage.py` preflights (destination absent, no game running, the data folder
   present, a ledger line), streams a tar over ssh and reads each sha256 back; remote `verify-stage.py` takes
   `game.lock` and checks hashes. Saves: `stage-save.py` (manifest verify and a pristine copy).
2. **Warm.** `run-one.py <tag> warm` runs the game with a window (512x288 is enough), the remote controller, `wait`, `fetch`.
   Repeat until a walk shows no first-use translations; freeze once with `cache-state.py snapshot` (cache, driver state
   and `longshot_options.ini` into a one-shot baseline folder).
3. **Run.** `run-one.py <tag> visual|fps` first runs `cache-state.py restore <tag>` (rmtree, copytree, hash check, a
   receipt; no replay), then the game, wait, fetch; it asserts exit 0 and not `hard_killed`. Use `--no-auto-shots` for
   any run whose speed matters. The wrapper sets `RX_VK_SHOT_EVERY` and other variables itself (`run-worker.py`): read it
   before relying on `--env`.
4. **Fetch and judge offline.** `fetch` takes top-level `*.json`/`*.txt` and `shots/` into
   `reports/WinBox-files/runs/<tag>`. Whether a game finished is decidable from `*-launcher.json` (`wait` and `fetch`
   actions with exit 0) plus the remote `manifest.json`/`result.json`.
5. **Restore.** The game rewrites `longshot_options.ini` at its first start and at every menu close: save the original,
   restore it at the end, ledger it. A test that appends settings leaves duplicate keys: replace the whole file.

## Limits that bit

- **480 s game cap** in three files (`hs-run.ps1`, `<win>-run.py`, `run-worker.py`; also `<win>-case.py`, `cpwin.py`). Only a
  `crossplay15-*` tag may go to 1,100 s; a ten-minute two-PC session needs that tag and Main's word.
- **ssh command line**: `remote()` base64-encodes UTF-16 with no guard. About 8,000 encoded characters run; 8,100 fail
  with "The command line is too long" (a launch of 8,732 wasted a 7,573 s queue wait). Split a long read-only script, scp
  it and run the file, or send it on ssh stdin to the laptop's Python (`ssh <win> "C:\ls\tools\python\python.exe -I -
  ARGS" < script.py`: nothing is written there; `reports/InternetSession-files/probe/probes.py` does it). Only `cpwin.py`
  guards the limit (7,600) and retries "exec request failed on channel 0".
- **PowerShell traps**: an apostrophe inside a single-quoted string kills a helper at `[scriptblock]::Create` before it
  runs (double it, lint every ledger sentence; `firewall-step.py` refuses a second try, so recover with a ledger line,
  delete the failed helper, apply again). Windows PowerShell 5 strips JSON quotes passed to a native CLI: send the bridge
  command through encoded Python. `Start-Process` dies with the ssh session; `Win32_Process.Create` survives.
  `Set-Content -Encoding UTF8` writes a BOM: read with `utf-8-sig`.
- **File sharing**: a reader of a log or of the atomically replaced manifest opens with Read|Write|Delete sharing, or it
  makes the writer's replace fail (WinError 5; the wrapper now retries, but your own reader must share).
- **Pictures**: Windows Graphics Capture of the one visible window of the game's pid (`window-shot`), never the desktop;
  Pillow/PrintWindow returns black for a Vulkan window. It needs the console session active and unlocked; "found 0"
  visible windows can last a whole session while bridge steps still work, so probe one picture before a long hold. Bridge
  `shot` omits the Insert-menu overlay. A 1280x720 window is a DPI-scaled swapchain: record both sizes.
- **Session 0**: ssh runs in session 0 (no window, no firewall prompt); desktop runs belong to the scheduled task.
- **Windows log lag**: the log reaches this PC by a poll over ssh, so its stamps lag the game by 1.5 to 6 s and one poll
  can stamp several lines alike (seen: an `is away` / `is back` pair): bracket, do not align, and date such a pair from
  the other side's frame gaps and the relay log. The runner checks a Windows side's `leave` and
  `accept` log line once, at the planned time plus the step's span plus 3 s (`verify_menu_step` in `cpsession.py`), so a
  late log fails a clean step: `reports/InternetSession-files/runner/cpsession.py` waits up to 12 s for `leave`
  (`accept` is not covered). A `chat` expectation widens its acknowledgement window with `win_slack_s` (default 4; a
  two-hour run saw 5.9 s of lag): give a Windows pair 8 or more.
- **Another network**: the SSH client configuration reaches the laptop over its LAN address. From a hotspot every `ssh`
  and `scp` needs `-o HostName=<tailnet address>` (the pinned known-hosts file has a key for both addresses): put a PATH
  shim named `ssh` and `scp` that adds it for the laptop's alias (`reports/InternetSession-files/bin/`); the wrapper's
  `OPTS` and the runner's helpers call plain `ssh`/`scp`, so the shim is all they need.
- **Metered link**: the evidence copy of a run folder with automatic pictures is hundreds of MB (216 MB, base64 over ssh,
  in a 15-minute run). Use `--no-auto-shots` (case: `win.no_auto_shots`, the default for a soak tag) and fetch only
  `*.json`, `*.txt` and named pictures; `win.defer_fetch` (`reports/InternetSession-files/runner/cpwin.py`) copies nothing
  of the run folder. Count bytes from the adapter (`Get-NetAdapterStatistics` before and after): once, the raw-socket
  counter of `reports/InternetSession-files/watch/net_watch_internet.py` missed about 110 MB of the adapter's transmit.
- **Shader preparation**: a fresh one does not finish on the laptop's Arc GPU: the one unlimited run failed (exit 4; its
  one-shot claim is spent) and a bounded one reached 399 of 38,809 programs in 392 s. A task that asks for one there
  cannot be met as written: say so and ask Main how to cover that step.
- **Undoing the long-tag patch** (`reports/Soak4-files/<win>-long/undo.py`): run `--dry-run` first and pass `--stamp` of
  the apply whose dated copies (`<name>.before-soak4-<stamp>` in `C:\ls\scripts`) exist. Without `--stamp` it takes the
  newest receipt, and a second `apply` that found the files patched writes an `unchanged` receipt with no copies, so the
  undo refuses. It needs the ssh shim above when the laptop is on a hotspot.
- A Windows cross-built fixture runs there (the laptop has Python at `C:\ls\tools\python`); `record.py` with `fixture_cc.py`
  in `reports/WinFixtures-files/tools/` is a working route to execute the co-op drivers. The syntax check in
  `ls-workbench` does not run them.
