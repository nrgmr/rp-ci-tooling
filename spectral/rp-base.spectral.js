// Shared RP OpenAPI quality rules.
//
// This ruleset is intentionally limited to spec shape and documentation checks
// that should always fail fast during Spectral linting. It also requires each
// non-probe API path to contain exactly one version segment, such as /v1.
//
// Route-version lifecycle policy, such as the maximum number of live versions
// and whether those versions are consecutive, lives in
// scripts/openapi_version_limit_check.py. That script has explicit exit-code
// semantics so the composite action can support override-version-limit without
// weakening this base ruleset or service-level .spectral.yaml overrides.
const { truthy } = require("@stoplight/spectral-functions");
const { oas } = require("@stoplight/spectral-rulesets");

const HTTP_METHODS = ["get", "post", "put", "patch", "delete", "head", "options", "trace"];
const OPERATION_SELECTOR = "$.paths[*][get,post,put,patch,delete,head,options,trace]";
const VERSION_SEGMENT = /\/v(\d+)(?=\/|$)/g;

function versionedPathCheck(paths) {
  const errors = [];

  for (const [pathKey, pathItem] of Object.entries(paths)) {
    const ops = HTTP_METHODS.map((m) => pathItem?.[m]).filter(
      (op) => op && typeof op === "object"
    );
    if (ops.length === 0) continue;
    if (ops.every((op) => Array.isArray(op.tags) && op.tags.includes("probe"))) continue;

    const matches = [...pathKey.matchAll(VERSION_SEGMENT)];
    if (matches.length === 0) {
      errors.push({
        message: `"${pathKey}" must contain exactly one version segment like /v1.`,
        path: [pathKey],
      });
    } else if (matches.length > 1) {
      errors.push({
        message: `"${pathKey}" contains ${matches.length} version segments - only one segment like /v1 is allowed.`,
        path: [pathKey],
      });
    }
  }

  return errors;
}

module.exports = {
  extends: [oas],
  rules: {
    // App-level
    "info-license": "off", // FastAPI doesn't populate info.license
    "info-contact": "error", // contact object required in FastAPI(...) constructor

    // Operation-level
    "operation-summary": {
      severity: "error",
      given: OPERATION_SELECTOR,
      then: { field: "summary", function: truthy },
    },
    "operation-description": "error",
    "operation-success-response": "error",

    // Response-level
    "response-description": {
      severity: "error",
      given: "$..responses[*]",
      then: { field: "description", function: truthy },
    },

    // Tags
    "operation-tag-defined": "error",
    "tag-description": "error",

    // Versioned paths
    "versioned-path": {
      severity: "error",
      given: "$.paths",
      then: { function: versionedPathCheck },
    },
  },
};
