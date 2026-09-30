#!/usr/bin/env bash
# Kept as a file rather than inline in action.yml so openapi-checks can run it
# through its own action path: a `uses: ./...` inside a composite resolves
# against the caller's workspace, not this repo.
#
# No `set -e`/`-u`/`pipefail` on purpose: a notification is best-effort and must
# never fail the calling job.

if [ -z "$WEBHOOK_URL" ]; then
  echo "No Teams webhook URL set - notification skipped." >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

if jq -se 'length == 1 and (.[0] | type) == "object"' <<< "$MESSAGE" > /dev/null 2>&1; then
  payload="$MESSAGE"
else
  # Adaptive Card, not {"text": ...}: Teams Workflows webhooks accept the plain
  # text shape with a 202 and then drop it, so nothing reaches the channel and
  # nothing fails. The card envelope is what both Workflows and the legacy
  # Incoming Webhook connector render.
  payload=$(jq -n --arg text "$MESSAGE" '{
    type: "message",
    attachments: [{
      contentType: "application/vnd.microsoft.card.adaptive",
      content: {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        type: "AdaptiveCard",
        version: "1.4",
        body: [{type: "TextBlock", text: $text, wrap: true}]
      }
    }]
  }')
fi

curl -sSf --max-time 30 -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$payload" \
  || {
    echo "::warning::Teams notification failed"
    echo "Teams notification failed - see the run log." >> "$GITHUB_STEP_SUMMARY"
  }
