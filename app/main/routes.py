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
import pdfkit

from app import db
from app.main import bp
from app.models import CalculationRun, PersonResult, CommissionRuleSet, MonthlyTarget, AppSetting
from app.calculator.validator import validate_excel_file
from app.calculator.engine import calculate_commissions, summarize_results, CalculationConfig
from app.main.forms import AdminLoginForm, CommissionRuleForm, MonthlyTargetForm, AppSettingForm
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
                    targets_json=targets_json_str # <-- SAVE THE TARGETS
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
                        remaining_balance=data['remaining_balance'], calculation_run_id=new_run.id
                    )
                    db.session.add(person_result)
                
                db.session.commit()
                flash('محاسبات با موفقیت انجام و ذخیره شد.', 'success')
                return redirect(url_for('main.view_report', run_id=new_run.id))

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
def history():
    """Displays a list of all past calculation runs."""
    runs = CalculationRun.query.order_by(CalculationRun.upload_timestamp.desc()).all()
    return render_template('history.html', runs=runs)

@bp.route('/report/<int:run_id>')
def view_report(run_id):
    """Displays the full, interactive report for a specific calculation run."""
    run = CalculationRun.query.get_or_404(run_id)
    
    if run.detailed_results_json:
        results = json.loads(run.detailed_results_json)
        person_results_query = PersonResult.query.filter_by(calculation_run_id=run.id).all()
        summary_data = {}
        for res in person_results_query:
            summary_data[res.person_name] = {
                'person_name': res.person_name,
                'commission_model': res.commission_model,
                'total_original_commission': res.total_original_commission,
                'total_additional_bonus': res.total_additional_bonus,
                'total_payable_commission': res.total_payable_commission,
                'total_paid_commission': res.total_paid_commission,
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
            person_list=frontend_data['personList']
        )
    else:
        # Fallback to simple summary view
        person_results = PersonResult.query.filter_by(calculation_run_id=run.id).all()
        return render_template('summary_report.html', run=run, person_results=person_results)

# @bp.route('/report/<int:run_id>/export/pdf')
# def export_pdf(run_id):
#     """Generates and serves a PDF report for a given calculation run using pdfkit."""
#     run = CalculationRun.query.get_or_404(run_id)
#     if not run.detailed_results_json:
#         flash('اطلاعات دقیق برای ساخت PDF یافت نشد.', 'danger')
#         return redirect(url_for('main.view_report', run_id=run_id))
    
#     try:
#         results = json.loads(run.detailed_results_json)
#         aggregated_results = _perform_frontend_aggregation(results)
#         # --- THIS IS THE NEW FILTERING LOGIC ---
#         filtered_people_str = request.args.get('filter')
#         if filtered_people_str:
#             filtered_people = filtered_people_str.split(',')
#             filtered_results = {}
#             for month_key, month_data in aggregated_results.items():
#                 # Copy top-level month data
#                 filtered_month = month_data.copy()
#                 filtered_month['persons'] = {}
                
#                 # Only include people who are in the filter list
#                 for person_name, person_data in month_data.get('persons', {}).items():
#                     if person_name in filtered_people:
#                         filtered_month['persons'][person_name] = person_data
                
#                 # Only add the month to the final results if it contains filtered people
#                 if filtered_month['persons']:
#                     filtered_results[month_key] = filtered_month
#             results_to_render = filtered_results
            
#             # Use the filtered results for rendering
#             results_to_render = filtered_results
#         else:
#             # If no filter is provided, use the original full results
#             results_to_render = aggregated_results
#         # --- END OF FILTERING LOGIC ---

#         html_string = render_template(
#             'report_pdf.html', 
#             detailed_report=results_to_render, 
#             filename=run.filename
#         )
        
#         path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
#         config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
#         options = {'page-size': 'A4', 'margin-top': '0.75in', 'margin-right': '0.75in', 'margin-bottom': '0.75in', 'margin-left': '0.75in', 'encoding': "UTF-8", 'no-outline': None}

#         pdf = pdfkit.from_string(html_string, False, configuration=config, options=options)
#         pdf_filename = f"commission_report_{run.id}_{run.report_period.replace(' ', '')}.pdf"

#         return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f"attachment;filename={pdf_filename}"})

#     except FileNotFoundError:
#         current_app.logger.error(f"wkhtmltopdf not found at path: {current_app.config.get('WKHTMLTOPDF_PATH')}")
#         flash('خطا: فایل اجرایی ساخت PDF یافت نشد. لطفاً مسیر wkhtmltopdf را در کانفیگ بررسی کنید.', 'danger')
#         return redirect(url_for('main.view_report', run_id=run_id))
#     except Exception as e:
#         current_app.logger.error(f"PDF generation failed for run {run_id}: {e}", exc_info=True)
#         flash('خطایی در هنگام ساخت فایل PDF رخ داد.', 'danger')
#         return redirect(url_for('main.view_report', run_id=run_id))

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
    flash('شما با موفقیت خارج شدید.', 'info')
    return redirect(url_for('main.index'))

@bp.route('/admin')
@admin_required
def admin_dashboard():
    """Main admin dashboard showing rules and targets."""
    rules = CommissionRuleSet.query.order_by(CommissionRuleSet.model_name, CommissionRuleSet.min_sales).all()
    targets = MonthlyTarget.query.order_by(MonthlyTarget.year.desc(), MonthlyTarget.month.desc()).all()
    return render_template('admin.html', rules=rules, targets=targets)

# --- CRUD for Commission Rules ---
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

# --- CRUD for Monthly Targets ---
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

# --- CRUD for App Settings ---
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
                # First, validate that the input is valid JSON
                parsed_json = json.loads(new_value)
                # Then, re-serialize it with ensure_ascii=False to store it correctly
                new_value = json.dumps(parsed_json, ensure_ascii=False)
            except json.JSONDecodeError:
                flash('مقدار وارد شده برای این تنظیم یک JSON معتبر نیست.', 'danger')
                return render_template('admin_form.html', form=form, title=f'ویرایش تنظیم: {setting.key}', description=setting.description)
        
        setting.value = new_value
        db.session.commit()
        
        # Invalidate the cached config so it reloads on next request
        from app.calculator.engine import CalculationConfig
        CalculationConfig._instance = None
        
        flash(f'تنظیم "{setting.key}" با موفقیت ویرایش شد و حافظه نهان (cache) کانفیگ پاک شد.', 'success')
        return redirect(url_for('main.admin_settings'))
        
    return render_template('admin_form.html', form=form, title=f'ویرایش تنظیم: {setting.key}', description=setting.description)