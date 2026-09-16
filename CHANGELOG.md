# Changelog

## [0.2.0](https://github.com/nrgmr/rp-ci-tooling/compare/v0.1.0...v0.2.0) (2026-09-16)


### Features

* add release-bot-token branch promotion workflows ([6fc0bea](https://github.com/nrgmr/rp-ci-tooling/commit/6fc0beaeed4b354faa678ed015254a5274ca7b83))
* add release-bot-token branch promotion workflows AB[#33175](https://github.com/nrgmr/rp-ci-tooling/issues/33175) ([e884150](https://github.com/nrgmr/rp-ci-tooling/commit/e88415042ca778e100210b7eabc485ae12d78309))
* fail loudly on fork-head merges in back-merge.yml ([42d80f6](https://github.com/nrgmr/rp-ci-tooling/commit/42d80f645d9e30555997a3d2a93052da8762804f))


### Bug Fixes

* address PR review findings on release-bot-token workflows ([2f73755](https://github.com/nrgmr/rp-ci-tooling/commit/2f7375509ef8abe779b9a3963479ea6a5eff503d))
* **release:** correct jsonpath filter for uv.lock version updater ([bf789b2](https://github.com/nrgmr/rp-ci-tooling/commit/bf789b23738f71e83468cc08fe7e7484073dd208))
* **release:** correct jsonpath filter for uv.lock version updater ([e420870](https://github.com/nrgmr/rp-ci-tooling/commit/e420870cbe82842c7333d50311a65f6ac06a68ef))
* **release:** keep uv.lock version in sync with release-please bumps ([e59b4c0](https://github.com/nrgmr/rp-ci-tooling/commit/e59b4c0a7d2b9f080c97938a106d6f8da022bf26))
* **release:** keep uv.lock version in sync with release-please bumps ([bd5b03b](https://github.com/nrgmr/rp-ci-tooling/commit/bd5b03b94a0d0b52b103f8860beee90040acf2d6))

## 0.1.0 (2026-06-08)


### Features

* add 80% coverage enforcement and fix duplicate CI runs ([753be82](https://github.com/nrgmr/rp-ci-tooling/commit/753be82e58512f2efa4b60db57b993d1f5946239))
* initial reusable CI/CD workflows and tooling ([2b587e7](https://github.com/nrgmr/rp-ci-tooling/commit/2b587e73255c7f4ef352f011b123b2f09583f515))
* initial reusable CI/CD workflows and tooling AB[#28657](https://github.com/nrgmr/rp-ci-tooling/issues/28657) ([e5cee82](https://github.com/nrgmr/rp-ci-tooling/commit/e5cee82ce607ec8cac9e4355023ebdcd1267d67f))
* promote service-account and gar-project from secrets to inputs ([d3ab4d0](https://github.com/nrgmr/rp-ci-tooling/commit/d3ab4d0c4f0121f82e066ebf6ac889044898259e))
* promote workload-identity-provider from secret to workflow input ([ec2c16a](https://github.com/nrgmr/rp-ci-tooling/commit/ec2c16a05e9bc5ac0ce9c442e05a0e9fe09a3668))


### Bug Fixes

* correct oasdiff download filename for v1.15.3 ([6c24136](https://github.com/nrgmr/rp-ci-tooling/commit/6c24136b98a5323e9de1c85b144268c13b720443))
* move working-directory from defaults to each run step ([ef0e4bf](https://github.com/nrgmr/rp-ci-tooling/commit/ef0e4bf4196e5878637e01bc86dd2466955446f4))
* queue concurrent release-please runs instead of racing ([8a23ec1](https://github.com/nrgmr/rp-ci-tooling/commit/8a23ec1a86de21edf912047c891066dc13f7597e))
* **workflow:** accept ci-tooling-token secret for self-checkout ([d55823c](https://github.com/nrgmr/rp-ci-tooling/commit/d55823c8dd12b8a4b2a9c8aff2e42c7f18f7cf49))
* **workflow:** quote verify-spec run step to fix YAML parse error ([ae0f18b](https://github.com/nrgmr/rp-ci-tooling/commit/ae0f18be85140f36da32483bfa3cebda7da4db7e))
* **workflow:** remove empty secrets key from workflow_call inputs ([c6c4ac5](https://github.com/nrgmr/rp-ci-tooling/commit/c6c4ac5e7141fede545631bcfd5d1b47f1dbed3d))
* **workflow:** use pull_request_target so fork PRs can report title check status ([eddb532](https://github.com/nrgmr/rp-ci-tooling/commit/eddb532aed8724ffce141f39a3ce5672b8f08768))
