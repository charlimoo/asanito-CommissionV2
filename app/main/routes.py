# ==============================================================================
# app/main/routes.py
# ------------------------------------------------------------------------------
# Defines all user-facing routes for the main application blueprint.
# This file acts as the main controller for the web interface.
# ==============================================================================

import os
import json
from datetime import datetime
from functools import wraps
import pandas as pd
from flask import (render_template, request, flash, redirect, url_for, 
                   current_app, session, Response)
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
import pdfkit

from app import db
from app.main import bp
from app.models import CalculationRun, PersonResult, CommissionRuleSet, MonthlyTarget, AppSetting, User
from app.calculator.validator import validate_excel_file
from app.calculator.engine import calculate_commissions, summarize_results, CalculationConfig
from app.main.forms import (AdminLoginForm, CommissionRuleForm, MonthlyTargetForm, AppSettingForm, 
                            UserForm, EditUserForm, UserLoginForm)
from app.main.utils import prepare_frontend_data, _perform_frontend_aggregation

# --- Helper Functions ---

def allowed_file(filename):
    """Checks if the file extension is allowed based on the app config."""
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def admin_required(f):
    """Decorator to protect admin routes with session-based authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('برای دسترسی به این صفحه باید به پنل مدیریت وارد شوید.', 'warning')
            return redirect(url_for('main.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Main Application Routes ---

@bp.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page with the file uploader."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('هیچ فایلی در درخواست وجود ندارد.', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('هیچ فایلی انتخاب نشده است.', 'warning')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)

            dataframes, errors = validate_excel_file(filepath)
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return redirect(request.url)
            
            try:
                results, config = calculate_commissions(dataframes)
                summary_data = summarize_results(results, dataframes.get('Commissions paid'), config)

                months_in_report = sorted(results.keys())
                period_string = f"{months_in_report[0]} to {months_in_report[-1]}" if months_in_report else "N/A"

                targets_df = dataframes.get('Additional commissions')
                targets_json_str = targets_df.to_json(orient='records') if targets_df is not None else '[]'

                new_run = CalculationRun(
                    filename=filename,
                    report_period=period_string,
                    upload_timestamp=datetime.utcnow(),
                    detailed_results_json=json.dumps(results, ensure_ascii=False),
                    targets_json=targets_json_str
                )
                db.session.add(new_run)
                db.session.flush()

                for person_name, data in summary_data.items():
                    person_result = PersonResult(
                        person_name=person_name, commission_model=data['commission_model'],
                        total_original_commission=data['total_original_commission'],
                        total_additional_bonus=data['total_additional_bonus'],
                        total_payable_commission=data['total_payable_commission'],
                        total_paid_commission=data['total_paid_commission'],
                        total_full_commission=data['total_full_commission'],
                        total_pending_commission=data['total_pending_commission'],
                        remaining_balance=data['remaining_balance'], calculation_run_id=new_run.id
                    )
                    db.session.add(person_result)
                
                db.session.commit()
                flash('محاسبات با موفقیت انجام و ذخیره شد.', 'success')
                return redirect(url_for('main.admin_master_report', public_id=new_run.public_id))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Calculation or database operation failed: {e}", exc_info=True)
                flash(f'یک خطای غیرمنتظره در حین محاسبه رخ داد. لطفاً لاگ سرور را بررسی کنید. خطا: {e}', 'danger')
                return redirect(request.url)

        else:
            flash('نوع فایل مجاز نیست. لطفاً یک فایل .xlsx بارگذاری کنید.', 'danger')
            return redirect(request.url)

    return render_template('index.html')

@bp.route('/history')
@admin_required
def history():
    """Displays a list of all past calculation runs for the admin."""
    runs = CalculationRun.query.order_by(CalculationRun.upload_timestamp.desc()).all()
    for run in runs:
        run.person_names = [p.person_name for p in run.person_results]
        run.users = User.query.filter(User.name.in_(run.person_names)).all()
    return render_template('history.html', runs=runs)

# --- NEW REPORTING AND LOGIN FLOW ---

@bp.route('/login/<public_id>/<username>', methods=['GET', 'POST'])
def user_login(public_id, username):
    """Login page for a specific user to view a specific report."""
    run = CalculationRun.query.filter_by(public_id=public_id).first_or_404()
    user = User.query.filter_by(username=username).first_or_404()
    
    person_exists = PersonResult.query.filter_by(calculation_run_id=run.id, person_name=user.name).first()
    if not person_exists:
        flash('شما به این گزارش دسترسی ندارید.', 'danger')
        return redirect(url_for('main.index'))

    form = UserLoginForm()
    if form.validate_on_submit():
        if user.check_password(form.password.data):
            session['report_access_user'] = user.username
            session['report_access_id'] = run.public_id
            return redirect(url_for('main.view_user_report', public_id=run.public_id, username=user.username))
        else:
            flash('رمز عبور نامعتبر است.', 'danger')
            
    return render_template('user_login.html', form=form, user=user, run=run)

@bp.route('/report/<public_id>/<username>')
def view_user_report(public_id, username):
    """Displays a filtered, secure report for a single user."""
    # --- DEBUG LOG ---
    current_app.logger.info("="*50)
    current_app.logger.info(f"ENTERING 'view_user_report' for user: '{username}', report: '{public_id}'")
    
    if session.get('report_access_user') != username or session.get('report_access_id') != public_id:
        # --- DEBUG LOG ---
        current_app.logger.warning(f"SESSION CHECK FAILED! Session user: '{session.get('report_access_user')}', Session report: '{session.get('report_access_id')}'")
        flash('برای مشاهده این گزارش ابتدا باید وارد شوید.', 'warning')
        return redirect(url_for('main.user_login', public_id=public_id, username=username))

    # --- DEBUG LOG ---
    current_app.logger.info("Session check PASSED.")
    
    run = CalculationRun.query.filter_by(public_id=public_id).first_or_404()
    user = User.query.filter_by(username=username).first_or_404()
    
    # --- DEBUG LOG ---
    current_app.logger.info(f"Successfully fetched User object. User's full name from DB is: '{user.name}'")
    
    if not run.detailed_results_json:
        flash('اطلاعات دقیق برای این گزارش یافت نشد.', 'danger')
        return redirect(url_for('main.index'))

    full_results = json.loads(run.detailed_results_json)
    all_person_results = PersonResult.query.filter_by(calculation_run_id=run.id).all()
    
    # --- DEBUG LOG ---
    all_names_in_report = [p.person_name for p in all_person_results]
    current_app.logger.info(f"All person names found in this report's PersonResult table: {all_names_in_report}")
    
    # --- THIS IS THE MOST IMPORTANT CHECK ---
    user_name_to_filter = user.name
    user_has_data = user_name_to_filter in all_names_in_report
    # --- DEBUG LOG ---
    current_app.logger.info(f"The name to filter by is: '{user_name_to_filter}'")
    current_app.logger.info(f"Is the user's name in the report's list of people? {'YES' if user_has_data else 'NO'}")

    if not user_has_data:
        flash(f'اطلاعاتی برای کاربر "{user.name}" در این گزارش یافت نشد.', 'warning')
        return redirect(url_for('main.index'))
        
    full_summary_data = {}
    for res in all_person_results:
        full_summary_data[res.person_name] = {
            'person_name': res.person_name, 'commission_model': res.commission_model,
            'total_original_commission': res.total_original_commission,
            'total_additional_bonus': res.total_additional_bonus,
            'total_payable_commission': res.total_payable_commission,
            'total_paid_commission': res.total_paid_commission,
            'total_full_commission': res.total_full_commission,
            'total_pending_commission': res.total_pending_commission,
            'remaining_balance': res.remaining_balance
        }
    
    targets_df = pd.read_json(run.targets_json, orient='records') if run.targets_json else pd.DataFrame()
    frontend_data = prepare_frontend_data(
        full_results, 
        full_summary_data, 
        targets_df, 
        filter_person_name=user.name
    )
    
    # --- DEBUG LOG ---
    current_app.logger.info(f"Data prepared for template. Number of people in final data: {len(frontend_data['personList'])}")
    current_app.logger.info("="*50)
    
    return render_template(
        'report.html', 
        run=run,
        frontend_data=frontend_data,
        overall_summary=frontend_data['overallSummary'],
        detailed_report=frontend_data['detailedReport'],
        person_monthly_report=frontend_data['personMonthlyReport'],
        person_list=frontend_data['personList'],
        is_user_view=True
    )

# --- DEPRECATED/OLD ROUTES ---
@bp.route('/report/<int:run_id>')
def view_report(run_id):
    flash('این لینک گزارش منقضی شده است. لطفاً از لینک‌های جدید در صفحه تاریخچه استفاده کنید.', 'info')
    if session.get('admin_logged_in'):
        return redirect(url_for('main.history'))
    return redirect(url_for('main.index'))

# ... [The rest of the routes.py file is unchanged from before] ...
# --- Admin Panel Routes ---
@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles admin login."""
    form = AdminLoginForm()
    if form.validate_on_submit():
        if form.password.data == current_app.config.get('ADMIN_PASSWORD', 'default_password'):
            session['admin_logged_in'] = True
            flash('شما با موفقیت وارد شدید.', 'success')
            return redirect(url_for('main.admin_dashboard'))
        else:
            flash('رمز عبور نامعتبر است.', 'danger')
    return render_template('admin_login.html', form=form, title='ورود به پنل مدیریت')

