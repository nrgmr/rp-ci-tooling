# Workflow Reference

Detailed reference for each reusable workflow in this repo. For pinning and versioning guidance, see [README.md](../README.md).

Examples use the sample tag `v1.2.0`; replace it with the released tag the service is adopting. Do not pin service workflows to `@main`.

```yaml
uses: nrgmr/rp-ci-tooling/.github/workflows/<workflow>.yml@v1.2.0
```

---

## python-lint-test.yml

Runs ruff lint and format checks plus pytest against a Python service using uv.

### Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `project-dir` | No | `.` | Directory containing the `pyproject.toml` |

### Usage

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  lint-test:
    uses: nrgmr/rp-ci-tooling/.github/workflows/python-lint-test.yml@v1.2.0
    with:
      project-dir: sidecar
```

---

## python-openapi-generate.yml

Generates an OpenAPI spec from a Python FastAPI service, then runs the shared OpenAPI checks: Spectral lint, oasdiff version enforcement, concurrent-version-limit check, and GCP baseline fetch/publish.

The workflow expects `project-dir` to be a uv project with `main.py` exporting a FastAPI app named `app`. It installs production dependencies with `uv sync --no-dev`, runs the repo-provided generator, and validates that the generated spec is JSON before running the shared checks.

### Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `project-dir` | No | `.` | Directory containing the `pyproject.toml` |
| `gen-spec-env` | No | `{}` | JSON object of env vars needed during spec generation (dummy values are fine) |
| `gar-repository` | Yes | | Artifact Registry repository name |
| `package-name` | Yes | | Package name used to store the prod spec in Artifact Registry |
| `gar-location` | No | `us-central1` | Artifact Registry region |
| `workload-identity-provider` | Yes | | GCP Workload Identity Provider used to authenticate GitHub Actions to GCP |
| `service-account` | Yes | | GCP service account email used by CI |
| `gar-project` | Yes | | GCP project hosting Artifact Registry |
| `override-version-limit` | No | `false` | Allows the version-limit gate to warn instead of fail when route retirement is already in progress |

### Usage

```yaml
name: API checks

on:
  push:
    branches: ["**"]
  pull_request:
  workflow_dispatch:
    inputs:
      override-version-limit:
        description: "Allow a temporary third route version when retirement is already in progress"
        type: boolean
        default: false

jobs:
  api-checks:
    uses: nrgmr/rp-ci-tooling/.github/workflows/python-openapi-generate.yml@v1.2.0
    with:
      project-dir: sidecar
      gen-spec-env: '{"UM_BASE_URL": "http://localhost", "PUBLIC_ORIGIN": "http://localhost"}'
      gar-repository: my-service
      package-name: my-service
      workload-identity-provider: projects/123456789/locations/global/workloadIdentityPools/github/providers/github
      service-account: nrg-elp-ci-prod-gha@nrg-bootstrap-master.iam.gserviceaccount.com
      gar-project: nrg-platsvc-elp-prod
      override-version-limit: ${{ inputs.override-version-limit || false }}
    secrets: inherit
```

### API check behavior

On every run the workflow checks out the caller repo and this tooling repo, generates `/tmp/openapi.json`, validates it as JSON, then:

1. **Spectral lint** - validates the spec against the shared RP Spectral ruleset, or the service's `.spectral.yaml` if present.
2. **GCP auth and baseline fetch** - runs on pull requests, manual `workflow_dispatch` runs, and pushes to `main`. Non-fork PRs, manual runs, and `main` pushes fail if GCP auth is unavailable. Fork PRs and non-main branch pushes still generate the spec and run local checks, but cannot run baseline diff or publish.
3. **Baseline selection** - downloads the latest immutable `sha-*` Artifact Registry version for the package. If no `sha-*` version exists, it falls back to `prod-baseline`. If no baseline exists, the run is treated as a new service or first deploy.
4. **Version enforcement** - when a baseline exists, compares the generated spec against the baseline using oasdiff. Non-breaking OpenAPI changes pass without a route version change. Breaking changes require a new major version path for each affected route. `info.version` is treated as OpenAPI metadata and is not used as a pass/fail gate.
5. **Concurrent version limit** - blocks the run if the current generated spec contains more than 2 live major versions for any route, or exactly 2 non-consecutive major versions for a route. This check does not need a prod baseline. `override-version-limit` converts this specific violation into a warning.
6. **PR comments** - on PRs, updates bot comments for new services with no baseline, breaking API changes, and version-limit violations or overrides.
7. **Baseline publish** - on a successful push to `main`, uploads the generated spec as `sha-${{ github.sha }}` and refreshes `prod-baseline` as a compatibility alias. Future checks prefer the latest `sha-*` baseline.

#### Route versioning rules

Routes are identified by their full path with the version segment normalized to `/v{N}`. Prefixes, suffixes, and the rest of the path all remain significant.

These are the **same route** across versions:

```text
/api/v1/auth/users
/api/v2/auth/users
```

These are **different routes**:

```text
/api/v1/auth/users
/api/v2/auth/roles
/internal/v2/auth/users
```

If `/api/v1/auth/users` has a breaking change, the replacement route must be `/api/v2/auth/users`. Adding only `/api/v2/auth/status` does not satisfy the rule.

At most two major versions of the same normalized route may be live at once, and two coexisting versions in the current spec must be consecutive. If prod has `v1` and `v2`, a PR may retire `v1` and introduce `v3` in the same current spec, leaving only `v2` and `v3`. A current spec containing `v1`, `v2`, and `v3` is blocked. Use `override-version-limit` only when retirement is already tracked and in progress.

For the manual override checkbox to appear, the caller workflow must define the `workflow_dispatch.inputs.override-version-limit` input and pass it through to `python-openapi-generate.yml`, as shown in the examples above.

#### Spectral overrides

A service can add a `.spectral.yaml` at its repo root to extend or adjust the shared ruleset:

```yaml
extends: [".rp-ci-tooling/spectral/rp-base.spectral.js"]
rules:
  operation-description: warn
