# start of app/calculator/engine.py
# ==============================================================================
# app/calculator/engine.py (REVERTED LOGIC VERSION)
# ------------------------------------------------------------------------------
# Core calculation engine for the Asanito Commission System.
# This version reverts the core calculation logic to the "Old Version" where:
#   1. Bracket/Tier is determined by SN-Only sales.
#   2. Bonuses are calculated on the SN-Only base.
#   3. Bonus collection uses a simple monthly average ratio.
# It RETAINS the new, detailed logging for auditability.
# ==============================================================================

import pandas as pd
import json
import logging
from app.models import CommissionRuleSet, AppSetting

# ==============================================================================
# HELPER FUNCTIONS (No changes needed here)
# ==============================================================================

def _normalize_text(text):
    if pd.isna(text) or text is None:
        return ""
    return str(text).replace('ي', 'ی').replace('ك', 'ک').strip()

def _parse_monetary(value, conversion_factor):
    if pd.isna(value): return 0.0
    try:
        clean_val = float(str(value).replace(',', ''))
        return clean_val * conversion_factor
    except (ValueError, TypeError):
        return 0.0

def _get_commission_rates(bracket_base, commission_model, all_rules_dict):
    brackets = all_rules_dict.get(commission_model, [])
    brackets.sort(key=lambda x: x.min_sales)
    for rule in brackets:
        if rule.min_sales <= bracket_base < rule.max_sales:
            return {
                'بازاریاب': rule.marketer_rate, 
                'مذاکره کننده ارشد': rule.negotiator_rate, 
                'هماهنگ کننده فروش': rule.coordinator_rate
            }, f"[{rule.min_sales:,.0f} - {rule.max_sales:,.0f}]"
    return {'بازاریاب': 0, 'مذاکره کننده ارشد': 0, 'هماهنگ کننده فروش': 0}, "OUT OF RANGE"

# ==============================================================================
# CONFIGURATION CLASS (No changes needed here)
# ==============================================================================

class CalculationConfig:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CalculationConfig, cls).__new__(cls)
            cls._instance.load_settings()
        return cls._instance

    def load_settings(self):
        settings = AppSetting.query.all()
        settings_dict = {s.key: s.get_value() for s in settings}
        self.CURRENCY_CONVERSION_FACTOR = settings_dict.get('CURRENCY_CONVERSION_FACTOR', 0.1)
        self.RENEWAL_COMMISSION_RATE = settings_dict.get('RENEWAL_COMMISSION_RATE', 0.05)
        self.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT = settings_dict.get('BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT', 0.3)
        self.DEFAULT_COMMISSION_MODEL = settings_dict.get('DEFAULT_COMMISSION_MODEL', 'پورسانت خالص')
        self.BONUS_PERCENTAGES = settings_dict.get('BONUS_PERCENTAGES', {'collective': 0.05, 'individual': 0.03, 'top_seller': 0.02})
        self.BRACKET_QUALIFICATION_MIN_VALUES = settings_dict.get('BRACKET_QUALIFICATION_MIN_VALUES', {'استاندارد': 12000000, 'حرفه‌ای': 40000000, 'VIP': 60000000, 'default': 12000000})

# ==============================================================================
# MAIN ENGINE LOGIC (REVERTED)
# ==============================================================================

