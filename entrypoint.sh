#!/bin/sh
set -e

INSTANCE_DIR="/app/instance"
DB_FILE="$INSTANCE_DIR/app.db"

echo "Checking instance directory..."
mkdir -p "$INSTANCE_DIR"

# Step 1: Attempt to upgrade the database normally
echo "Applying database migrations..."
if ! flask db upgrade; then
    echo "Migration failed (likely out of sync with existing table). Attempting to sync..."
    
    # Step 2: If upgrade fails, tell Alembic to assume the DB is at the latest version
    # This creates the 'alembic_version' table if it's missing or updates the hash
    flask db stamp head
    
    # Step 3: Attempt upgrade again to catch any actual missing columns
    flask db upgrade
fi

# Step 4: Run seed every time. 
# Your app/seed.py logic already checks 'if not setting', so it won't duplicate data.
echo "Seeding/Updating default settings..."
flask seed

echo "Starting application..."
exec "$@"