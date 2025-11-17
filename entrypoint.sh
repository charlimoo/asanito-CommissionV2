#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Application Startup Logic ---

# It's good practice to wait for the database to be ready, although for SQLite this is instant.
# For PostgreSQL or MySQL, you would add a wait-for-it loop here.

echo "Applying database migrations..."
# The 'flask' command is available because of the PATH set in the Dockerfile.
flask db upgrade

echo "Seeding database with initial data..."
# This will run your `flask seed` command.
flask seed

echo "Database is ready. Starting the application..."

# This is the crucial part: `exec "$@"` executes the command passed as arguments to the script.
# In our case, this will be the `gunicorn` command from the Dockerfile's CMD.
# `exec` replaces the shell process, which is important for proper signal handling (e.g., docker stop).
exec "$@"