#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../backend"

echo "Running migrations from: $(pwd)"
alembic upgrade head
echo "Migrations applied."