```

Overrides should be narrow and intentional. They apply only to the repo that declares them.

The shared ruleset enforces OpenAPI validity, contact metadata, operation summaries and descriptions, success responses, response descriptions, defined/described tags, and the rule that every non-probe API path has exactly one version segment like `/v1`. The concurrent route version limit is enforced separately by `scripts/openapi_version_limit_check.py` so the workflow can support `override-version-limit` without weakening the base Spectral ruleset.

---

## docker-build-push.yml

Builds a Docker image on every run. Pushes the commit SHA tag to Artifact Registry only on pushes to `develop`, `staging`, and `main`; `main` also pushes `latest`. Pull requests and other branch pushes build the image but do not push it.

### Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `image-name` | Yes | | Docker image name |
| `gar-repository` | Yes | | Artifact Registry repository name |
| `gar-project` | Yes | | GCP project hosting Artifact Registry |
| `dockerfile` | No | `./Dockerfile` | Path to the Dockerfile |
| `context` | No | `.` | Docker build context |
| `gar-location` | No | `us-central1` | Artifact Registry region |

### Secrets

| Secret | Required | Purpose |
| --- | --- | --- |
| `WORKLOAD_IDENTITY_PROVIDER` | Yes | Authenticate GitHub Actions to GCP |
| `SERVICE_ACCOUNT` | Yes | GCP service account used by CI |

### Usage

```yaml
name: Docker

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  docker:
    uses: nrgmr/rp-ci-tooling/.github/workflows/docker-build-push.yml@v1.2.0
    with:
      image-name: my-service-sidecar
      dockerfile: ./sidecar/Dockerfile
      context: ./sidecar
      gar-repository: my-service
      gar-project: my-gcp-project
    secrets: inherit
```

---

## Combined service workflow

```yaml
name: Service CI

on:
  push:
    branches: ["**"]
  pull_request:
  workflow_dispatch:
    inputs:
      override-version-limit:
        description: "Allow a temporary third route version when retirement is already in progress"
        type: boolean
        default: false

jobs:
  lint-test:
    uses: nrgmr/rp-ci-tooling/.github/workflows/python-lint-test.yml@v1.2.0
    with:
      project-dir: sidecar

  api-checks:
    needs: lint-test
    uses: nrgmr/rp-ci-tooling/.github/workflows/python-openapi-generate.yml@v1.2.0
    with:
      project-dir: sidecar
      gen-spec-env: '{"UM_BASE_URL": "http://localhost", "PUBLIC_ORIGIN": "http://localhost"}'
      gar-repository: my-service
      package-name: my-service
      workload-identity-provider: projects/123456789/locations/global/workloadIdentityPools/github/providers/github
      service-account: nrg-elp-ci-prod-gha@nrg-bootstrap-master.iam.gserviceaccount.com
      gar-project: nrg-platsvc-elp-prod
      override-version-limit: ${{ inputs.override-version-limit || false }}
    secrets: inherit

  docker:
    needs: [lint-test, api-checks]
    uses: nrgmr/rp-ci-tooling/.github/workflows/docker-build-push.yml@v1.2.0
    with:
      image-name: my-service-sidecar
      dockerfile: ./sidecar/Dockerfile
      context: ./sidecar
      gar-repository: my-service
      gar-project: my-gcp-project
    secrets: inherit
```