@bp.route('/admin/logout')
def admin_logout():
    """Handles admin logout."""
    session.pop('admin_logged_in', None)
    session.pop('report_access_user', None) # Also clear user session
    session.pop('report_access_id', None)
    flash('شما با موفقیت خارج شدید.', 'info')
    return redirect(url_for('main.index'))

@bp.route('/admin')
@admin_required
def admin_dashboard():
    """Main admin dashboard showing rules and targets."""
    rules = CommissionRuleSet.query.order_by(CommissionRuleSet.model_name, CommissionRuleSet.min_sales).all()
    targets = MonthlyTarget.query.order_by(MonthlyTarget.year.desc(), MonthlyTarget.month.desc()).all()
    return render_template('admin.html', rules=rules, targets=targets)
    
@bp.route('/admin/report/<public_id>')
@admin_required
def admin_master_report(public_id):
    """Displays the full, unfiltered report for an administrator."""
    run = CalculationRun.query.filter_by(public_id=public_id).first_or_404()
    
    if not run.detailed_results_json:
        flash('اطلاعات دقیق برای این گزارش یافت نشد.', 'danger')
        return redirect(url_for('main.history'))

    results = json.loads(run.detailed_results_json)
    person_results_query = PersonResult.query.filter_by(calculation_run_id=run.id).all()
    summary_data = {}
    for res in person_results_query:
        summary_data[res.person_name] = {
            'person_name': res.person_name, 'commission_model': res.commission_model,
            'total_original_commission': res.total_original_commission,
            'total_additional_bonus': res.total_additional_bonus,
            'total_payable_commission': res.total_payable_commission,
            'total_paid_commission': res.total_paid_commission,
            'total_full_commission': res.total_full_commission,
            'total_pending_commission': res.total_pending_commission,
            'remaining_balance': res.remaining_balance
        }
    
    targets_df = pd.read_json(run.targets_json, orient='records') if run.targets_json else pd.DataFrame()
    frontend_data = prepare_frontend_data(results, summary_data, targets_df)
    
    return render_template(
        'report.html', 
        run=run,
        frontend_data=frontend_data,
        overall_summary=frontend_data['overallSummary'],
        detailed_report=frontend_data['detailedReport'],
        person_monthly_report=frontend_data['personMonthlyReport'],
        person_list=frontend_data['personList'],
        is_user_view=False
    )

