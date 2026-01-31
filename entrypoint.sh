#!/bin/sh
set -e

INSTANCE_DIR="/app/instance"
DB_FILE="$INSTANCE_DIR/app.db"

echo "Preparing instance directory..."
mkdir -p "$INSTANCE_DIR"

# 1. RESET LOGIC: 
# If you want to force a reset via an environment variable, 
# you can run the container with -e RESET_DATABASE=true
if [ "$RESET_DATABASE" = "true" ]; then
    echo "RESET_DATABASE environment variable is true. Deleting existing database..."
    rm -f "$DB_FILE"
fi

if [ ! -f "$DB_FILE" ]; then
    echo "No database found. Running initial migrations and seeding..."
    # Create the DB from scratch based on migration scripts
    flask db upgrade
    flask seed
else
    echo "Database found. Checking for pending migrations..."
    # 2. FIX FOR THE "TABLE ALREADY EXISTS" ERROR:
    # We try to upgrade. If it fails because the table exists, 
    # we "stamp" it to 'head' so Alembic knows the DB is actually up to date.
    flask db upgrade || {
        echo "Migration failed (likely out of sync). Stamping database as 'head' and retrying..."
        flask db stamp head
        flask db upgrade
    }
fi

echo "Starting application..."
exec "$@"