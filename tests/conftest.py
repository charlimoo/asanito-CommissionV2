# tests/conftest.py

import pytest

@pytest.fixture(scope="module")
def app_with_db():
    """
    Creates a new app instance for a test module, sets up an in-memory database,
    and yields the app within an application context.
    """
    from app import create_app, db

    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })

    with app.app_context():
        db.create_all()
        yield app  # The tests will run here
        db.drop_all()