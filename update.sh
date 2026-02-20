#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

git pull --ff-only

if [ -d RELEASE/.git ]; then
  (cd RELEASE && git pull --ff-only && git check v2023.1.8)
fi

docker compose pull
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps