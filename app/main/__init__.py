from flask import Blueprint
from datetime import datetime # <-- Import datetime

bp = Blueprint('main', __name__)

# This function makes the 'datetime' object available in all templates
@bp.app_context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Import routes, filters, and forms at the bottom
from app.main import routes, filters, forms