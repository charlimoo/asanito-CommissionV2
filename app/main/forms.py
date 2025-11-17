# ==============================================================================
# app/main/forms.py
# ------------------------------------------------------------------------------
# Defines web forms using Flask-WTF for user input and validation.
# ==============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SubmitField, SelectField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, InputRequired

class AppSettingForm(FlaskForm):
    """Form for editing a single application setting."""
    value = TextAreaField('مقدار', validators=[DataRequired()], render_kw={'rows': 3})
    submit = SubmitField('ذخیره تغییرات')
    
class AdminLoginForm(FlaskForm):
    """Form for admin login."""
    password = PasswordField('رمز عبور', validators=[InputRequired(message="رمز عبور الزامی است.")])
    submit = SubmitField('ورود')

class CommissionRuleForm(FlaskForm):
    """Form for adding or editing a commission rule."""
    model_name = SelectField(
        'مدل همکاری',
        choices=[('پورسانت خالص', 'پورسانت خالص'), ('حقوق ثابت + پورسانت', 'حقوق ثابت + پورسانت')],
        validators=[InputRequired(message="لطفاً مدل همکاری را انتخاب کنید.")]
    )
    # --- FIX IS HERE ---
    min_sales = FloatField('فروش از (تومان)', validators=[InputRequired(message="این فیلد الزامی است.")])
    max_sales = FloatField('فروش تا (تومان)', validators=[InputRequired(message="این فیلد الزامی است.")])
    marketer_rate = FloatField('نرخ بازاریاب (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    negotiator_rate = FloatField('نرخ مذاکره کننده ارشد (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    coordinator_rate = FloatField('نرخ هماهنگ کننده فروش (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    # --- END OF FIX ---
    submit = SubmitField('ذخیره قانون')

class MonthlyTargetForm(FlaskForm):
    """Form for adding or editing a monthly target."""
    year = IntegerField('سال', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=1400, max=1500)])
    month = IntegerField('ماه', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=1, max=12)])
    # --- FIX IS HERE ---
    collective_target = FloatField('تارگت جمعی (ریال)', validators=[InputRequired(message="این فیلد الزامی است.")])
    individual_target = FloatField('تارگت فرعی (ریال)', validators=[InputRequired(message="این فیلد الزامی است.")])
    # --- END OF FIX ---
    submit = SubmitField('ذخیره تارگت')