import json
import subprocess
import sys
from pathlib import Path


def test_gen_openapi_writes_only_json_to_stdout(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "gen-spec" / "python" / "gen_openapi.py"

    (tmp_path / "main.py").write_text(
        """
print("import side effect")


class App:
    def openapi(self):
        print("openapi side effect")
        return {
            "openapi": "3.1.0",
            "info": {"title": "Example API", "version": "1.0.0"},
            "paths": {},
        }


app = App()
""".lstrip()
    )

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    spec = json.loads(result.stdout)
    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "Example API"
    assert result.stdout.endswith("\n")
    assert "side effect" not in result.stdout
    assert "import side effect" in result.stderr
    assert "openapi side effect" in result.stderr
