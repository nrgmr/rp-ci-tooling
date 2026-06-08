"""Export a FastAPI app's OpenAPI schema to stdout as JSON.

Expects to be run from the service's Python project directory (where main.py lives).

Usage (from the project directory):
    uv run python <path-to-this-script>/gen_openapi.py > /tmp/openapi.json
"""

import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

with redirect_stdout(sys.stderr):
    from main import app  # noqa: E402

    schema = app.openapi()

json.dump(schema, sys.stdout, indent=2)
sys.stdout.write("\n")
