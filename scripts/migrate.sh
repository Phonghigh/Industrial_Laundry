#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
alembic upgrade head
echo "Migrations applied."
