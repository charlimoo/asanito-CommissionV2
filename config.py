# =' ' =============================================================================
# config.py
# ------------------------------------------------------------------------------
# Configuration settings for the Flask application.
# Uses environment variables for sensitive data to keep them out of version control.
# ==============================================================================

import os
from dotenv import load_dotenv

# Determine the absolute path of the project directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from a .env file located in the project root
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """
    Base configuration class. Contains default settings that can be overridden
    by environment-specific configurations.
    """
    # --- Security ---
    # A strong, random secret key is crucial for session security and CSRF protection.
    # It's loaded from an environment variable for security.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-should-really-set-a-secret-key-in-your-env-file'
    
    # Custom configuration for the admin password
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'change-this-default-password'

    # --- Database Configuration ---
    # Configures the application to use SQLite, which is simple and file-based.
    # The database file will be located in the 'instance' folder.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance/app.db')
    
    # Disable an SQLAlchemy feature that is not needed and adds overhead.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- File Upload Configuration ---
    # Defines the folder where uploaded files will be temporarily stored.
    UPLOAD_FOLDER = os.path.join(basedir, 'instance/uploads')
    
    # Specifies the allowed file extension for uploads.
    ALLOWED_EXTENSIONS = {'.xlsx'}

    # Optional: Set a maximum file size for uploads (e.g., 16 MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    WKHTMLTOPDF_PATH = os.environ.get('WKHTMLTOPDF_PATH') or None