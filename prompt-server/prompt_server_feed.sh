#!/usr/bin/env bash
cat "$@" | jq -R . | jq -s . |
	curl -s -S -m 3600 -X POST --json @- http://localhost:8000/prompt > /dev/null

