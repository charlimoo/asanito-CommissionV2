# ==============================================================================
# app/calculator/schema.py
# ------------------------------------------------------------------------------
# Defines the expected structure of the uploaded Excel file.
# This schema is the single source of truth for the validator.
# ==============================================================================

EXPECTED_SHEETS = {
    'Sales data': {
        'required_columns': [
            'بازاریاب', 'مذاکره کننده ارشد', 'هماهنگ کننده فروش', 'شرکت خریدار',
            'مبلغ کل خالص فاکتور', 'وصول شده', 'کل مبلغ مبنای پورسانت',
            'ماه', 'سال', 'تمدید اشتراک', 'نسخه پلن'
        ],
        'numeric_columns': ['مبلغ کل خالص فاکتور', 'وصول شده', 'کل مبلغ مبنای پورسانت']
    },
    'Commissions paid': {
        'required_columns': ['نام', 'مبلغ پرداخت شده'],
        'numeric_columns': ['مبلغ پرداخت شده']
    },
    'Additional commissions': {
        'required_columns': [
            'سال', 'ماه', 'تارگت جمعی', 'درصد اضافه جمعی',
            'تارگت فرعی', 'درصد اضافه فرعی', 'درصد تاپ سلر'
        ],
        'numeric_columns': [
            'تارگت جمعی', 'درصد اضافه جمعی', 'تارگت فرعی',
            'درصد اضافه فرعی', 'درصد تاپ سلر'
        ]
    },
    'Renew': {
        'required_columns': ['سال', 'ماه', 'درصد تمدید'],
        'numeric_columns': ['درصد تمدید']
    },
    'Employee Models': {
        'required_columns': ['نام', 'مدل همکاری'],
        'numeric_columns': []
    }
}