@bp.route('/admin/rule/add', methods=['GET', 'POST'])
@admin_required
def add_rule():
    form = CommissionRuleForm()
    if form.validate_on_submit():
        new_rule = CommissionRuleSet(model_name=form.model_name.data, min_sales=form.min_sales.data, max_sales=form.max_sales.data, marketer_rate=form.marketer_rate.data / 100, negotiator_rate=form.negotiator_rate.data / 100, coordinator_rate=form.coordinator_rate.data / 100)
        db.session.add(new_rule)
        db.session.commit()
        flash('قانون پورسانت جدید با موفقیت اضافه شد.', 'success')
        return redirect(url_for('main.admin_dashboard'))
    return render_template('admin_form.html', form=form, title='افزودن قانون پورسانت جدید')

@bp.route('/admin/rule/edit/<int:rule_id>', methods=['GET', 'POST'])
@admin_required
def edit_rule(rule_id):
    rule = CommissionRuleSet.query.get_or_404(rule_id)
    form = CommissionRuleForm(obj=rule)
    if request.method == 'GET':
        form.marketer_rate.data = rule.marketer_rate * 100
        form.negotiator_rate.data = rule.negotiator_rate * 100
        form.coordinator_rate.data = rule.coordinator_rate * 100
    if form.validate_on_submit():
        rule.model_name = form.model_name.data
        rule.min_sales = form.min_sales.data
        rule.max_sales = form.max_sales.data
        rule.marketer_rate = form.marketer_rate.data / 100
        rule.negotiator_rate = form.negotiator_rate.data / 100
        rule.coordinator_rate = form.coordinator_rate.data / 100
        db.session.commit()
        flash('قانون پورسانت با موفقیت ویرایش شد.', 'success')
        return redirect(url_for('main.admin_dashboard'))
    return render_template('admin_form.html', form=form, title='ویرایش قانون پورسانت')

