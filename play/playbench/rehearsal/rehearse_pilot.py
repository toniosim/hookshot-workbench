"""pilot.py with hsap replaced by the rehearsal's wrapper (the fake launcher): python3 -I -B rehearse_pilot.py run <chapter> ... (pilot.py's own arguments)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ['REHEARSE_TREE'] + '/pilot')
import pilot  # noqa: E402

pilot.HSAP = Path(os.environ['REHEARSE_WRAP'])
sys.argv = ['pilot.py'] + sys.argv[1:]
sys.exit(pilot.main())
