"""Use the configured harness's one runtime-name resolver; never execute checkout code."""
from src.effects.evidence_common import backend, load_backend

# Retained evidence remains readable without a currently installed game/harness.
LOG_NAMES = frozenset({"hookshot_log.txt", "longshot_log.txt"})


def resolver(deps, operation):
    return load_backend(backend(deps, "hs_names.py", operation))


def copy_names(deps, root, operation):
    try:
        return resolver(deps, operation).copy_names(root)
    except (ValueError, OSError, SyntaxError):
        raise deps.error("unavailable", operation) from None


def checkout_names(deps, root, operation):
    try:
        return resolver(deps, operation).checkout_names(root)
    except (ValueError, OSError, SyntaxError):
        raise deps.error("unavailable", operation) from None
