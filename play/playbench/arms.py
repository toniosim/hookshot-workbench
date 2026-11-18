"""The scoreboard's arms. name -> {label, decider (rules | openai-decisions), planner (bool: the model planner / the chapter planner), args (extra
pilot.py run arguments), env (extra environment), requires (a text the committed pilot.py must contain: an arm that needs a flag the pilot does not
have yet is `unavailable` for the night, not failed)}. Which arms play every night is the private config's `arms` list (each arm adds about 1.2 holds
of the card a night). A changed arm starts a new series (its hash is stored with each result). The learning switches are PilotLearn's (pilot.py:
tactics ranked|fixed|off, lessons on|off; the defaults are ON and WRITING, so every arm names its own): the baselines turn both off (PILOT_LEARN=off:
nothing read, nothing written; an older pilot ignores it), the learned arms read the tactics library read-only (a night never learns from its own
cells).
"""

ARMS = {
    'rules': {
        'label': 'the rules player, learning off (the baseline)',
        'decider': 'rules',
        'env': {'PILOT_LEARN': 'off'},
    },
    'cheap': {
        'label': 'the cheap model arm (Decisions API decider and planner, no pictures), learning off (the baseline)',
        'decider': 'openai-decisions',
        'planner': True,
        'env': {'PILOT_LEARN': 'off'},
    },
    'rules-tactics': {
        'label': 'the rules player with the ranked tactics library (read-only)',
        'decider': 'rules',
        'env': {'PILOT_TACTICS': 'ranked', 'PILOT_TACTICS_READONLY': '1', 'PILOT_LESSONS': 'off'},
        'requires': '--tactics-readonly',
    },
    'cheap-tactics': {
        'label': 'the cheap model arm with the ranked tactics library (read-only), no lessons',
        'decider': 'openai-decisions',
        'planner': True,
        'env': {'PILOT_TACTICS': 'ranked', 'PILOT_TACTICS_READONLY': '1', 'PILOT_LESSONS': 'off'},
        'requires': '--tactics-readonly',
    },
    'cheap-lessons': {
        'label': "the cheap model arm with lessons in the planner's prompt, no tactics",
        'decider': 'openai-decisions',
        'planner': True,
        'env': {'PILOT_TACTICS': 'off', 'PILOT_LESSONS': 'on'},
        'requires': '--tactics-readonly',
    },
    'cheap-learned': {
        'label': 'the cheap model arm with tactics (read-only) and lessons',
        'decider': 'openai-decisions',
        'planner': True,
        'env': {'PILOT_TACTICS': 'ranked', 'PILOT_TACTICS_READONLY': '1', 'PILOT_LESSONS': 'on'},
        'requires': '--tactics-readonly',
    },
}
