"""The co-op progress classifier's lists, read out of an LS checkout's `host/oot_coop.c` (not retyped, not copied here).

The source holds hashes only; this module parses the C text for the constants (`#define`), the hash lists (`static const
uint32_t name[] = {...}`), the ammunition pairs, the boss sets and the comments beside the hashes. The classifier's rules are
code, and fd_classify.py mirrors them as of the revision named in RULES_VERIFIED; `rule_warnings` says when the source's
`classify()` no longer has the fragments the mirror depends on.
"""
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

RULES_VERIFIED = "29b087a83"
SOURCE = "host/oot_coop.c"
SCENES_SOURCE = "host/coop_scenes.c"

CONSTANTS = ("S_POUCH", "M_STOCK", "S_FIRST_GET", "S_DUNGEON", "M_SMALL_KEYS", "M_GET_MAP", "M_GET_COMPASS", "M_GET_BOSS_KEY",
             "S_CAPACITY", "F_RUPEES", "F_MAGIC_SIZE")
LISTS = ("song_flags", "heart_reward_flags", "unshared_flags", "quest_counts", "own_counts")
OPTIONAL_LISTS = ("code_read_scenes",)
# What fd_classify.classify mirrors; each fragment must still be in the source's classify().
RULE_FRAGMENTS = ("file != 0", "RESET_TEMPORARY", "RESET_NEW_GAME", "heart_reward_flags", "unshared_flags", "boss_own(h)", "song_flags",
                  "first_get", "coop_scenes_has", "code_read_scenes", "boss_proof_of", "F_RUPEES", "hset_has(&s->keys",
                  "hset_has(&s->pouch", "own_counts", "quest_counts", "ammo[i].count", "hset_has(&s->capacity", "F_MAGIC_SIZE")


@dataclass
class CoopLists:
    constants: dict
    reset_new_game: int
    reset_temporary: int
    key_max: int
    int_max_item: int
    lists: dict                         # name -> [hash]
    ammo: list                          # [(count hash, capacity member hash)]
    boss_sets: list                     # [{name, scene, quest, end, steps, proof: [(hash, end)], members: [(hash, end)], fight: [hash]}]
    comments: dict                      # hash -> the comment beside it in the source
    warnings: list = field(default_factory=list)


def read_source(path=None, repo=None, rev="HEAD", name=SOURCE):
    """The text of `host/oot_coop.c` (or another file): from `path`, else from `repo` (a clone, at `rev`)."""
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not repo:
        raise ValueError("give the source file (--source) or an LS checkout (--repo [--rev])")
    done = subprocess.run(["git", "-C", str(repo), "show", "%s:%s" % (rev, name)], capture_output=True)
    if done.returncode:
        raise ValueError("git show %s:%s failed: %s" % (rev, name, done.stderr.decode(errors="replace").strip()))
    return done.stdout.decode("utf-8")


