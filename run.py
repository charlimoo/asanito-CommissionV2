# ==============================================================================
# run.py
# ------------------------------------------------------------------------------
# The main entry point to launch the Flask application.
# ==============================================================================

from app import create_app, db
from app.models import AppSetting, CommissionRuleSet, MonthlyTarget, User

# Create the Flask application instance using the factory function
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Provides a shell context for the `flask shell` command."""
    return {
        'db': db,
        'AppSetting': AppSetting,
        'CommissionRuleSet': CommissionRuleSet,
        'MonthlyTarget': MonthlyTarget,
        'User': User
    }

if __name__ == '__main__':
    app.run(debug=True)