"""Enforce route-level breaking-change policy against a prod baseline spec.

Exits non-zero if any of these conditions hold:
  - Breaking changes exist in a versioned route but that route has no new major
    version path in the current spec. Routes version independently: only the
    affected route needs to move, e.g. /api/v1/auth/users ->
    /api/v2/auth/users; unaffected routes are untouched.
  - Breaking changes exist, but oasdiff did not report any affected versioned
    route path that can be checked.

Routes are identified by the full path with exactly one version segment
normalized to /v{N}. This keeps prefixes and suffixes significant:
/api/v1/auth/users and /api/v2/auth/users are the same route, but
/api/v1/auth/users and /api/v1/auth/roles are different routes.

The OpenAPI info.version field is treated as metadata. It is not used as a
pass/fail gate; route paths are the compatibility contract.

When running inside GitHub Actions, writes these step outputs to GITHUB_OUTPUT:
  has_breaking  - "true" / "false"
  is_major_bump - "true" when breaking changes are present and route-level
                  major version paths were introduced
  route_summary - "<old route> -> <new route>, ..." for each affected route, set
                  only when is_major_bump is "true"
  breaking_details - multiline list of oasdiff's breaking changes grouped into
                  removed endpoints, removed fields, changed request shapes and
                  other, capped at about 20 KB, set whenever has_breaking is "true"

Usage:
    python3 openapi_version_check.py <baseline-spec> <current-spec>

Both arguments are paths to OpenAPI JSON files. oasdiff must be on PATH.
"""

import json
import os
import re
import subprocess
import sys
import uuid

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
_VERSION_SEGMENT = re.compile(r"/v(\d+)(?=/|$)")

_REMOVED_ENDPOINT_IDS = {
    "api-path-removed-without-deprecation",
    "api-path-removed-before-sunset",
    "api-removed-without-deprecation",
    "api-removed-before-sunset",
}
_REMOVED_FIELD_IDS = {
    "response-required-property-removed",
    "response-optional-property-removed",
    "required-response-header-removed",
    "optional-response-header-removed",
}
_REQUEST_SHAPE_ID_PREFIXES = ("request-", "new-request-", "new-required-request-")
_ERR_LEVEL = 3  # oasdiff: 1 INFO, 2 WARN, 3 ERR
# Teams rejects webhook payloads over 28 KB, and a rejected post only leaves a
# step-summary line. 20 KB leaves room for the rest of the card and JSON escaping.
_DETAILS_MAX_BYTES = 20_000


def versioned_route_key(path_key: str) -> tuple[str, int] | None:
    """Return (normalized_route_key, major_version) for paths with one /vN segment."""
    matches = list(_VERSION_SEGMENT.finditer(path_key))
    if len(matches) != 1:
        return None
    match = matches[0]
    version = int(match.group(1))
    route_key = f"{path_key[: match.start()]}/v{{N}}{path_key[match.end() :]}"
    return route_key, version


def route_key_for_version(route_key: str, version: int) -> str:
    return route_key.replace("/v{N}", f"/v{version}", 1)


def route_versions(spec: dict) -> dict[str, set[int]]:
    """Return {normalized_route_key: {major_versions}} for all non-probe paths."""
    routes: dict[str, set[int]] = {}
    for path_key, path_item in spec.get("paths", {}).items():
        ops = [v for k, v in path_item.items() if k in _HTTP_METHODS]
        if not ops or all("probe" in (op.get("tags") or []) for op in ops):
            continue
        route = versioned_route_key(path_key)
        if route:
            route_key, version = route
            routes.setdefault(route_key, set()).add(version)
    return routes


def _load_changes(breaking_json: str) -> list[dict]:
    try:
        return json.loads(breaking_json or "[]")
    except json.JSONDecodeError:
        return []


def breaking_change_routes(breaking_json: str) -> set[str]:
    """Extract normalized route keys from oasdiff breaking --format json output."""
    routes: set[str] = set()
    for change in _load_changes(breaking_json):
        path = change.get("path", "")
        route = versioned_route_key(path)
        if route:
            route_key, _ = route
            routes.add(route_key)
    return routes


