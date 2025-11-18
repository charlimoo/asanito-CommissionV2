# ==============================================================================
# app/main/forms.py
# ------------------------------------------------------------------------------
# Defines web forms using Flask-WTF for user input and validation.
# ==============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SubmitField, SelectField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, InputRequired, EqualTo, Optional

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
    min_sales = FloatField('فروش از (تومان)', validators=[InputRequired(message="این فیلد الزامی است.")])
    max_sales = FloatField('فروش تا (تومان)', validators=[InputRequired(message="این فیلد الزامی است.")])
    marketer_rate = FloatField('نرخ بازاریاب (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    negotiator_rate = FloatField('نرخ مذاکره کننده ارشد (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    coordinator_rate = FloatField('نرخ هماهنگ کننده فروش (%)', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=0, max=100)])
    submit = SubmitField('ذخیره قانون')

class MonthlyTargetForm(FlaskForm):
    """Form for adding or editing a monthly target."""
    year = IntegerField('سال', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=1400, max=1500)])
    month = IntegerField('ماه', validators=[InputRequired(message="این فیلد الزامی است."), NumberRange(min=1, max=12)])
    collective_target = FloatField('تارگت جمعی (ریال)', validators=[InputRequired(message="این فیلد الزامی است.")])
    individual_target = FloatField('تارگت فرعی (ریال)', validators=[InputRequired(message="این فیلد الزامی است.")])
    submit = SubmitField('ذخیره تارگت')

class UserForm(FlaskForm):
    """Form for adding a new user."""
    username = StringField('نام کاربری (انگلیسی)', validators=[DataRequired(message="این فیلد الزامی است.")])
    name = StringField('نام کامل (دقیقاً مطابق با نام در فایل اکسل)', validators=[DataRequired(message="این فیلد الزامی است.")])
    password = PasswordField('رمز عبور', validators=[DataRequired(message="این فیلد الزامی است.")])
    password2 = PasswordField(
        'تکرار رمز عبور', 
        validators=[DataRequired(message="این فیلد الزامی است."), EqualTo('password', message='رمزهای عبور باید مطابقت داشته باشند.')]
    )
    submit = SubmitField('ذخیره کاربر')

class EditUserForm(FlaskForm):
    """Form for editing an existing user. Password is optional."""
    username = StringField('نام کاربری (انگلیسی)', validators=[DataRequired(message="این فیلد الزامی است.")])
    name = StringField('نام کامل (دقیقاً مطابق با نام در فایل اکسل)', validators=[DataRequired(message="این فیلد الزامی است.")])
    password = PasswordField('رمز عبور جدید (برای تغییر خالی بگذارید)', validators=[Optional()])
    password2 = PasswordField(
        'تکرار رمز عبور', 
        validators=[EqualTo('password', message='رمزهای عبور باید مطابقت داشته باشند.')]
    )
    submit = SubmitField('ذخیره تغییرات')


class UserLoginForm(FlaskForm):
    """Form for a standard user to log in to view their report."""
    password = PasswordField('رمز عبور', validators=[InputRequired(message="رمز عبور الزامی است.")])
    submit = SubmitField('مشاهده گزارش')