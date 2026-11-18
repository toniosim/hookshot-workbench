#!/usr/bin/env python3
"""Propose and apply labels for every open pull request on the LS forge.

  pr_tags.py plan  [--numbers N ...] [--out DIR]     read the forge, write DIR/plan.json and DIR/plan.md; changes nothing
  pr_tags.py apply --plan DIR/plan.json [--go]       add the planned labels (dry run without --go)

Only adds labels, never removes one. A scope a pull request already has a label in (kind/, priority/, area/,
platform/, gpu/) is left as it is; the proposal for it is only reported. Maintainer and bot labels (beanstalk:,
ci: approved, preview, testing wanted, needs measurements, good first issue, help wanted, status/) are never set.
Every forge call runs under /tmp/longshot-forge-auth.lock, so no other process renews the sign-in at the same time.
"""
import argparse
import fcntl
import json
import os
import re
import sys
import time

LSMAIN = "/home/tonesi/hookshot-wt/longshot-main"
REPO = "MagicBeanDev/Longshot"
LOCK = "/tmp/longshot-forge-auth.lock"
sys.path.insert(0, os.path.join(LSMAIN, "scripts"))
os.chdir(LSMAIN)
import forge  # noqa: E402  (the project's own forge client: api(), token())

SCOPES = ("kind/", "priority/", "area/", "platform/", "gpu/")
KIND = {"feat": "kind/feature", "fix": "kind/bug", "perf": "kind/performance", "docs": "kind/docs",
        "chore": "kind/chore", "build": "kind/chore", "ci": "kind/chore", "test": "kind/chore", "tests": "kind/chore",
        "refactor": "kind/chore", "style": "kind/chore", "revert": "kind/bug"}
CC = re.compile(r"^\s*(?:WIP:\s*)?(\w+)(?:\([^)]*\))?!?:", re.I)

# area by changed path (lower-cased); tests and docs only count when nothing else matched
AREA_PATH = [
    ("area/upscaling", r"dlss|fsr|xess|upscal|framegen|frame_gen|ngx|streamline"),
    ("area/menu", r"vk_menu|menu|coop_menu|settings_ui|imgui"),
    ("area/input", r"input|controller|gamepad|keyboard|mouse|sdl_joy|rumble|gyro"),
    ("area/audio", r"audio|sound|music|sfx|seq_|bgm"),
    ("area/saves", r"nn_fs|save|coop_profile|coop_backup|backup"),
    ("area/install", r"appimage|install|packag|launcher|preflight|make_game|^nx2/build\.py|build_release|flatpak|\.desktop$"),
    ("area/renderer", r"^gpu/|shader|\.glsl$|\.comp$|\.frag$|\.vert$|vk_|vulkan|render"),
]
AREA_WORDS = [
    ("area/accessibility", r"accessib|colou?r ?blind|screen reader|subtitle|text size|high contrast"),
    ("area/upscaling", r"\bdlss\b|\bfsr\d?\b|\bxess\b|upscal|frame generation|frame-gen"),
    ("area/audio", r"\baudio\b|\bsound\b|\bmusic\b"),
    ("area/input", r"\bcontroller\b|\bkeyboard\b|\bmouse\b|\bgamepad\b|\binput\b"),
    ("area/saves", r"\bsaves?\b(?! the)|\bbackup\b"),
    ("area/menu", r"\bmenu\b|\btab\b|\bsettings\b"),
    ("area/install", r"\binstall|\bappimage\b|\blauncher\b|\bupdater?\b"),
]
MAC = r"\bmac ?os\b|\bmacos\b|\bmac\b|\bmetal\b|moltenvk|\bapple\b|\bdarwin\b|apple silicon|\bcocoa\b"
MAC_PATH = r"(^|/)mac(os)?/|_mac\.|_macos\.|darwin|moltenvk|metal|\.mm$|\.m$|\.plist$|\.dylib"
WIN_PATH = r"(^|/)win(dows)?/|_win\.|_win32\.|_windows\.|mingw|msvc|\.ps1$|\.bat$|\.rc$|\.manifest$|dxgi|d3d"
LINUX_PATH = r"linux|appimage|wayland|x11|flatpak|\.desktop$"
DECK = r"steam ?deck|\bdeck\b"
GPU = [("gpu/intel", r"\barc\b|intel (gpu|graphics|uhd|iris|xe)|\banv\b|\bb580\b|\ba770\b|\ba750\b"),
       ("gpu/amd", r"\bamd\b|\bradv\b|radeon|\brdna\d?\b"),
       ("gpu/nvidia", r"\bnvidia\b|geforce|\brtx ?\d{4}\b"),
       ("gpu/igpu", r"integrated (gpu|graphics)|\bigpu\b|\buhd ?\d+")]
