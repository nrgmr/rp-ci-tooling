"""Check that the current spec has <=2 consecutive major versions per route.

Version limits are enforced per normalized route path in the current generated
spec, which is the post-deploy live API contract. A PR may retire /api/v1/users
and introduce /api/v3/users in the same spec as long as the resulting spec has
at most two consecutive versions, such as /api/v2/users and /api/v3/users.

Routes are identified by the full path with exactly one version segment
normalized to /v{N}. This keeps prefixes and suffixes significant:
/api/v1/auth/users and /api/v2/auth/users are the same route, but
/api/v1/auth/users and /api/v1/auth/roles are different routes.

Exit codes:
    0  - within limit for all routes; safe to deploy
    2  - at least one route would have more than 2 concurrent major versions
         or 2 non-consecutive major versions
    1  - error (bad args, unreadable current spec)

Usage:
    python3 openapi_version_limit_check.py <current-spec>
"""

import json
import re
import sys

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
_VERSION_SEGMENT = re.compile(r"/v(\d+)(?=/|$)")


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
        if not isinstance(path_item, dict):
            continue

        ops = [v for k, v in path_item.items() if k in _HTTP_METHODS and isinstance(v, dict)]
        if not ops or all("probe" in (op.get("tags") or []) for op in ops):
            continue
        route = versioned_route_key(path_key)
        if route:
            route_key, version = route
            routes.setdefault(route_key, set()).add(version)
    return routes


def main(current_path: str) -> int:
    try:
        with open(current_path) as f:
            current_spec = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read current spec - {e}")
        return 1

    current_routes = route_versions(current_spec)

    failed = False
    for route_key, current_versions in sorted(current_routes.items()):
        route_failed = False
        if len(current_versions) > 2:
            retiring = min(current_versions)
            retiring_route = route_key_for_version(route_key, retiring)
            print(
                f"ERROR {route_key}: current spec has {len(current_versions)} concurrent "
                f"major versions ({sorted(current_versions)}). Retire {retiring_route} before "
                "proceeding, or re-run the workflow manually with 'Override version limit' checked."
            )
            route_failed = True
        elif len(current_versions) == 2:
            ordered_versions = sorted(current_versions)
            if ordered_versions[1] - ordered_versions[0] != 1:
                print(
                    f"ERROR {route_key}: current spec has non-consecutive major versions "
                    f"({ordered_versions}). The two coexisting versions for one route must "
                    "be consecutive."
                )
                route_failed = True

        if route_failed:
            failed = True
        else:
            print(
                f"OK   {route_key}: {sorted(current_versions)} concurrent major version(s) "
                "in current spec"
            )

    return 2 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <current-spec>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