def _strip(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _block(src, pattern):
    """The text of the first `{...}` after `pattern =`, braces balanced, comments removed."""
    m = re.search(pattern + r"[^=;]*=\s*\{", src)
    if not m:
        raise ValueError("not found in the source: " + pattern)
    start, depth = m.end() - 1, 0
    for at in range(start, len(src)):
        if src[at] == "{":
            depth += 1
        elif src[at] == "}":
            depth -= 1
            if depth == 0:
                return _strip(src[start:at + 1])
    raise ValueError("unbalanced braces after " + pattern)


def _parse(block):
    tokens = re.findall(r'\{|\}|"[^"]*"|0[xX][0-9a-fA-F]+|\d+|[A-Za-z_]\w*', block)
    pos = 0

    def node():
        nonlocal pos
        pos += 1   # the opening brace
        out = []
        while tokens[pos] != "}":
            if tokens[pos] == "{":
                out.append(node())
            else:
                t = tokens[pos]
                pos += 1
                out.append(int(t, 16) if t[:2].lower() == "0x" else int(t) if t.isdigit() else t)
        pos += 1
        return out

    return node()


def _int(expr):
    value = 0
    for part in expr.split("|"):
        value |= int(part.strip().rstrip("uUlL"), 0)
    return value


def parse(text):
    """The classifier's lists out of the source text."""
    warnings = []
    constants = {}
    for name in CONSTANTS:
        m = re.search(r"#define\s+%s\s+(0[xX][0-9a-fA-F]+)" % name, text)
        if not m:
            raise ValueError("not found in the source: #define " + name)
        constants[name] = int(m.group(1), 16)

    def enum_value(name):
        m = re.search(r"\b%s\s*=\s*([0-9xXa-fA-F| ]+?)\s*[,;}\n]" % name, text)
        if not m:
            raise ValueError("not found in the source: " + name)
        return _int(m.group(1))

    lists = {}
    for name in LISTS + OPTIONAL_LISTS:
        try:
            lists[name] = _parse(_block(text, r"static const uint32_t %s\[\]" % name))
        except ValueError:
            if name in OPTIONAL_LISTS:
                lists[name] = []
                warnings.append("no %s in the source: treated as empty (an older revision)" % name)
            else:
                raise
    ammo = [tuple(x) for x in _parse(_block(text, r"static const struct \{[^}]*\} ammo\[\]"))]
    bosses = []
    for b in _parse(_block(text, r"static const BossSet boss_sets\[[^\]]*\]")):
        name, scene, quest, end, end_at, steps, proof, members, fight = b
        bosses.append(dict(name=name.strip('"'), scene=scene.strip('"'), quest=quest, end=end, end_at=end_at,
                           steps=[s for s in steps if s],
                           proof=[tuple(p) for p in proof if isinstance(p, list) and p and p[0]],
                           members=[tuple(p) for p in members if isinstance(p, list) and p and p[0]],
                           fight=[x for x in fight if x]))
    comments = {}
    for m in re.finditer(r"(0[xX][0-9a-fA-F]{8})[^/\n]*?[,}][ \t]*(?:\}[ \t]*,?)?[ \t]*/\*\s*(.*?)\s*\*/", text):
        comments[int(m.group(1), 16)] = m.group(2)
    return CoopLists(constants=constants, reset_new_game=enum_value("RESET_NEW_GAME"),
                     reset_temporary=enum_value("RESET_TEMPORARY"), key_max=enum_value("KEY_MAX"),
                     int_max_item=enum_value("INT_MAX_ITEM"), lists=lists, ammo=ammo, boss_sets=bosses, comments=comments,
                     warnings=warnings)


def rule_warnings(text):
    """Fragments the classifier's mirror depends on that the source's `classify()` no longer has: its rules may have changed."""
    m = re.search(r"static Class classify\(", text)
    if not m:
        return ["no classify() in the source: the rules cannot be checked"]
    end = text.find("\n}\n", m.start())
    body = text[m.start():end if end > 0 else len(text)]
    missing = [f for f in RULE_FRAGMENTS if f not in body]
    return ["classify() no longer contains %r: its rules changed after %s; check fd_classify.py against it" % (f, RULES_VERIFIED)
            for f in missing]


def scan_settings(text):
    """(folders, table folder, table name start, table name end, played prefix, longest name) of coop_scenes.c, or None."""
    roots = re.search(r"scan_roots\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if not roots:
        return None

    def define(name):
        m = re.search(r'#define\s+%s\s+"([^"]*)"' % name, text)
        return m.group(1) if m else None

    folders = re.findall(r'"([^"]+)"', _strip(roots.group(1)))
    longest = re.search(r"COOP_SCENES_NAME_MAX\s*=\s*(\d+)", text)
    return dict(folders=folders, table_folder=define("TABLE_FOLDER"), table_start=define("TABLE_START"), table_end=define("TABLE_END"),
                prefix=define("PLAYED_PREFIX"), name_max=int(longest.group(1)) if longest else 255)
