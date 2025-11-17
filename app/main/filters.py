# ==============================================================================
# app/main/filters.py
# ------------------------------------------------------------------------------
# Defines custom Jinja2 template filters for the application.
# ==============================================================================

from app.main import bp

@bp.app_template_filter('to_persian_int')
def to_persian_int_filter(s):
    """
    Formats an integer with Persian/Arabic thousands separators.
    Example: 1234567 -> "1,234,567"
    """
    try:
        # Round to handle potential floats, then convert to int
        return "{:,}".format(int(round(float(s))))
    except (ValueError, TypeError):
        return s