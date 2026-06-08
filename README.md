# rp-ci-tooling

Reusable GitHub Actions workflows for Research Platform services. Service teams call these workflows to run common CI/CD gates without duplicating logic in every repo.

## Who this is for

**Pipeline consumers** — teams wiring up CI in a service repo. See [docs/tools.md](docs/tools.md) for available workflows, inputs, required secrets, and usage examples.

**Contributors** — adding new workflows, scripts, or Spectral rules to this repo. See [AGENTS.md](AGENTS.md) for conventions and gotchas, and [docs/release.md](docs/release.md) for the release process.

## Versioning

Releases follow semantic versioning and are automated via release-please. See [docs/release.md](docs/release.md) for the full release process, PR title conventions, and semver rules.

### Pinning in service workflows

Use an exact tag when CI behavior should only change during an intentional upgrade:

```yaml
uses: nrgmr/rp-ci-tooling/.github/workflows/python-lint-test.yml@v1.2.0
```

Use the floating major tag when backward-compatible updates should apply automatically:

```yaml
uses: nrgmr/rp-ci-tooling/.github/workflows/python-lint-test.yml@v1
```

Never pin to a branch:

```yaml
# Do not use this.
uses: nrgmr/rp-ci-tooling/.github/workflows/python-lint-test.yml@main
```

## This repo's own CI

`tooling-ci.yml` runs on pull requests and pushes to `main`. It lints and formats `scripts/` with ruff, then runs the full pytest suite alongside oasdiff and Spectral. Coverage is measured against `scripts/` and must stay at or above 80%. No external secrets are required.

To run the same checks locally:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```
