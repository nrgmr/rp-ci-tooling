"""Tests for openapi_version_check.py.

Integration tests call the script via subprocess and require oasdiff on PATH.
Unit tests for pure-Python helpers run without any external tools.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openapi_version_check import breaking_change_routes, main, route_versions

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "openapi_version_check.py"
FIXTURES = Path(__file__).parent / "fixtures"

needs_oasdiff = pytest.mark.skipif(
    shutil.which("oasdiff") is None,
    reason="oasdiff not on PATH",
)


def run(baseline: Path, current: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(baseline), str(current)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout


class TestRouteVersions:
    def test_extracts_route_and_version(self):
        spec = {"paths": {"/v1/auth/verify": {"get": {"responses": {}}}}}
        assert route_versions(spec) == {"/v{N}/auth/verify": {1}}

    def test_multiple_versions_same_route(self):
        spec = {
            "paths": {
                "/v1/auth/verify": {"get": {"responses": {}}},
                "/v2/auth/verify": {"get": {"responses": {}}},
            }
        }
        assert route_versions(spec) == {"/v{N}/auth/verify": {1, 2}}

    def test_keeps_path_prefix_before_version(self):
        spec = {
            "paths": {
                "/api/v1/auth/verify": {"get": {"responses": {}}},
                "/api/v2/auth/verify": {"get": {"responses": {}}},
            }
        }
        assert route_versions(spec) == {"/api/v{N}/auth/verify": {1, 2}}

    def test_different_suffixes_are_different_routes(self):
        spec = {
            "paths": {
                "/v1/auth/verify": {"get": {"responses": {}}},
                "/v2/auth/whoami": {"get": {"responses": {}}},
            }
        }
        assert route_versions(spec) == {
            "/v{N}/auth/verify": {1},
            "/v{N}/auth/whoami": {2},
        }

    def test_probe_excluded(self):
        spec = {
            "paths": {
                "/v1/auth/verify": {"get": {"responses": {}}},
                "/v1/auth/probe": {"get": {"tags": ["probe"], "responses": {}}},
            }
        }
        assert route_versions(spec) == {"/v{N}/auth/verify": {1}}

    def test_unversioned_path_ignored(self):
        spec = {"paths": {"/auth/verify": {"get": {"responses": {}}}}}
        assert route_versions(spec) == {}


class TestBreakingChangeRoutes:
    def test_extracts_route_from_path(self):
        payload = '[{"path": "/v1/auth/verify", "id": "api-path-removed"}]'
        assert breaking_change_routes(payload) == {"/v{N}/auth/verify"}

    def test_keeps_prefix_before_version(self):
        payload = '[{"path": "/api/v1/auth/verify", "id": "api-path-removed"}]'
        assert breaking_change_routes(payload) == {"/api/v{N}/auth/verify"}

    def test_multiple_routes(self):
        payload = '[{"path": "/v1/auth/verify"}, {"path": "/v1/reports/list"}]'
        assert breaking_change_routes(payload) == {
            "/v{N}/auth/verify",
            "/v{N}/reports/list",
        }

    def test_deduplicates_same_route(self):
        payload = '[{"path": "/v1/auth/verify"}, {"path": "/v2/auth/verify"}]'
        assert breaking_change_routes(payload) == {"/v{N}/auth/verify"}

    def test_does_not_deduplicate_different_routes_in_same_group(self):
        payload = '[{"path": "/v1/auth/verify"}, {"path": "/v1/auth/whoami"}]'
        assert breaking_change_routes(payload) == {
            "/v{N}/auth/verify",
            "/v{N}/auth/whoami",
        }

    def test_empty_list(self):
        assert breaking_change_routes("[]") == set()

    def test_invalid_json_returns_empty(self):
        assert breaking_change_routes("not json") == set()

    def test_change_without_path_ignored(self):
        payload = '[{"id": "schema-change", "path": ""}]'
        assert breaking_change_routes(payload) == set()


class TestOasdiffExitCodeHandling:
    """oasdiff diff exits 0 on some versions even when differences exist.

    The script must detect changes from stdout content, not just exit code.
    """

    def _mock_run(self, diff_returncode, diff_stdout, breaking_returncode, breaking_stdout):
        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[1] == "diff":
                result.returncode = diff_returncode
                result.stdout = diff_stdout
                result.stderr = ""
            else:
                result.returncode = breaking_returncode
                result.stdout = breaking_stdout
                result.stderr = ""
            return result

        return side_effect

    def test_exit0_with_stdout_treated_as_changed(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text('{"openapi":"3.0.0","info":{"title":"T","version":"1.0.0"},"paths":{}}')
        current = tmp_path / "current.json"
        current.write_text('{"openapi":"3.0.0","info":{"title":"T","version":"1.0.0"},"paths":{}}')
        side_effect = self._mock_run(
            diff_returncode=0,
            diff_stdout="some diff output\n",
            breaking_returncode=0,
            breaking_stdout="[]",
        )
        with patch("openapi_version_check.subprocess.run", side_effect=side_effect):
            rc = main(str(baseline), str(current))
        assert rc == 0

    def test_exit0_with_empty_stdout_treated_as_no_changes(self, tmp_path):
        spec = tmp_path / "spec.json"
        spec.write_text('{"openapi":"3.0.0","info":{"title":"T","version":"1.0.0"},"paths":{}}')
        side_effect = self._mock_run(
            diff_returncode=0,
            diff_stdout="",
            breaking_returncode=0,
            breaking_stdout="[]",
        )
        with patch("openapi_version_check.subprocess.run", side_effect=side_effect):
            rc = main(str(spec), str(spec))
        assert rc == 0

    def test_breaking_without_identified_route_fails(self, tmp_path):
        spec = tmp_path / "spec.json"
        spec.write_text('{"openapi":"3.0.0","info":{"title":"T","version":"1.0.0"},"paths":{}}')
        side_effect = self._mock_run(
            diff_returncode=1,
            diff_stdout="some diff output\n",
            breaking_returncode=1,
            breaking_stdout='[{"id": "schema-removed"}]',
        )
        with patch("openapi_version_check.subprocess.run", side_effect=side_effect):
            rc = main(str(spec), str(spec))
        assert rc == 1


@needs_oasdiff
class TestApiVersionScript:
    def test_no_changes_passes(self):
        rc, _ = run(FIXTURES / "auth_v1.json", FIXTURES / "auth_v1.json")
        assert rc == 0

    def test_nonbreaking_change_with_info_version_bump_passes(self):
        rc, _ = run(FIXTURES / "auth_v1.json", FIXTURES / "api_nonbreaking_v1_1.json")
        assert rc == 0

    def test_nonbreaking_change_without_info_version_bump_passes(self):
        rc, _ = run(FIXTURES / "auth_v1.json", FIXTURES / "api_nonbreaking_no_bump.json")
        assert rc == 0

    def test_breaking_with_new_paths_passes(self):
        rc, _ = run(FIXTURES / "auth_v1.json", FIXTURES / "api_breaking_v2.json")
        assert rc == 0

    def test_breaking_with_new_paths_and_no_info_version_bump_passes(self):
        rc, _ = run(FIXTURES / "auth_v1.json", FIXTURES / "api_breaking_v2_no_bump.json")
        assert rc == 0

    def test_breaking_without_new_version_paths_fails(self):
        rc, out = run(FIXTURES / "auth_v1.json", FIXTURES / "api_breaking_no_paths_v2.json")
        assert rc == 1
        assert "/v2/auth/verify" in out

    def test_breaking_without_new_version_paths_fails_even_when_info_version_changes(self):
        rc, out = run(FIXTURES / "auth_v1.json", FIXTURES / "api_breaking_minor.json")
        assert rc == 1
        assert "/v2/auth/verify" in out

    def test_breaking_with_new_version_on_different_route_fails(self):
        rc, out = run(
            FIXTURES / "auth_v1.json",
            FIXTURES / "api_breaking_different_route_v2.json",
        )
        assert rc == 1
        assert "/v2/auth/verify" in out

    def test_breaking_in_one_group_other_group_unaffected_passes(self):
        rc, _ = run(
            FIXTURES / "api_multi_group_base.json",
            FIXTURES / "api_multi_group_breaking_auth.json",
        )
        assert rc == 0

    def test_outputs_affected_route_on_success(self):
        rc, out = run(FIXTURES / "auth_v1.json", FIXTURES / "api_breaking_v2.json")
        assert rc == 0
        assert "/v1/auth/verify -> /v2/auth/verify" in out
