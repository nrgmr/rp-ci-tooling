"""Tests for openapi_version_limit_check.py.

No external tools required; the script is pure Python.
"""

from pathlib import Path

from openapi_version_limit_check import main, route_versions

FIXTURES = Path(__file__).parent / "fixtures"


class TestRouteVersions:
    def test_single_route_single_version(self):
        spec = {"paths": {"/v1/auth/verify": {"get": {"responses": {}}}}}
        assert route_versions(spec) == {"/v{N}/auth/verify": {1}}

    def test_multiple_routes(self):
        spec = {
            "paths": {
                "/v1/auth/verify": {"get": {"responses": {}}},
                "/v2/auth/verify": {"get": {"responses": {}}},
                "/v1/reports/list": {"get": {"responses": {}}},
            }
        }
        assert route_versions(spec) == {
            "/v{N}/auth/verify": {1, 2},
            "/v{N}/reports/list": {1},
        }

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

    def test_probe_paths_excluded(self):
        spec = {
            "paths": {
                "/v1/auth/verify": {"get": {"responses": {}}},
                "/healthz": {"get": {"tags": ["probe"], "responses": {}}},
            }
        }
        assert route_versions(spec) == {"/v{N}/auth/verify": {1}}

    def test_path_tagged_probe_excluded(self):
        spec = {"paths": {"/v1/probe/ready": {"get": {"tags": ["probe"], "responses": {}}}}}
        assert route_versions(spec) == {}

    def test_unversioned_path_ignored(self):
        spec = {"paths": {"/auth/verify": {"get": {"responses": {}}}}}
        assert route_versions(spec) == {}

    def test_empty_paths(self):
        assert route_versions({"paths": {}}) == {}

    def test_non_object_path_item_ignored(self):
        spec = {"paths": {"/v1/auth/verify": "not an object"}}
        assert route_versions(spec) == {}

    def test_non_object_operation_ignored(self):
        spec = {"paths": {"/v1/auth/verify": {"get": "not an operation object"}}}
        assert route_versions(spec) == {}


class TestVersionLimitMain:
    def test_missing_current_spec_fails(self, tmp_path, capsys):
        rc = main(str(tmp_path / "nonexistent.json"))
        assert rc == 1
        out = capsys.readouterr().out
        assert "could not read current spec" in out

    def test_current_spec_os_error_fails(self, tmp_path, capsys):
        rc = main(str(tmp_path))
        assert rc == 1
        out = capsys.readouterr().out
        assert "could not read current spec" in out

    def test_single_version_passes(self):
        rc = main(str(FIXTURES / "auth_v1.json"))
        assert rc == 0

    def test_two_versions_passes(self):
        rc = main(str(FIXTURES / "auth_v1_v2.json"))
        assert rc == 0

    def test_retire_oldest_and_add_new_version_in_same_spec_passes(self):
        rc = main(str(FIXTURES / "auth_v2_v3.json"))
        assert rc == 0

    def test_non_consecutive_versions_fail(self, capsys):
        rc = main(str(FIXTURES / "auth_v1_v3.json"))
        assert rc == 2
        out = capsys.readouterr().out
        assert "non-consecutive" in out

    def test_three_versions_fails(self, capsys):
        rc = main(str(FIXTURES / "auth_v1_v2_v3.json"))
        assert rc == 2
        out = capsys.readouterr().out
        assert "/v{N}/auth/verify" in out
        assert "3" in out

    def test_two_groups_within_limit_passes(self):
        rc = main(str(FIXTURES / "two_groups_v2_auth.json"))
        assert rc == 0

    def test_two_groups_both_at_two_versions_passes(self):
        rc = main(str(FIXTURES / "two_groups_v1_v2.json"))
        assert rc == 0

    def test_auth_exceeds_limit_reports_unaffected(self, capsys):
        rc = main(str(FIXTURES / "two_groups_v3_auth.json"))
        assert rc == 2
        out = capsys.readouterr().out
        assert "/v{N}/auth/verify" in out
        assert "OK   /v{N}/reports/list" in out

    def test_error_message_instructs_retirement(self, capsys):
        main(str(FIXTURES / "auth_v1_v2_v3.json"))
        out = capsys.readouterr().out
        assert "Retire" in out
        assert "OVERRIDE_VERSION_LIMIT" not in out
