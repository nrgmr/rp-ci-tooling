"""Invalidate the `approved-<staging>` tag when staging has moved past it.

The tag marks the staging commit a human last approved. If staging changed
afterwards, the tag is deleted so its existence stays trustworthy.

`gh api` prints the error body to stdout on a failed request, so a lookup is
judged by its exit code, never by whether stdout is empty. Treating a 404 body
as a SHA is what made this check try to delete a tag that did not exist.

Environment:
    GITHUB_REPOSITORY   owner/repo
    STAGING_BRANCH      branch whose approval is checked
    GH_TOKEN            token for `gh api`

Outputs (GITHUB_OUTPUT):
    invalidated         "true" when the tag was deleted, otherwise "false"

Exit codes:
    0  - checked; the tag was absent, current, or deleted
    1  - a GitHub API call that had to succeed failed
"""

import os
import subprocess
import sys
from collections.abc import Callable

NO_TAG = "no_tag"
CURRENT = "current"
INVALIDATED = "invalidated"

# Takes `gh api` arguments and returns (exit code, stdout).
GhRunner = Callable[..., tuple[int, str]]


class GitHubApiError(RuntimeError):
    pass


def run_gh(*args: str) -> tuple[int, str]:
    result = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip()


def check_approval(repo: str, staging_branch: str, gh: GhRunner) -> tuple[str, str]:
    """Return (outcome, summary line). Deletes the tag only when staging moved past it."""
    tag = f"approved-{staging_branch}"

    code, approved_sha = gh(f"repos/{repo}/git/ref/tags/{tag}", "-q", ".object.sha")
    if code != 0 or not approved_sha:
        return NO_TAG, f"no {tag} tag set - nothing to invalidate"

    code, staging_sha = gh(f"repos/{repo}/git/ref/heads/{staging_branch}", "-q", ".object.sha")
    if code != 0:
        raise GitHubApiError(f"could not read {staging_branch}: {staging_sha}")
    if approved_sha == staging_sha:
        return CURRENT, f"{staging_branch} still matches the last approval"

    code, body = gh("--method", "DELETE", f"repos/{repo}/git/refs/tags/{tag}")
    if code != 0:
        raise GitHubApiError(f"could not delete {tag}: {body}")
    return INVALIDATED, f"{tag} invalidated: {staging_branch} changed after approval"


def _append(path_var: str, line: str) -> None:
    path = os.environ.get(path_var)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main(gh: GhRunner = run_gh) -> int:
    try:
        outcome, summary = check_approval(
            os.environ["GITHUB_REPOSITORY"], os.environ["STAGING_BRANCH"], gh
        )
    except (KeyError, GitHubApiError) as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1

    _append("GITHUB_STEP_SUMMARY", summary)
    _append("GITHUB_OUTPUT", f"invalidated={'true' if outcome == INVALIDATED else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