def breaking_change_details(breaking_json: str, max_bytes: int = _DETAILS_MAX_BYTES) -> str:
    """Group oasdiff breaking changes into a markdown list per category.

    Items past max_bytes are dropped and counted in a closing "... N more" line.

    oasdiff has no rename check: a renamed property is reported as the old name
    removed (the new name is a non-breaking addition), so renames can only show
    up under removed fields.
    """
    sections: dict[str, list[str]] = {
        "Removed endpoints": [],
        "Removed fields (a rename shows up as a removal)": [],
        "Changed request shapes": [],
        "Other breaking changes": [],
    }
    for change in _load_changes(breaking_json):
        # `breaking` also reports WARN-level changes; only ERR ones break a client.
        if change.get("level", _ERR_LEVEL) < _ERR_LEVEL:
            continue
        change_id = change.get("id", "")
        if change_id in _REMOVED_ENDPOINT_IDS:
            title = "Removed endpoints"
        elif change_id in _REMOVED_FIELD_IDS:
            title = "Removed fields (a rename shows up as a removal)"
        elif change_id.startswith(_REQUEST_SHAPE_ID_PREFIXES):
            title = "Changed request shapes"
        else:
            title = "Other breaking changes"
        sections[title].append(
            f"- {change.get('operation', '')} {change.get('path', '')}: {change.get('text', '')}"
        )

    blocks: list[str] = []
    size = omitted = 0
    for title, items in sections.items():
        kept: list[str] = []
        for item in items:
            added = len(item.encode()) + (0 if kept else len(title.encode()) + 4)
            if omitted or size + added > max_bytes:
                omitted += 1
                continue
            kept.append(item)
            size += added + 1
        if kept:
            blocks.append(f"{title}:\n\n" + "\n".join(kept))
    if omitted:
        blocks.append(f"... {omitted} more, see the spec artifact.")
    return "\n\n".join(blocks)


def _set_gha_output(**kwargs: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a") as f:
        for k, v in kwargs.items():
            # Heredoc form for every value, so multiline ones need no special case;
            # the unguessable delimiter means no line of a value can close it early.
            delimiter = f"ghadelimiter_{uuid.uuid4()}"
            f.write(f"{k}<<{delimiter}\n{v}\n{delimiter}\n")


def main(baseline_path: str, current_path: str) -> int:
    with open(baseline_path) as f:
        baseline_spec = json.load(f)
    with open(current_path) as f:
        current_spec = json.load(f)

    diff = subprocess.run(
        ["oasdiff", "diff", baseline_path, current_path],
        capture_output=True,
        text=True,
    )
    # oasdiff diff exits 0 regardless of whether differences exist in some versions;
    # treat non-zero exit OR any stdout output as "has changes".
    has_changes = diff.returncode != 0 or bool(diff.stdout.strip())

    if not has_changes:
        _set_gha_output(has_breaking="false", is_major_bump="false")
        print("No API changes detected.")
        return 0

    breaking = subprocess.run(
        [
            "oasdiff",
            "breaking",
            "--fail-on",
            "ERR",
            "--format",
            "json",
            baseline_path,
            current_path,
        ],
        capture_output=True,
        text=True,
    )
    has_breaking = breaking.returncode != 0

    if not has_breaking:
        _set_gha_output(has_breaking="false", is_major_bump="false")
        print("Non-breaking API changes detected; no route version action required.")
        return 0

    affected = breaking_change_routes(breaking.stdout)
    baseline_routes = route_versions(baseline_spec)
    current_routes = route_versions(current_spec)
    failed = False

    if not affected:
        print(
            "ERROR: breaking changes detected, but no affected versioned route paths "
            "could be identified from oasdiff output."
        )
        failed = True

    for route_key in affected:
        baseline_max = max(baseline_routes.get(route_key, {0}))
        current_vers = current_routes.get(route_key, set())
        new_vers = {v for v in current_vers if v > baseline_max}
        if not new_vers:
            expected = route_key_for_version(route_key, baseline_max + 1)
            print(
                f"ERROR: breaking change in {route_key} but no new major version path found "
                f"(baseline max: v{baseline_max}, current versions for {route_key}: "
                f"{sorted(current_vers) or 'none'}). "
                f"Add {expected}."
            )
            failed = True

    _set_gha_output(
        has_breaking="true",
        is_major_bump="false" if failed else "true",
        breaking_details=breaking_change_details(breaking.stdout),
    )

    if not failed:
        route_summary = ", ".join(
            f"{route_key_for_version(r, max(baseline_routes.get(r, {0})))} -> "
            f"{route_key_for_version(r, max(current_routes.get(r, {0})))}"
            for r in sorted(affected)
        )
        _set_gha_output(route_summary=route_summary)
        print(f"Breaking changes detected; route major version bump confirmed: {route_summary}")

    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <baseline-spec> <current-spec>")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
