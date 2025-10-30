#!/bin/bash

# Test with curl to see exact error
TOKEN="$1"

if [ -z "$TOKEN" ]; then
    echo "Usage: $0 <auth_token>"
    exit 1
fi

GRID='ver:"3.0" commit:"add"
dis
"Test Site"
'

echo "Testing commit with token: ${TOKEN:0:20}..."
curl -v \
  -X POST \
  "http://ace-skyspark-testing:8080/api/demo/commit" \
  -H "Authorization: Bearer authToken=$TOKEN" \
  -H "Content-Type: text/zinc" \
  -H "Accept: application/json" \
  -d "$GRID"
