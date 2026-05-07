#!/bin/bash

# !!!!!!!!!IMPORTANT!!!!!!!!!
# You need to set the environment variables `api_host`, `web_port` and `root_path` before running this script.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!

WEB_PORT="${web_port:-8080}"
API_HOST="${api_host:-127.0.0.1}"

cd "$(dirname "$0")" || exit 1

echo "Starting web server on $API_HOST:$WEB_PORT..."
python3 -m uvicorn api:app --host "$API_HOST" --port "$WEB_PORT"