def calculate_commissions(dataframes):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    logger.info("\n" + "#"*80)
    logger.info("### STARTING CALCULATION ENGINE (REVERTED LOGIC - AUDIT MODE) ###")
    logger.info("#"*80)
    
    config = CalculationConfig()
    
    all_rules = CommissionRuleSet.query.all()
    all_rules_dict = {m: [] for m in set(r.model_name for r in all_rules)}
    for rule in all_rules: all_rules_dict[rule.model_name].append(rule)
    
    employee_models_df = dataframes['Employee Models']
    employee_models = {_normalize_text(row['نام']): row['مدل همکاری'] for _, row in employee_models_df.iterrows()}
    
    additional_comm_df = dataframes.get('Additional commissions')
    sales_df = dataframes['Sales data']
    results = {}

    # --------------------------------------------------------------------------
    # PASS 1: ROW PROCESSING (Qualification & SN-Only Aggregation)
    # --------------------------------------------------------------------------
    logger.info("\n>>> PASS 1: PROCESSING ROWS (Qualification Check)")
    
    for index, row in sales_df.iterrows():
        excel_row_num = index + 2
        if 'مذاکره کننده ارشد' not in row.index: continue
        try:
            month_key = f"{int(row.get('سال'))}-{int(row.get('ماه'))}"
        except: continue

        company = str(row.get('شرکت خریدار', 'Unknown')).strip()
        net_invoice = _parse_monetary(row.get('مبلغ کل خالص فاکتور', 0), config.CURRENCY_CONVERSION_FACTOR)
        commission_base = _parse_monetary(row.get('کل مبلغ مبنای پورسانت', 0), config.CURRENCY_CONVERSION_FACTOR)
        paid_amount = _parse_monetary(row.get('وصول شده', 0), config.CURRENCY_CONVERSION_FACTOR)
        is_renewal = str(row.get('تمدید اشتراک', 'خیر')).strip() == 'بله'
        plan_version = str(row.get('نسخه پلن', 'default')).strip()
        
        ratio = (paid_amount / net_invoice) if net_invoice > 0 else 0.0
        min_threshold = config.BRACKET_QUALIFICATION_MIN_VALUES.get(plan_version, config.BRACKET_QUALIFICATION_MIN_VALUES.get('default', 0))
        
        is_acceptable = (ratio >= config.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT) and (paid_amount >= min_threshold)

        log_status = "✅ ACCEPTABLE" if is_acceptable else "❌ REJECTED"
        reject_reason = []
        if not (ratio >= config.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT): reject_reason.append(f"Ratio {ratio:.1%} < {config.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT:.1%}")
        if not (paid_amount >= min_threshold): reject_reason.append(f"Paid {paid_amount:,.0f} < Threshold {min_threshold:,.0f}")
        reason_str = f"({', '.join(reject_reason)})" if reject_reason else ""
        
        logger.info(f"Row {excel_row_num:03d} | {company[:20]:<20} | {log_status} {reason_str}")

        roles = ['بازاریاب', 'مذاکره کننده ارشد', 'هماهنگ کننده فروش']
        for role in roles:
            raw_name = row.get(role)
            if pd.isna(raw_name) or str(raw_name).lower() == 'nan': continue
            
            person_name = _normalize_text(raw_name)
            if not person_name: continue

            results.setdefault(month_key, {'persons': {}})
            person_data = results[month_key]['persons'].setdefault(person_name, {
                'model': employee_models.get(person_name, config.DEFAULT_COMMISSION_MODEL),
                'bracket_base': 0, # REVERTED: This is the SN-Only ladder base
                'transactions': []
            })
            
            # --- REVERTED LOGIC ---
            # Only add to the bracket base if the role is Senior Negotiator and the deal is acceptable.
            # Renewals are included in the ladder base in this old logic.
            if role == 'مذاکره کننده ارشد' and is_acceptable:
                person_data['bracket_base'] += commission_base
            
            person_data['transactions'].append({
                'role': role, 'company': company, 'net_value': net_invoice,
                'commission_base': commission_base, 'paid_amount': paid_amount,
                'collection_ratio': ratio, 'is_renewal': is_renewal,
                'is_acceptable': is_acceptable, 'plan_version': plan_version,
                'invoice_link': str(row.get('لینک فاکتور', ''))
            })

    # --------------------------------------------------------------------------
    # PASS 2: COMMISSION CALCULATION
    # --------------------------------------------------------------------------
    logger.info("\n>>> PASS 2: CALCULATING COMMISSIONS (Per Person)")
    
    # 1. We need a history tracker to calculate averages across months
    # Structure: { 'Person Name': { 'total_bracket_base_so_far': [], 'months_seen': [] } }
    person_history = {}

    # 2. Sort months to ensure chronological processing (e.g. 1404-1, 1404-2...)
    sorted_months = sorted(results.keys())

    for month_key in sorted_months:
        month_data = results[month_key]
        logger.info(f"--- Month: {month_key} ---")
        
        for person_name, person_data in month_data['persons'].items():
            
            # --- HISTORY TRACKING FOR GRADING ---
            if person_name not in person_history:
                person_history[person_name] = []
            
            # Add current month's SN-Only Base to history
            current_bracket_base = person_data['bracket_base']
            person_history[person_name].append(current_bracket_base)
            
            # --- DETERMINE EFFECTIVE BASE FOR TIERING ---
            commission_model = person_data['model']
            effective_base_for_tier = current_bracket_base
            calculation_note = "Monthly Base"

            # [FIX] Apply 3-Month Rolling Average for "Fixed Salary" Model
            if commission_model == 'حقوق ثابت + پورسانت':
                # Get the last 3 months of sales (including current)
                last_3_months = person_history[person_name][-3:] 
                if last_3_months:
                    average_sales = sum(last_3_months) / len(last_3_months)
                    effective_base_for_tier = average_sales
                    calculation_note = f"3-Month Avg (Last 3: {[f'{x:,.0f}' for x in last_3_months]})"

            # --- GET RATES BASED ON EFFECTIVE BASE ---
            # We use effective_base_for_tier to find the % Rate, 
            # BUT we apply that % Rate to the actual current_bracket_base (and transactions)
            rates, bracket_str = _get_commission_rates(effective_base_for_tier, commission_model, all_rules_dict)
            
            logger.info(
                f"  > {person_name} ({commission_model}): "
                f"Actual Base: {current_bracket_base:,.0f} | "
                f"Tier Base: {effective_base_for_tier:,.0f} ({calculation_note}) -> Tier {bracket_str}"
            )

            # --- APPLY RATES TO TRANSACTIONS ---
            for txn in person_data['transactions']:
                if txn['is_renewal']:
                    rate = config.RENEWAL_COMMISSION_RATE
                else:
                    rate = rates.get(txn['role'], 0)
                
                # Standard calculation logic continues...
                comm_base = txn['commission_base'] * rate
                comm_acceptable = comm_base if txn['is_acceptable'] else 0.0
                effective_ratio = min(1.0, txn['collection_ratio'])
                comm_collected = comm_acceptable * effective_ratio
                
                txn['full_commission'] = comm_base
                txn['acceptable_commission'] = comm_acceptable
                txn['payable_commission'] = comm_collected
                txn['rate_used'] = rate
                txn['calculation_details'] = f"Base: {comm_base:,.0f}, Rate: {rate*100:.2f}% (Tier Base: {effective_base_for_tier:,.0f}), Collected: {comm_collected:,.0f}"

    # --------------------------------------------------------------------------
    # PASS 3: BONUS CALCULATION (REVERTED)
    # --------------------------------------------------------------------------
    logger.info("\n>>> PASS 3: CALCULATING BONUSES (Reverted Logic)")
    
    targets_lookup = additional_comm_df.set_index(['سال', 'ماه'])
    last_valid_targets = {'collective': 0, 'individual': 0}

    for month_key in sorted(results.keys()):
        month_data = results[month_key]
        year, month = map(int, month_key.split('-'))
        
        if (year, month) in targets_lookup.index:
            t_data = targets_lookup.loc[(year, month)]
            if not pd.isna(t_data.get('تارگت جمعی')): last_valid_targets['collective'] = t_data.get('تارگت جمعی')
            if not pd.isna(t_data.get('تارگت فرعی')): last_valid_targets['individual'] = t_data.get('تارگت فرعی')
            
        target_coll = last_valid_targets['collective'] * config.CURRENCY_CONVERSION_FACTOR
        target_ind = last_valid_targets['individual'] * config.CURRENCY_CONVERSION_FACTOR
        
        # --- REVERTED LOGIC ---
        # Top Seller is based on the SN-Only 'bracket_base'
        top_seller_name, top_seller_val = None, -1
        month_total_bracket_base = 0
        
        for name, p in month_data['persons'].items():
            month_total_bracket_base += p['bracket_base']
            if p['bracket_base'] > top_seller_val:
                top_seller_val, top_seller_name = p['bracket_base'], name

        logger.info(f"--- Month {month_key} Bonus Context (Reverted) ---")
        logger.info(f"  Team SN-Only Base: {month_total_bracket_base:,.0f} vs Target: {target_coll:,.0f}")
        logger.info(f"  Top Seller (SN-Only): {top_seller_name} ({top_seller_val:,.0f})")

        for name, p in month_data['persons'].items():
            # --- REVERTED LOGIC ---
            # Bonus is calculated on the SN-Only 'bracket_base'
            bracket_base = p['bracket_base']
            
            potential_bonus = 0
            reasons = []
            if target_coll > 0 and month_total_bracket_base >= target_coll:
                potential_bonus += bracket_base * config.BONUS_PERCENTAGES['collective']
                reasons.append("Coll")
            if target_ind > 0 and bracket_base >= target_ind:
                potential_bonus += bracket_base * config.BONUS_PERCENTAGES['individual']
                reasons.append("Ind")
            if top_seller_val > 0 and name == top_seller_name:
                potential_bonus += bracket_base * config.BONUS_PERCENTAGES['top_seller']
                reasons.append("Top")
            
            # --- REVERTED LOGIC ---
            # Use simple monthly collection ratio
            total_net = sum(txn['net_value'] for txn in p['transactions'])
            total_paid = sum(txn['paid_amount'] for txn in p['transactions'])
            person_ratio = (total_paid / total_net) if total_net > 0 else 0.0
            
            payable_bonus = potential_bonus * person_ratio
            
            p['bonus_base'] = potential_bonus # In old logic, base and acceptable are the same
            p['bonus_acceptable'] = potential_bonus
            p['bonus_collected'] = payable_bonus
            p['monthly_collection_ratio'] = person_ratio

            logger.info(f"  User {name}: Potential Bonus={potential_bonus:,.0f} {reasons} | Simple Ratio={person_ratio:.1%} | Payable Bonus={payable_bonus:,.0f}")

    return results, config

