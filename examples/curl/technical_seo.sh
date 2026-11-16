#!/usr/bin/env bash
# Audit a URL with the 27 checks of the Semust Technical SEO API.
#   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
#   ./technical_seo.sh
# A request still running after `wait` seconds answers 202; poll the task with the second command.
set -euo pipefail

curl -sS -X POST "https://data.semust.com/v1/technical-seo?wait=60" \
  --max-time 90 \
  -H "Content-Type: application/json" \
  -H "SEMUST-API-USER: ${SEMUST_API_USER}" \
  -H "SEMUST-API-PASSWORD: ${SEMUST_API_PASSWORD}" \
  -d '{
    "url": "https://www.wikipedia.org/"
  }'

# If you received 202, fetch the result with the task_id from the response:
# curl -sS "https://data.semust.com/v1/tasks/$TASK_ID" \
#   -H "SEMUST-API-USER: ${SEMUST_API_USER}" -H "SEMUST-API-PASSWORD: ${SEMUST_API_PASSWORD}"