CRITICAL = r"\bcrash|data loss|corrupt|lost saves?|loses? (the )?saves?|cannot start|can't start|fails to start|won't start|does not start|freezes? at (start|boot)"
REGRESSION = r"\bregress|worked in (an )?(earlier|older|previous)|broke(n)? (in|since|after) (the )?(last|recent|new)"
NOT_TESTS = re.compile(r"^(tests?|docs)/|\.md$")


def why_text(body):
    """The reason part of a description: before 'What changed', without the status line and its hardware words."""
    body = body or ""
    cut = re.split(r"^##\s+(What changed|Measurements|Testing)\b", body, maxsplit=1, flags=re.M)[0]
    keep = [ln for ln in cut.splitlines() if not re.search(r"\*\*(Type|Tested on|Needs)\:?\*\*|Tested on", ln)]
    return "\n".join(keep)[:4000]


def get_all(path):
    out, page = [], 1
    while True:
        r = forge.api("GET", "%s%slimit=50&page=%d" % (path, "&" if "?" in path else "?", page))
        if not r:
            break
        out += r
        if len(r) < 50:
            break
        page += 1
    return out


def propose(pr, files):
    title = pr["title"]
    words = (title + "\n" + why_text(pr.get("body"))).lower()
    tl = title.lower()
    src = [f for f in files if not NOT_TESTS.search(f)]
    paths = [f.lower() for f in (src or files)]
    prop, notes = [], []

    m = CC.match(title)
    kind = KIND.get(m.group(1).lower()) if m else None
    if not kind:
        kind = "kind/bug" if re.search(r"\bfix", tl) else None
        notes.append("title has no Conventional Commit type" + ("" if kind else "; kind left for a person"))
    if files and not src and all(re.search(r"^docs/|\.md$", f) for f in files):
        kind = "kind/docs"
    if kind:
        prop.append(kind)

    counts = {}
    for p in paths:
        for lab, rx in AREA_PATH:
            if re.search(rx, p):
                counts[lab] = counts.get(lab, 0) + 1
                break
    total = max(1, len(paths))
    areas = [lab for lab, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n / total >= 0.10][:3]
    for lab, rx in AREA_WORDS:
        if lab not in areas and re.search(rx, tl):
            areas.append(lab)
    if not areas:
        notes.append("no area found")
    prop += areas[:3]

    mac_title = re.search(MAC, tl) or (paths and all(re.search(MAC_PATH, p) for p in paths))
    if mac_title:
        prop.append("platform/macos")
    elif re.search(DECK, tl):
        prop += ["platform/steam-deck", "platform/linux"]
    elif paths and all(re.search(WIN_PATH, p) for p in paths) or re.search(r"\bwindows\b", tl) and not re.search(r"\blinux\b", tl):
        prop.append("platform/windows")
    elif paths and all(re.search(LINUX_PATH, p) for p in paths) or re.search(r"\blinux\b", tl) and not re.search(r"\bwindows\b", tl):
        prop.append("platform/linux")
    else:
        prop += ["platform/windows", "platform/linux"]
        if re.search(MAC, words):
            prop.append("platform/macos")      # shared code, found or wanted on a Mac: it reaches every system
            notes.append("macOS in its reason, shared files: all three platforms")

    for lab, rx in GPU:
        if re.search(rx, tl):
            prop.append(lab)

    if kind == "kind/bug" and re.search(CRITICAL, tl):
        prop.append("priority/high")
        notes.append("crash or data-loss words: critical is a person's call")
    elif kind in ("kind/bug", "kind/performance"):
        prop.append("priority/high")
    elif kind:
        prop.append("priority/low")
    if kind == "kind/bug" and re.search(REGRESSION, words):
        prop.append("regression")
        notes.append("regression by its words: check")
    return prop, notes


