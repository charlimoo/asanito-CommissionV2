#!/bin/sh
set -e

INSTANCE_DIR="/app/instance"
DB_FILE="$INSTANCE_DIR/app.db"   # CHANGE this to your real DB filename

echo "Preparing instance directory..."
mkdir -p "$INSTANCE_DIR"

# Ensure the app user actually owns it (important when Kubernetes mounts volumes)
chown -R app:app "$INSTANCE_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "No database found. Running initial migrations and seeding..."
    flask db upgrade
    flask seed
else
    echo "Database found. Running migrations only..."
    flask db upgrade
fi

echo "Starting application..."
exec "$@"