@bp.route('/admin/rule/delete/<int:rule_id>', methods=['POST'])
@admin_required
def delete_rule(rule_id):
    rule = CommissionRuleSet.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('قانون پورسانت حذف شد.', 'success')
    return redirect(url_for('main.admin_dashboard'))

@bp.route('/admin/target/add', methods=['GET', 'POST'])
@admin_required
def add_target():
    form = MonthlyTargetForm()
    if form.validate_on_submit():
        new_target = MonthlyTarget(year=form.year.data, month=form.month.data, collective_target=form.collective_target.data, individual_target=form.individual_target.data)
        db.session.add(new_target)
        db.session.commit()
        flash('تارگت ماهانه جدید با موفقیت اضافه شد.', 'success')
        return redirect(url_for('main.admin_dashboard'))
    return render_template('admin_form.html', form=form, title='افزودن تارگت ماهانه')

@bp.route('/admin/target/delete/<int:target_id>', methods=['POST'])
@admin_required
def delete_target(target_id):
    target = MonthlyTarget.query.get_or_404(target_id)
    db.session.delete(target)
    db.session.commit()
    flash('تارگت ماهانه حذف شد.', 'success')
    return redirect(url_for('main.admin_dashboard'))

@bp.route('/admin/settings', methods=['GET'])
@admin_required
def admin_settings():
    settings = AppSetting.query.order_by(AppSetting.key).all()
    return render_template('admin_settings.html', settings=settings)

@bp.route('/admin/setting/edit/<int:setting_id>', methods=['GET', 'POST'])
@admin_required
def edit_setting(setting_id):
    setting = AppSetting.query.get_or_404(setting_id)
    form = AppSettingForm(obj=setting)
    if form.validate_on_submit():
        new_value = form.value.data
        if setting.value_type == 'json':
            try:
                parsed_json = json.loads(new_value)
                new_value = json.dumps(parsed_json, ensure_ascii=False)
            except json.JSONDecodeError:
                flash('مقدار وارد شده برای این تنظیم یک JSON معتبر نیست.', 'danger')
                return render_template('admin_form.html', form=form, title=f'ویرایش تنظیم: {setting.key}', description=setting.description)
        setting.value = new_value
        db.session.commit()
        from app.calculator.engine import CalculationConfig
        CalculationConfig._instance = None
        flash(f'تنظیم "{setting.key}" با موفقیت ویرایش شد و حافظه نهان (cache) کانفیگ پاک شد.', 'success')
        return redirect(url_for('main.admin_settings'))
    return render_template('admin_form.html', form=form, title=f'ویرایش تنظیم: {setting.key}', description=setting.description)

@bp.route('/admin/users')
@admin_required
def manage_users():
    """Lists all users for the admin."""
    users = User.query.order_by(User.name).all()
    return render_template('admin_users.html', users=users)

@bp.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Handles adding a new user."""
    form = UserForm()
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data, name=form.name.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(f'کاربر "{user.username}" با موفقیت اضافه شد.', 'success')
            return redirect(url_for('main.manage_users'))
        except IntegrityError:
            db.session.rollback()
            flash('نام کاربری یا نام کامل از قبل وجود دارد. لطفاً مقدار دیگری را انتخاب کنید.', 'danger')
    return render_template('admin_user_form.html', form=form, title='افزودن کاربر جدید')

@bp.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Handles editing an existing user."""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        try:
            user.username = form.username.data
            user.name = form.name.data
            if form.password.data:
                user.set_password(form.password.data)
            db.session.commit()
            flash(f'اطلاعات کاربر "{user.username}" با موفقیت ویرایش شد.', 'success')
            return redirect(url_for('main.manage_users'))
        except IntegrityError:
            db.session.rollback()
            flash('نام کاربری یا نام کامل از قبل وجود دارد و متعلق به کاربر دیگری است.', 'danger')
    return render_template('admin_user_form.html', form=form, title=f'ویرایش کاربر: {user.username}')

@bp.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Handles deleting a user."""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'کاربر "{user.username}" حذف شد.', 'success')
    return redirect(url_for('main.manage_users'))