#!/bin/sh
set -e

INSTANCE_DIR="/app/instance"
DB_FILE="$INSTANCE_DIR/app.db"   # <--- change to your actual DB filename

echo "Preparing instance directory..."
mkdir -p "$INSTANCE_DIR"

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