def cmd_plan(a):
    os.makedirs(a.out, exist_ok=True)
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        labels = {l["name"]: l["id"] for l in get_all("/repos/%s/labels" % REPO)}
        prs = get_all("/repos/%s/pulls?state=open" % REPO)
        if a.numbers:
            prs = [p for p in prs if p["number"] in a.numbers]
        plan = []
        for i, pr in enumerate(prs, 1):
            files = [f["filename"] for f in get_all("/repos/%s/pulls/%d/files" % (REPO, pr["number"]))]
            have = [l["name"] for l in pr["labels"]]
            prop, notes = propose(pr, files)
            add, kept = [], []
            for lab in dict.fromkeys(prop):
                if lab in have:
                    continue
                scope = next((s for s in SCOPES if lab.startswith(s)), None)
                if scope and any(h.startswith(scope) for h in have):
                    kept.append(lab)          # the scope is already labelled: report, do not add
                elif lab not in labels:
                    notes.append("no such label: " + lab)
                else:
                    add.append(lab)
            plan.append(dict(number=pr["number"], title=pr["title"], author=pr["user"]["login"],
                             draft=pr.get("draft", False), files=len(files), have=have, add=add,
                             not_added_scope_taken=kept, notes=notes, url=pr["html_url"]))
            if i % 25 == 0:
                print("read", i, "of", len(prs), file=sys.stderr)
    plan.sort(key=lambda r: r["number"])
    with open(os.path.join(a.out, "plan.json"), "w") as f:
        json.dump(dict(made=time.strftime("%Y-%m-%dT%H:%M:%S%z"), labels=labels, prs=plan), f, indent=1)
    with open(os.path.join(a.out, "plan.md"), "w") as f:
        f.write("| PR | author | title | has | adds | notes |\n|---|---|---|---|---|---|\n")
        for r in plan:
            f.write("| %d | %s | %s | %s | %s | %s |\n" % (r["number"], r["author"], r["title"].replace("|", "/")[:80],
                    ", ".join(r["have"]), ", ".join(r["add"]), "; ".join(r["notes"])))
    n_add = sum(1 for r in plan if r["add"])
    print("%d open pull requests, %d unlabelled, %d would get labels, %d flagged for a look; %s" % (
        len(plan), sum(1 for r in plan if not r["have"]), n_add, sum(1 for r in plan if r["notes"]),
        os.path.join(a.out, "plan.md")))


def cmd_apply(a):
    with open(a.plan) as f:
        plan = json.load(f)
    labels = plan["labels"]
    todo = [r for r in plan["prs"] if r["add"] and (not a.numbers or r["number"] in a.numbers)]
    print("%d pull requests to label%s" % (len(todo), "" if a.go else " (dry run: add --go)"))
    if not a.go:
        for r in todo:
            print(r["number"], "+", ", ".join(r["add"]))
        return
    done = []
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        for r in todo:
            now = [l["name"] for l in forge.api("GET", "/repos/%s/issues/%d/labels" % (REPO, r["number"]))]
            add = [x for x in r["add"] if x not in now and not (
                next((s for s in SCOPES if x.startswith(s)), None) and
                any(h.startswith(next(s for s in SCOPES if x.startswith(s))) for h in now))]
            if add:
                forge.api("POST", "/repos/%s/issues/%d/labels" % (REPO, r["number"]), {"labels": [labels[x] for x in add]})
            done.append(dict(number=r["number"], added=add))
            print(r["number"], "+", ", ".join(add) or "(nothing: labelled meanwhile)")
            time.sleep(0.2)
    with open(a.plan.replace("plan.json", "applied.json"), "w") as f:
        json.dump(dict(at=time.strftime("%Y-%m-%dT%H:%M:%S%z"), done=done), f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--numbers", type=int, nargs="*")
    p.add_argument("--out", default=os.path.join("/home/tonesi/hookshot-wt/reports/PrTags", time.strftime("%Y%m%d-%H%M")))
    p = sub.add_parser("apply")
    p.add_argument("--plan", required=True)
    p.add_argument("--numbers", type=int, nargs="*")
    p.add_argument("--go", action="store_true")
    a = ap.parse_args()
    (cmd_plan if a.cmd == "plan" else cmd_apply)(a)


if __name__ == "__main__":
    main()
