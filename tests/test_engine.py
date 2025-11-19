# start of tests/test_engine.py
# tests/test_engine.py

import pytest
import pandas as pd
from io import StringIO
import json

# The app_with_db fixture is now automatically available from conftest.py

@pytest.fixture
def demo_dataframes():
    """Provides the test case data as a dictionary of pandas DataFrames."""
    # Note: 'درصد پلن های آسانیتویی' column is still here but should be ignored by engine
    sales_data_csv = """بازاریاب,مذاکره کننده ارشد,هماهنگ کننده فروش,شرکت خریدار,مبلغ کل خالص فاکتور,وصول شده,کل مبلغ مبنای پورسانت,ماه,سال,تمدید اشتراک,درصد پلن های آسانیتویی,نسخه پلن
,آمانج کردستانی,آمانج کردستانی,شرکت آلفا (فروش مستقیم),"300,000,000","300,000,000","300,000,000",1,1404,خیر,100,استاندارد
,آمانج کردستانی,آمانج کردستانی,شرکت بتا (فروش با نماینده),"200,000,000","200,000,000","200,000,000",1,1404,خیر,50,استاندارد
,پریناز لواسانی,پریناز لواسانی,شرکت گاما (تمدید),"50,000,000","50,000,000","50,000,000",1,1404,بله,100,حرفه‌ای
,پریناز لواسانی,پریناز لواسانی,شرکت دلتا (فاقد شرایط پله),"100,000,000","10,000,000","100,000,000",1,1404,خیر,100,استاندارد
,آمانج کردستانی,آمانج کردستانی,شرکت امگا (فروش ماه دوم),"800,000,000","800,000,000","800,000,000",2,1404,خیر,100,VIP
"""
    employee_models_csv = "نام,مدل همکاری\nآمانج کردستانی,پورسانت خالص\nپریناز لواسانی,حقوق ثابت + پورسانت"
    additional_commissions_csv = "سال,ماه,تارگت جمعی,درصد اضافه جمعی,تارگت فرعی,درصد اضافه فرعی,درصد تاپ سلر\n1404,1,45000000,5,35000000,3,2\n1404,2,,5,,3,2"
    commissions_paid_csv = "نام,مبلغ پرداخت شده\nآمانج کردستانی,10000000"
    
    return {
        'Sales data': pd.read_csv(StringIO(sales_data_csv)),
        'Employee Models': pd.read_csv(StringIO(employee_models_csv)),
        'Additional commissions': pd.read_csv(StringIO(additional_commissions_csv)),
        'Commissions paid': pd.read_csv(StringIO(commissions_paid_csv))
    }

# --- THE MAIN TEST FUNCTION (UPDATED) ---

def test_calculation_engine_with_demo_data(demo_dataframes, app_with_db):
    """
    This test runs the calculation engine against a temporary, seeded database
    to verify the correctness of the final numbers with controlled data.
    """
    from app import db
    from app.models import AppSetting, CommissionRuleSet
    from app.calculator.engine import CalculationConfig, calculate_commissions, summarize_results

    # --- 0. Clean existing data to prevent unique constraint errors ---
    # This ensures we start with a clean slate even if the fixture seeded the DB
    db.session.query(AppSetting).delete()
    db.session.query(CommissionRuleSet).delete()
    db.session.commit()

    # --- 1. Seed the temporary database with our specific test rules ---
    settings_data = {
        'CURRENCY_CONVERSION_FACTOR': ['0.1', 'float'], 'RENEWAL_COMMISSION_RATE': ['0.05', 'float'],
        'BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT': ['0.30', 'float'], 
        # REMOVED: AGENT_SALE_MULTIPLIER and AGENT_KEYWORDS
        'DEFAULT_COMMISSION_MODEL': ['پورسانت خالص', 'string'],
        'BONUS_PERCENTAGES': [json.dumps({'collective': 0.05, 'individual': 0.03, 'top_seller': 0.02}), 'json'],
        'BRACKET_QUALIFICATION_MIN_VALUES': [json.dumps({'استاندارد': 12000000, 'حرفه‌ای': 40000000, 'VIP': 60000000, 'default': 12000000}), 'json']
    }
    brackets_data = [
        ('پورسانت خالص', 0, 250000000, 0.05, 0.10, 0.02),
        ('پورسانت خالص', 250000000, 500000000, 0.06, 0.12, 0.04),
        ('حقوق ثابت + پورسانت', 0, 150000000, 0.00, 0.00, 0.00),
        ('حقوق ثابت + پورسانت', 150000000, 250000000, 0.05, 0.05, 0.01)
    ]
    
    for key, val in settings_data.items():
        db.session.add(AppSetting(key=key, value=val[0], value_type=val[1]))
    
    for data in brackets_data:
        db.session.add(CommissionRuleSet(model_name=data[0], min_sales=data[1], max_sales=data[2], marketer_rate=data[3], negotiator_rate=data[4], coordinator_rate=data[5]))
    
    db.session.commit()
    
    # Invalidate any cached config singleton before running
    CalculationConfig._instance = None
    
    # --- 2. Execute the Calculation Engine ---
    results, config = calculate_commissions(demo_dataframes)
    summary = summarize_results(results, demo_dataframes.get('Commissions paid'), config)

    # --- 3. Define Expected Values (UPDATED) ---
    TOLERANCE = 0.01
    
    # Amanj Calculations:
    # Amanj is BOTH 'Negotiator' (10%) AND 'Coordinator' (2%) in the CSV data.
    # Total Rate = 12%.
    # Month 1 Base: 50M. Comm: 50M * 12% = 6,000,000.
    # Month 2 Base: 80M. Comm: 80M * 12% = 9,600,000.
    # Total Original: 15,600,000.
    
    # Bonus (Calculated on Base of 50M and 80M):
    # M1: 50M * 10% = 5,000,000.
    # M2: 80M * 10% = 8,000,000.
    # Total Bonus: 13,000,000.
    
    amanj_expected = {
        'original_commission': 15_600_000, 
        'bonus': 13_000_000, 
        'total_payable': 28_600_000, 
        'paid': 1_000_000, 
        'remaining': 27_600_000
    }
    
    # Parinaz Calculations (Unchanged):
    # Renewal (5M * 5% * 2 roles) = 500,000.
    parinaz_expected = {
        'original_commission': 500_000, 
        'bonus': 0, 
        'total_payable': 500_000, 
        'paid': 0, 
        'remaining': 500_000
    }

    # --- 4. Perform Assertions ---
    assert 'آمانج کردستانی' in summary and 'پریناز لواسانی' in summary
    amanj_calculated = summary['آمانج کردستانی']
    parinaz_calculated = summary['پریناز لواسانی']
    
    assert abs(amanj_calculated['total_original_commission'] - amanj_expected['original_commission']) < TOLERANCE
    assert abs(amanj_calculated['total_additional_bonus'] - amanj_expected['bonus']) < TOLERANCE
    assert abs(amanj_calculated['total_payable_commission'] - amanj_expected['total_payable']) < TOLERANCE
    
    assert abs(parinaz_calculated['total_original_commission'] - parinaz_expected['original_commission']) < TOLERANCE
    assert abs(parinaz_calculated['total_additional_bonus'] - parinaz_expected['bonus']) < TOLERANCE
# end of tests/test_engine.py