# ==============================================================================
# SUMMARIZATION (Adapted for Reverted Logic)
# ==============================================================================

def summarize_results(results, commissions_paid_df, config):
    logger = logging.getLogger(__name__)
    logger.info("\n>>> SUMMARIZATION (Reverted Logic): Preparing Database Records")
    
    summary = {}
    
    paid_summary = {}
    if commissions_paid_df is not None and not commissions_paid_df.empty:
        commissions_paid_df['normalized_name'] = commissions_paid_df['نام'].apply(_normalize_text)
        commissions_paid_df['clean_amount'] = pd.to_numeric(commissions_paid_df['مبلغ پرداخت شده'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) * config.CURRENCY_CONVERSION_FACTOR
        paid_summary = commissions_paid_df.groupby('normalized_name')['clean_amount'].sum().to_dict()

    for month_key, month_data in results.items():
        for person_name, person_data in month_data['persons'].items():
            
            if person_name not in summary:
                summary[person_name] = {
                    'person_name': person_name, 'commission_model': person_data.get('model'),
                    'total_declared': 0, 'total_base': 0, 'total_acceptable': 0,
                    'commission_base': 0, 'commission_acceptable': 0, 'commission_collected': 0,
                    'bonus_base': 0, 'bonus_acceptable': 0, 'bonus_collected': 0,
                }
            
            s = summary[person_name]
            
            for txn in person_data['transactions']:
                s['total_declared'] += txn['net_value']
                s['total_base'] += txn['commission_base']
                if txn['is_acceptable']:
                    s['total_acceptable'] += txn['commission_base']
                
                s['commission_base'] += txn['full_commission']
                s['commission_acceptable'] += txn['acceptable_commission']
                s['commission_collected'] += txn['payable_commission']
            
            s['bonus_base'] += person_data.get('bonus_base', 0)
            s['bonus_acceptable'] += person_data.get('bonus_acceptable', 0)
            s['bonus_collected'] += person_data.get('bonus_collected', 0)

    for name, data in summary.items():
        data['payable_amount'] = data['commission_collected'] + data['bonus_collected']
        data['total_paid_commission'] = paid_summary.get(name, 0)
        
        data['remaining_acceptable'] = (data['commission_acceptable'] + data['bonus_acceptable']) - data['payable_amount']
        data['remaining_base'] = (data['commission_base'] + data['bonus_base']) - data['payable_amount']
        
        data['remaining_balance'] = data['payable_amount'] - data['total_paid_commission']
        data['total_original_commission'] = data['commission_acceptable']
        data['total_additional_bonus'] = data['bonus_collected']
        data['total_payable_commission'] = data['payable_amount']
        
        logger.info(f"Summary for {name}: Payable={data['payable_amount']:,.0f}, Paid={data['total_paid_commission']:,.0f}, Balance={data['remaining_balance']:,.0f}")

    logger.info("### ENGINE FINISHED (REVERTED LOGIC) ###")
    return summary
# end of app/calculator/engine.py