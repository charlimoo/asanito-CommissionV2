# ==============================================================================
# app/__init__.py
# ------------------------------------------------------------------------------
# Application factory for creating and configuring the Flask app instance.
# ==============================================================================

import os
import logging
from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions globally to be accessible by other modules
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    """
    Application factory function. Creates and configures the Flask application.
    
    Args:
        config_class (class): The configuration class to use.
    
    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Configure logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # Ensure the instance folder exists for the SQLite database and other instance-specific files
    try:
        os.makedirs(app.instance_path)
    except OSError:
        # The directory already exists, which is fine.
        pass

    # Initialize extensions with the application instance
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints with the application
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # A simple test route to confirm the app is running can be useful during development
    # @app.route('/test')
    # def test_page():
    #     return '<h1>It works! The Asanito Commission Calculator v2.0 is running.</h1>'

    app.logger.info('Asanito Commission Calculator startup complete')

    @app.cli.command("seed")
    def seed():
        """Seeds the database with default values."""
        from app.seed import seed_data
        seed_data()
        app.logger.info("Database has been seeded with default values.")

    app.logger.info('Asanito Commission Calculator startup complete')
    
    return app