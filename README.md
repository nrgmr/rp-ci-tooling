# rp-ci-tooling

Reusable GitHub Actions workflows for Research Platform services. Service teams call these workflows to run common CI/CD gates without duplicating logic in every repo.

## Who this is for

**Pipeline consumers** — teams wiring up CI in a service repo. See [TOOLS.md](TOOLS.md) for available workflows, inputs, required secrets, and usage examples.

**Contributors** — adding new workflows, scripts, or Spectral rules to this repo. See [AGENTS.md](AGENTS.md) for conventions, gotchas, and the release process.

## Versioning

Releases follow semantic versioning. Tags are cut manually after merging to `main`.

### Semver rules

| Change | Bump |
| --- | --- |
| Removing a workflow, removing or renaming an input, changing required secret names, breaking script interface change (args, exit codes, GHA outputs) | Major (`v2.0.0`) |
| New optional input, new workflow, new composite action | Minor (`v1.1.0`) |
| Bug fix, internal refactor, dependency update with no behavior change | Patch (`v1.0.1`) |

### Cutting a release

Releases are automated via release-please. After merging to `main`:

1. The release-please workflow opens or updates a release PR with a computed version bump and changelog.
2. Merging the release PR creates the semver tag (e.g. `v1.2.0`) and a GitHub release.
3. The floating major tag (e.g. `v1`) is moved forward automatically.

PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/) — the `pr-title-check` workflow enforces this on every PR. The bump is determined by the titles of commits since the last release:

| PR title prefix | Bump |
| --- | --- |
| `feat!:` or `BREAKING CHANGE:` in body | Major |
| `feat:` | Minor |
| `fix:`, `perf:` | Patch |
| `docs:` | No bump |
| `chore:`, `ci:`, `test:`, `refactor:` | No bump |

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

`tooling-ci.yml` runs on every push and pull request. It lints and formats `scripts/` with ruff, then runs the full pytest suite alongside oasdiff and Spectral. No external secrets are required.

To run the same checks locally:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```
