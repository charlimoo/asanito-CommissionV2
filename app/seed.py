import json
from app import db
from app.models import AppSetting, CommissionRuleSet

DEFAULT_SETTINGS = {
    # key: [value, description, value_type]
    'CURRENCY_CONVERSION_FACTOR': ['0.1', 'ضریب تبدیل ریال به تومان', 'float'],
    'RENEWAL_COMMISSION_RATE': ['0.05', 'نرخ ثابت پورسانت برای تمدیدها (مثال: 0.05 برای 5%)', 'float'],
    'BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT': ['0.30', 'حداقل درصد وصولی برای محاسبه در پله (مثال: 0.30 برای 30%)', 'float'],
    'AGENT_SALE_MULTIPLIER': ['0.5', 'ضریب کاهش پورسانت برای فروش با نماینده (مثال: 0.5 برای 50%)', 'float'],
    'DEFAULT_COMMISSION_MODEL': ['پورسانت خالص', 'مدل پورسانت پیش‌فرض برای کارمندان تعریف نشده', 'string'],
    
    # --- FIX IS HERE ---
    'AGENT_KEYWORDS': [json.dumps(['نمایندگان', 'نماینده'], ensure_ascii=False), 'کلمات کلیدی برای شناسایی فروش با نماینده در ستون بازاریاب (فرمت JSON)', 'json'],
    'BONUS_PERCENTAGES': [json.dumps({'collective': 0.05, 'individual': 0.03, 'top_seller': 0.02}, ensure_ascii=False), 'درصدهای پاداش (جمعی، فردی، تاپ سلر) (فرمت JSON)', 'json'],
    'BRACKET_QUALIFICATION_MIN_VALUES': [json.dumps({
        'استاندارد': 12000000, 
        'حرفه‌ای': 40000000, 
        'VIP': 60000000, 
        'default': 12000000
    }, ensure_ascii=False), 'حداقل مبلغ وصولی برای محاسبه در پله (تومان) (فرمت JSON)', 'json']
    # --- END OF FIX ---
}

DEFAULT_COMMISSION_BRACKETS = [
    # (model_name, min, max, marketer, negotiator, coordinator)
    ('پورسانت خالص', 0, 250000000, 0.05, 0.10, 0.02),
    ('پورسانت خالص', 250000000, 500000000, 0.06, 0.12, 0.04),
    ('پورسانت خالص', 500000000, 750000000, 0.07, 0.14, 0.06),
    ('پورسانت خالص', 750000000, 1000000000, 0.08, 0.16, 0.08),
    ('پورسانت خالص', 1000000000, 1250000000, 0.09, 0.18, 0.09),
    ('پورسانت خالص', 1250000000, 999999999999, 0.10, 0.20, 0.10),
    ('حقوق ثابت + پورسانت', 0, 150000000, 0.00, 0.00, 0.00),
    ('حقوق ثابت + پورسانت', 150000000, 250000000, 0.05, 0.05, 0.01),
    ('حقوق ثابت + پورسانت', 250000000, 500000000, 0.06, 0.06, 0.02),
    ('حقوق ثابت + پورسانت', 500000000, 750000000, 0.07, 0.07, 0.03),
    ('حقوق ثابت + پورسانت', 750000000, 1000000000, 0.08, 0.08, 0.04),
    ('حقوق ثابت + پورسانت', 1000000000, 1250000000, 0.09, 0.09, 0.045),
    ('حقوق ثابت + پورسانت', 1250000000, 999999999999, 0.10, 0.10, 0.05),
]

def seed_data():
    """Populates the database with default settings and rules."""
    # Seed App Settings
    for key, data in DEFAULT_SETTINGS.items():
        setting = AppSetting.query.filter_by(key=key).first()
        if not setting: # Only add if it doesn't exist
            setting = AppSetting(key=key, value=data[0], description=data[1], value_type=data[2])
            db.session.add(setting)
            print(f'Seeding setting: {key}')

    # Seed Commission Brackets
    if CommissionRuleSet.query.count() == 0:
        print('Seeding default commission brackets...')
        for model, min_s, max_s, mark, neg, coord in DEFAULT_COMMISSION_BRACKETS:
            rule = CommissionRuleSet(
                model_name=model, min_sales=min_s, max_sales=max_s,
                marketer_rate=mark, negotiator_rate=neg, coordinator_rate=coord
            )
            db.session.add(rule)

    db.session.commit()
    print('Seeding complete.')