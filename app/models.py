# ==============================================================================
# app/models.py
# ------------------------------------------------------------------------------
# Defines the database schema using SQLAlchemy ORM models.
# ==============================================================================

from datetime import datetime
from app import db
import json
class CalculationRun(db.Model):
    """
    Stores metadata for each uploaded file and calculation run.
    Each run is a snapshot of a calculation at a specific time.
    """
    __tablename__ = 'calculation_run'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(128), nullable=False)
    report_period = db.Column(db.String(64), index=True)
    upload_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    
    # Column to store the full, detailed report as a JSON string
    detailed_results_json = db.Column(db.Text, nullable=True)
    targets_json = db.Column(db.Text, nullable=True)
    # Relationship: One CalculationRun has many PersonResults.
    # If a run is deleted, all its associated results are also deleted.
    person_results = db.relationship('PersonResult', backref='calculation_run', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<CalculationRun {self.id}: {self.filename}>'

class PersonResult(db.Model):
    """
    Stores the final summarized results for each person for a specific run.
    """
    __tablename__ = 'person_result'
    id = db.Column(db.Integer, primary_key=True)
    person_name = db.Column(db.String(128), index=True, nullable=False)
    commission_model = db.Column(db.String(64))
    
    total_original_commission = db.Column(db.Float, default=0)
    total_additional_bonus = db.Column(db.Float, default=0)
    total_payable_commission = db.Column(db.Float, default=0)
    total_paid_commission = db.Column(db.Float, default=0)
    remaining_balance = db.Column(db.Float, default=0)
    
    # Foreign Key to link back to the CalculationRun
    calculation_run_id = db.Column(db.Integer, db.ForeignKey('calculation_run.id'), nullable=False)

    def __repr__(self):
        return f'<PersonResult {self.id}: {self.person_name}>'

class CommissionRuleSet(db.Model):
    """
    Stores the commission brackets for each employment model.
    This table is managed via the Admin Panel.
    """
    __tablename__ = 'commission_rule_set'
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(64), nullable=False, index=True)
    min_sales = db.Column(db.Float, nullable=False)
    max_sales = db.Column(db.Float, nullable=False)
    marketer_rate = db.Column(db.Float, default=0)
    negotiator_rate = db.Column(db.Float, default=0)
    coordinator_rate = db.Column(db.Float, default=0)

    def __repr__(self):
        return f'<CommissionRule {self.id}: {self.model_name} ({self.min_sales}-{self.max_sales})>'

class MonthlyTarget(db.Model):
    """
    Stores the monthly targets for bonus calculations.
    This table is managed via the Admin Panel.
    """
    __tablename__ = 'monthly_target'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    collective_target = db.Column(db.Float, default=0) # Stored in Rials
    individual_target = db.Column(db.Float, default=0) # Stored in Rials
    
    # Ensure that there can only be one target entry per year/month combination
    __table_args__ = (db.UniqueConstraint('year', 'month', name='_year_month_uc'),)

    def __repr__(self):
        return f'<MonthlyTarget {self.year}-{self.month}>'
    
    
class AppSetting(db.Model):
    """
    Stores key-value pairs for all application settings and business rules
    that were previously hardcoded. This makes the entire application
    configurable through the admin panel.
    """
    __tablename__ = 'app_setting'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.String(256), nullable=False)
    description = db.Column(db.String(512)) # For hints in the admin panel
    value_type = db.Column(db.String(32), default='string') # e.g., 'float', 'int', 'string', 'json'

    def __repr__(self):
        return f'<AppSetting {self.key}: {self.value}>'

    def get_value(self):
        """Casts the string value to its correct Python type."""
        if self.value_type == 'float':
            return float(self.value)
        if self.value_type == 'int':
            return int(self.value)
        if self.value_type == 'json':
            return json.loads(self.value)
        return self.value