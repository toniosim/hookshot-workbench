"""What a model driver needs before it may ask: a key (where one is needed) and room under the caps.

KeySource is openai_api's key handling for another service: the key is read at the moment of each request from the environment or
from a private file outside the repository (mode 600, one line), held in a local variable for that request, sent only in the
Authorization header, scrubbed from every error text, and never printed, logged or written to a transcript.
"""
import os
import stat
from pathlib import Path

import openai_api

from .base import Availability


class KeySource:
    def __init__(self, env_var, file_env, default_name):
        self.env_var, self.file_env, self.default_name = env_var, file_env, default_name

    def file(self):
        explicit = os.environ.get(self.file_env)
        if explicit:
            return Path(explicit)
        base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
        return Path(base) / 'ls-pilot' / self.default_name   # (read only; never inside a repository)

    def state(self):
        """'env', 'file', 'no key' or 'no key (the key file is not mode 600)': without reading more than the file's mode."""
        if os.environ.get(self.env_var):
            return 'env'
        try:
            mode = stat.S_IMODE(self.file().stat().st_mode)
        except OSError:
            return 'no key'
        return 'file' if mode == 0o600 else 'no key (the key file is not mode 600)'

    def get(self):
        """The key, for one request. Raises openai_api.NoKey (the text never holds the key)."""
        k = os.environ.get(self.env_var)
        if k:
            return k.strip()
        path = self.file()
        try:
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise openai_api.NoKey('the key file is not mode 600')
            k = path.read_text().strip()
        except OSError:
            raise openai_api.NoKey('no key') from None
        if not k:
            raise openai_api.NoKey('the key file is empty')
        return k


OPENROUTER_KEY = KeySource('OPENROUTER_API_KEY', 'PILOT_OPENROUTER_KEY_FILE', 'openrouter.key')
CHAT_KEY = KeySource('PILOT_CHAT_API_KEY', 'PILOT_CHAT_KEY_FILE', 'chat.key')   # optional: a local server needs none


def caps_availability(run_id):
    """Room under the three caps (per run, per night, in total) and a readable caps file: the same limits every paid request is
    checked against (openai_api.Client.check_caps), asked without a request."""
    try:
        c = openai_api.caps()
    except openai_api.CapReached as e:
        return Availability.no(str(e), 'over_budget')
    s = openai_api.spent(run_id)
    for what, key, cap in (('run', 'run', 'per_run_usd'), ('night', 'night', 'per_night_usd'), ('total', 'total', 'total_usd')):
        if s[key] >= c[cap]:
            return Availability.no(f'{what} cap {c[cap]:.2f} USD reached ({s[key]:.4f} spent)', 'over_budget')
    return Availability.yes()
