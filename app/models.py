# start of app/models.py
# ==============================================================================
# app/models.py
# ------------------------------------------------------------------------------
# Defines the database schema using SQLAlchemy ORM models.
# ==============================================================================

from datetime import datetime
from app import db
import json
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

class CalculationRun(db.Model):
    """
    Stores metadata for each uploaded file and calculation run.
    Each run is a snapshot of a calculation at a specific time.
    """
    __tablename__ = 'calculation_run'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(128), nullable=False)
    report_period = db.Column(db.String(64), index=True)
    upload_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    
    # Column to store the full, detailed report as a JSON string
    detailed_results_json = db.Column(db.Text, nullable=True)
    targets_json = db.Column(db.Text, nullable=True)
    
    # Relationship: One CalculationRun has many PersonResults.
    person_results = db.relationship('PersonResult', backref='calculation_run', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<CalculationRun {self.id}: {self.filename}>'

class PersonResult(db.Model):
    """
    Stores the final summarized results for each person for a specific run.
    Updated to include the 12-column logic for the new reporting standards.
    """
    __tablename__ = 'person_result'
    id = db.Column(db.Integer, primary_key=True)
    person_name = db.Column(db.String(128), index=True, nullable=False)
    commission_model = db.Column(db.String(64))
    
    # --- 1. The Input Metrics ---
    # کل اعلامی: Total invoice amount before changes
    total_declared = db.Column(db.Float, default=0)
    # کل مبنا: Total commissionable base (after exclusions)
    total_base = db.Column(db.Float, default=0)
    # کل قابل قبول: Total base of deals that met the 30% + Min Value threshold
    total_acceptable = db.Column(db.Float, default=0)
    
    # --- 2. Commission Metrics ---
    # پورسانت بر اساس کل مبنا: Potential commission ignoring thresholds
    commission_base = db.Column(db.Float, default=0)
    # پورسانت قابل قبول: Commission on acceptable deals only
    commission_acceptable = db.Column(db.Float, default=0)
    # پورسانت وصول شده: Acceptable Commission * Collection Ratio
    commission_collected = db.Column(db.Float, default=0)
    
    # --- 3. Bonus Metrics ---
    # پاداش مبنا: Bonus calculated on Total Base
    bonus_base = db.Column(db.Float, default=0)
    # پاداش قابل قبول: Bonus calculated on Total Acceptable
    bonus_acceptable = db.Column(db.Float, default=0)
    # پاداش وصول شده: Cash portion of the bonus
    bonus_collected = db.Column(db.Float, default=0)
    
    # --- 4. Final Aggregates ---
    # قابل پرداخت: commission_collected + bonus_collected
    payable_amount = db.Column(db.Float, default=0)
    # مبلغ پرداخت شده (Manually entered from Excel)
    total_paid_commission = db.Column(db.Float, default=0)
    
    # مانده دریافتی وصول قابل قبول
    # (commission_acceptable + bonus_acceptable) - payable_amount
    # Note: In the context of "Remaining Balance", usually it is (Payable - Paid).
    # But strictly following the prompt's definition:
    remaining_acceptable = db.Column(db.Float, default=0)
    
    # مانده دریافتی وصول مبنا
    # (commission_base + bonus_base) - payable_amount
    remaining_base = db.Column(db.Float, default=0)
    
    # Legacy fields (kept for backward compatibility if needed, though replaced by above)
    total_original_commission = db.Column(db.Float, default=0)
    total_additional_bonus = db.Column(db.Float, default=0)
    total_payable_commission = db.Column(db.Float, default=0) # Same as payable_amount
    total_full_commission = db.Column(db.Float, default=0)
    total_pending_commission = db.Column(db.Float, default=0)
    remaining_balance = db.Column(db.Float, default=0) # Usually (payable - paid)

    # Foreign Key
    calculation_run_id = db.Column(db.Integer, db.ForeignKey('calculation_run.id'), nullable=False)

    def __repr__(self):
        return f'<PersonResult {self.id}: {self.person_name}>'

class CommissionRuleSet(db.Model):
    """
    Stores the commission brackets for each employment model.
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
    """
    __tablename__ = 'monthly_target'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    collective_target = db.Column(db.Float, default=0)
    individual_target = db.Column(db.Float, default=0)
    
    __table_args__ = (db.UniqueConstraint('year', 'month', name='_year_month_uc'),)

    def __repr__(self):
        return f'<MonthlyTarget {self.year}-{self.month}>'
    
class AppSetting(db.Model):
    """
    Stores key-value pairs for application settings.
    """
    __tablename__ = 'app_setting'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.String(256), nullable=False)
    description = db.Column(db.String(512))
    value_type = db.Column(db.String(32), default='string')

    def __repr__(self):
        return f'<AppSetting {self.key}: {self.value}>'

    def get_value(self):
        if self.value_type == 'float':
            return float(self.value)
        if self.value_type == 'int':
            return int(self.value)
        if self.value_type == 'json':
            return json.loads(self.value)
        return self.value
    
class User(db.Model):
    """
    Stores user credentials.
    """
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(128), index=True, unique=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'
# end of app/models.py