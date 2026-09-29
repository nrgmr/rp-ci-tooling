"""Tests for approval_stale_check.py.

`gh` is replaced by a fake; no network or GitHub CLI required.
"""

import pytest
from approval_stale_check import (
    CURRENT,
    INVALIDATED,
    NO_TAG,
    GitHubApiError,
    check_approval,
    main,
)

NOT_FOUND_BODY = '{"message":"Not Found","status":"404"}'


class FakeGh:
    """Answers `gh api` calls by endpoint and records each call."""

    def __init__(self, tag=(1, NOT_FOUND_BODY), staging=(0, "bbb"), delete=(0, "")):
        self.tag, self.staging, self.delete = tag, staging, delete
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "--method":
            return self.delete
        return self.tag if "/git/ref/tags/" in args[0] else self.staging

    @property
    def deleted(self):
        return any(a[0] == "--method" for a in self.calls)


class TestCheckApproval:
    def test_missing_tag_is_not_deleted(self):
        # gh puts the 404 body on stdout with a non-zero exit; it must not read as a SHA.
        gh = FakeGh(tag=(1, NOT_FOUND_BODY))
        outcome, summary = check_approval("o/r", "staging", gh)
        assert outcome == NO_TAG
        assert "no approved-staging tag set" in summary
        assert not gh.deleted

    def test_empty_successful_lookup_counts_as_no_tag(self):
        outcome, _ = check_approval("o/r", "staging", FakeGh(tag=(0, "")))
        assert outcome == NO_TAG

    def test_tag_matching_staging_is_kept(self):
        gh = FakeGh(tag=(0, "bbb"), staging=(0, "bbb"))
        outcome, summary = check_approval("o/r", "staging", gh)
        assert outcome == CURRENT
        assert "still matches" in summary
        assert not gh.deleted

    def test_tag_behind_staging_is_deleted(self):
        gh = FakeGh(tag=(0, "aaa"), staging=(0, "bbb"))
        outcome, summary = check_approval("o/r", "staging", gh)
        assert outcome == INVALIDATED
        assert "approved-staging invalidated" in summary
        assert gh.calls[-1] == ("--method", "DELETE", "repos/o/r/git/refs/tags/approved-staging")

    def test_uses_configured_staging_branch_in_tag_name(self):
        gh = FakeGh(tag=(0, "aaa"), staging=(0, "bbb"))
        check_approval("o/r", "release", gh)
        assert gh.calls[0][0] == "repos/o/r/git/ref/tags/approved-release"

    def test_unreadable_staging_branch_raises(self):
        gh = FakeGh(tag=(0, "aaa"), staging=(1, NOT_FOUND_BODY))
        with pytest.raises(GitHubApiError, match="could not read staging"):
            check_approval("o/r", "staging", gh)

    def test_failed_delete_raises(self):
        gh = FakeGh(tag=(0, "aaa"), staging=(0, "bbb"), delete=(1, "boom"))
        with pytest.raises(GitHubApiError, match="could not delete approved-staging"):
            check_approval("o/r", "staging", gh)


class TestMain:
    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("STAGING_BRANCH", "staging")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
        return tmp_path

    def test_missing_tag_exits_zero_and_reports_not_invalidated(self, env):
        assert main(FakeGh()) == 0
        assert (env / "output").read_text() == "invalidated=false\n"
        assert "nothing to invalidate" in (env / "summary").read_text()

    def test_deleted_tag_reports_invalidated(self, env):
        assert main(FakeGh(tag=(0, "aaa"), staging=(0, "bbb"))) == 0
        assert (env / "output").read_text() == "invalidated=true\n"

    def test_api_failure_exits_one(self, env, capsys):
        assert main(FakeGh(tag=(0, "aaa"), staging=(1, "boom"))) == 1
        assert "::error::" in capsys.readouterr().err

    def test_missing_env_exits_one(self, monkeypatch):
        monkeypatch.delenv("STAGING_BRANCH", raising=False)
        assert main(FakeGh()) == 1
