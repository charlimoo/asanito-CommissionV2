# ==============================================================================
# app/calculator/engine.py (Final, Complete, and Corrected)
# ==============================================================================

import pandas as pd
import json
import logging
from app.models import CommissionRuleSet, AppSetting

# --- Configuration Loader Class ---

class CalculationConfig:
    """
    A singleton class to load and hold all business rules from the database.
    This ensures the database is queried only once per application lifecycle.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logging.info("Creating and loading CalculationConfig instance...")
            cls._instance = super(CalculationConfig, cls).__new__(cls)
            try:
                cls._instance.load_settings()
                logging.info("CalculationConfig loaded successfully.")
            except Exception as e:
                logging.error(f"FATAL: Could not load settings from database. Engine cannot run. Error: {e}", exc_info=True)
                raise
        return cls._instance

    def load_settings(self):
        """Loads all settings from the AppSetting table into attributes."""
        settings = AppSetting.query.all()
        settings_dict = {s.key: s.get_value() for s in settings}
        
        self.CURRENCY_CONVERSION_FACTOR = settings_dict.get('CURRENCY_CONVERSION_FACTOR', 0.1)
        self.RENEWAL_COMMISSION_RATE = settings_dict.get('RENEWAL_COMMISSION_RATE', 0.05)
        self.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT = settings_dict.get('BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT', 0.3)
        self.AGENT_SALE_MULTIPLIER = settings_dict.get('AGENT_SALE_MULTIPLIER', 0.5)
        self.DEFAULT_COMMISSION_MODEL = settings_dict.get('DEFAULT_COMMISSION_MODEL', 'پورسانت خالص')
        self.AGENT_KEYWORDS = settings_dict.get('AGENT_KEYWORDS', ['نمایندگان', 'نماینده'])
        self.BONUS_PERCENTAGES = settings_dict.get('BONUS_PERCENTAGES', {'collective': 0.05, 'individual': 0.03, 'top_seller': 0.02})
        self.BRACKET_QUALIFICATION_MIN_VALUES = settings_dict.get('BRACKET_QUALIFICATION_MIN_VALUES', {'استاندارد': 12000000, 'حرفه‌ای': 40000000, 'VIP': 60000000, 'default': 12000000})

# --- Helper Functions ---

def _parse_monetary(value, config):
    if pd.isna(value): return 0.0
    return float(str(value).replace(',', '')) * config.CURRENCY_CONVERSION_FACTOR

def _get_commission_rates_for_bracket(bracket_base, commission_model, all_rules):
    brackets_to_use = all_rules.get(commission_model, [])
    for rule in brackets_to_use:
        if rule.min_sales <= bracket_base < rule.max_sales:
            return {'بازاریاب': rule.marketer_rate, 'مذاکره کننده ارشد': rule.negotiator_rate, 'هماهنگ کننده فروش': rule.coordinator_rate}
    logging.warning(f"No matching commission bracket found for model '{commission_model}' with base {bracket_base:,.0f}.")
    return {'بازاریاب': 0, 'مذاکره کننده ارشد': 0, 'هماهنگ کننده فروش': 0}


# --- Main Calculation Orchestrator ---

def calculate_commissions(dataframes):
    logging.info("="*80)
    logging.info("STARTING COMMISSION CALCULATION PROCESS (FORENSIC MODE)")
    logging.info("="*80)
    
    config = CalculationConfig()

    logging.info("\n" + "="*30 + " CURRENT CONFIGURATION STATE " + "="*30)
    all_settings = AppSetting.query.all()
    logging.info("--- App Settings from DB ---")
    for s in all_settings: logging.info(f"  - {s.key}: {s.value} (Type: {s.value_type})")

    all_rules = CommissionRuleSet.query.all()
    logging.info("\n--- Commission Rules from DB ---")
    for r in all_rules: logging.info(f"  - Model: {r.model_name}, Range: {r.min_sales:,.0f}-{r.max_sales:,.0f}, Rates: M={r.marketer_rate:.2%}, N={r.negotiator_rate:.2%}, C={r.coordinator_rate:.2%}")

    additional_comm_df = dataframes.get('Additional commissions')
    logging.info("\n--- Additional Commissions Sheet Content ---")
    logging.info("\n" + additional_comm_df.to_string())
    
    employee_models_df = dataframes['Employee Models']
    logging.info("\n--- Employee Models Sheet Content ---")
    logging.info("\n" + employee_models_df.to_string())
    logging.info("="*80 + "\n")
    
    sales_df = dataframes['Sales data']
    employee_models = dict(zip(employee_models_df['نام'], employee_models_df['مدل همکاری']))
    results = {}

    all_rules_dict = {}
    for rule in all_rules:
        all_rules_dict.setdefault(rule.model_name, []).append(rule)
    
    logging.info("--- Starting Pass 1: Processing transactions and calculating bracket bases. ---")
    for index, row in sales_df.iterrows():
        excel_row_num = index + 2
        
        row_summary = (
            f"Processing Excel Row: {excel_row_num} | "
            f"Company: '{row.get('شرکت خریدار', 'N/A')}' | "
            f"Net Value: {row.get('مبلغ کل خالص فاکتور', 0)} | "
            f"Paid: {row.get('وصول شده', 0)} | "
            f"SN: '{row.get('مذاکره کننده ارشد', 'N/A')}' | "
            f"Plan: '{row.get('نسخه پلن', 'N/A')}'"
        )
        logging.debug(f"\n{row_summary}")
        
        if 'مذاکره کننده ارشد' not in row.index:
            logging.error(f"FATAL FLAW in Excel file: Column 'مذاکره کننده ارشد' not found! All bracket calculations will be 0.")
            logging.error(f"Available columns are: {list(row.index)}")

        try:
            month = str(int(row.get('ماه'))).strip()
            year = str(int(row.get('سال'))).strip()
        except (ValueError, TypeError):
            logging.warning(f"SKIPPING Row {excel_row_num}: Invalid or missing 'ماه'/'سال'.")
            continue
        
        month_key = f"{year}-{month}"

        net_value = _parse_monetary(row.get('مبلغ کل خالص فاکتور', 0), config)
        commission_base = _parse_monetary(row.get('کل مبلغ مبنای پورسانت', 0), config)
        paid_amount = _parse_monetary(row.get('وصول شده', 0), config)
        is_renewal = str(row.get('تمدید اشتراک', 'خیر')).strip() == 'بله'
        
        if 'نسخه پلن' in row and not pd.isna(row.get('نسخه پلن')):
            plan_version = str(row['نسخه پلن']).strip()
        else:
            plan_version = 'default'
        
        marketer_name = str(row.get('بازاریاب', '')).strip()
        asanito_plan_percent = row.get('درصد پلن های آسانیتویی', 100)
        is_agent_sale = any(keyword in marketer_name for keyword in config.AGENT_KEYWORDS) or (asanito_plan_percent == 50)

        min_collection_value = config.BRACKET_QUALIFICATION_MIN_VALUES.get(plan_version, config.BRACKET_QUALIFICATION_MIN_VALUES.get('default', 0))
        collection_ratio = (paid_amount / net_value) if net_value > 0 else 0
        
        is_renewal_check = not is_renewal
        collection_ratio_check = collection_ratio >= config.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT
        min_value_check = paid_amount >= min_collection_value
        qualifies_for_bracket = is_renewal_check and collection_ratio_check and min_value_check
        
        log_story = [
            f"\n--- Audit Log for Row {excel_row_num} ({row.get('شرکت خریدار', 'N/A')}) ---",
            f"  - Net Value  : {net_value:,.0f} Toman",
            f"  - Paid Amount: {paid_amount:,.0f} Toman",
            f"  - Is Renewal : {is_renewal}",
            f"  - Plan Version: '{plan_version}'",
            "  --- Qualification Checks ---",
            f"  1. Is NOT Renewal? ({not is_renewal}) -> {'PASS' if is_renewal_check else 'FAIL'}",
            f"  2. Collection Ratio Check: {collection_ratio:.2%} >= {config.BRACKET_QUALIFICATION_MIN_COLLECTION_PERCENT:.2%} -> {'PASS' if collection_ratio_check else 'FAIL'}",
            f"  3. Min Value Check: {paid_amount:,.0f} >= {min_collection_value:,.0f} (for plan '{plan_version}') -> {'PASS' if min_value_check else 'FAIL'}",
            f"  => FINAL QUALIFICATION: {'QUALIFIES' if qualifies_for_bracket else 'DOES NOT QUALIFY'}",
            "  ------------------------------------"
        ]
        logging.debug("\n".join(log_story))
        
        person_assigned_in_row = False
        for role in ['بازاریاب', 'مذاکره کننده ارشد', 'هماهنگ کننده فروش']:
            person_name = str(row.get(role, '')).strip()
            
            if not person_name or person_name.lower() == 'nan':
                continue
            
            person_assigned_in_row = True
            results.setdefault(month_key, {'persons': {}})
            person_data = results[month_key]['persons'].setdefault(person_name, {
                'model': employee_models.get(person_name, config.DEFAULT_COMMISSION_MODEL),
                'bracket_base': 0, 'transactions': []
            })
            
            if role == 'مذاکره کننده ارشد' and qualifies_for_bracket:
                bracket_value = commission_base * (config.AGENT_SALE_MULTIPLIER if is_agent_sale else 1.0)
                person_data['bracket_base'] += bracket_value
                logging.debug(f"  > QUALIFIED: Adding {bracket_value:,.0f} to bracket_base for {person_name}. New base: {person_data['bracket_base']:,.0f}")

            person_data['transactions'].append({
                'role': role, 'net_value': net_value, 'commission_base': commission_base, 
                'paid_amount': paid_amount, 'is_renewal': is_renewal, 'is_agent_sale': is_agent_sale, 
                'company': str(row.get('شرکت خریدار', '')).strip(), 
                'invoice_link': str(row.get('لینک فاکتور', '')).strip()
            })

        if not person_assigned_in_row:
            logging.warning(f"WARNING: No person was assigned any role in Excel Row {excel_row_num}.")

    logging.info(f"--- Pass 1 Finished. ---")
    
    logging.info("--- Starting Pass 2: Calculating base commissions... ---")
    for month_key, month_data in results.items():
        for person_name, person_data in month_data['persons'].items():
            rates = _get_commission_rates_for_bracket(person_data['bracket_base'], person_data['model'], all_rules_dict)
            person_data['total_commission'] = 0
            for txn in person_data['transactions']:
                original_rate = config.RENEWAL_COMMISSION_RATE if txn['is_renewal'] else rates.get(txn['role'], 0)
                current_rate = original_rate
                if txn['is_agent_sale']:
                    current_rate *= config.AGENT_SALE_MULTIPLIER
                
                collection_ratio = (txn['paid_amount'] / txn['net_value']) if txn['net_value'] > 0 else 1.0
                full_commission = txn['commission_base'] * current_rate
                payable_commission = full_commission * collection_ratio
                commission_remaining = full_commission - payable_commission
                
                txn['rate_used'] = current_rate
                txn['payable_commission'] = payable_commission
                txn['full_commission'] = full_commission
                txn['commission_remaining'] = commission_remaining
                person_data['total_commission'] += payable_commission

                details = [
                    f"مبلغ مبنای پورسانت: {txn['commission_base']:,.0f} تومان",
                    f"نرخ پایه پورسانت (نقش {txn['role']}): {original_rate:.2%}",
                ]
                if txn['is_agent_sale']:
                    details.append(f"اعمال ضریب نماینده ({config.AGENT_SALE_MULTIPLIER:.0%}): {original_rate:.2%} * {config.AGENT_SALE_MULTIPLIER:.0%} = {current_rate:.2%}")
                details.append(f"محاسبه پورسانت کامل: {txn['commission_base']:,.0f} * {current_rate:.2%} = {full_commission:,.0f} تومان")
                details.append("-" * 20)
                details.append(f"نسبت وصول: {collection_ratio:.2%} ({txn['paid_amount']:,.0f} / {txn['net_value']:,.0f})")
                details.append(f"پورسانت قابل پرداخت: {full_commission:,.0f} * {collection_ratio:.2%} = {payable_commission:,.0f} تومان")
                details.append(f"پورسانت باقی مانده: {full_commission:,.0f} - {payable_commission:,.0f} = {commission_remaining:,.0f} تومان")
                txn['calculation_details'] = "\n".join(details)
    logging.info("--- Pass 2 Finished. ---")

    logging.info("--- Starting Pass 3: Calculating additional bonuses... ---")
    targets_lookup = additional_comm_df.set_index(['سال', 'ماه'])
    
    last_valid_targets = {'collective': 0, 'individual': 0}
    for month_key in sorted(results.keys()):
        month_data = results[month_key]
        year, month = map(int, month_key.split('-'))
        
        logging.info(f"\n----- BONUS CALC FOR MONTH: {month_key} -----")
        
        # This is a snapshot of the memory from the PREVIOUS month's loop
        logging.info(f"  [START] Initial raw targets (from prev month): C={last_valid_targets['collective']:,.0f}, I={last_valid_targets['individual']:,.0f}")

        if (year, month) in targets_lookup.index:
            target_data = targets_lookup.loc[(year, month)]
            logging.info(f"  Found targets in Excel for {month_key}: C_raw={target_data.get('تارگت جمعی')}, I_raw={target_data.get('تارگت فرعی')}")
            
            # ** THE FIX IS HERE **
            # Only update the 'last_valid_targets' dictionary with new, valid numbers.
            current_collective = target_data.get('تارگت جمعی')
            if not pd.isna(current_collective):
                last_valid_targets['collective'] = current_collective
            
            current_individual = target_data.get('تارگت فرعی')
            if not pd.isna(current_individual):
                last_valid_targets['individual'] = current_individual
        else:
            logging.info(f"  No targets found in Excel for {month_key}. Using carried-over values.")
        
        collective_target_toman = last_valid_targets['collective'] * config.CURRENCY_CONVERSION_FACTOR
        individual_target_toman = last_valid_targets['individual'] * config.CURRENCY_CONVERSION_FACTOR
        logging.info(f"  [FINAL] Using Toman targets for {month_key}: Collective={collective_target_toman:,.0f}, Individual={individual_target_toman:,.0f}")

        if collective_target_toman == 0 and individual_target_toman == 0:
            logging.warning(f"Skipping bonus calculation for {month_key} due to zero targets.")
            for p_data in month_data.get('persons', {}).values(): p_data['additional_bonus'] = 0
            continue

        total_monthly_bracket_base = sum(p.get('bracket_base', 0) for p in month_data.get('persons', {}).values())
        top_seller_name, top_seller_sales = None, 0
        for name, p_data in month_data.get('persons', {}).items():
            if p_data.get('bracket_base', 0) > top_seller_sales:
                top_seller_sales = p_data['bracket_base']; top_seller_name = name
        logging.info(f"  Monthly Bracket Base Total: {total_monthly_bracket_base:,.0f}. Top Seller: {top_seller_name}")

        month_data['bonus_summary'] = { # Storing for frontend
            'collective_target': collective_target_toman, 'individual_target': individual_target_toman,
            'collective_amount': 0, 'individual_amount': 0, 'top_seller_amount': 0,
            'top_seller_name': top_seller_name, 'top_seller_sales': top_seller_sales,
            'bonus_percentages': config.BONUS_PERCENTAGES
        }
        
        for name, p_data in month_data.get('persons', {}).items():
            bonus_amount, bracket_base = 0, p_data.get('bracket_base', 0)
            bonus_details_list = []
            
            coll_check = total_monthly_bracket_base >= collective_target_toman and collective_target_toman > 0
            ind_check = bracket_base >= individual_target_toman and individual_target_toman > 0
            top_check = name == top_seller_name and bracket_base > 0
            logging.info(f"    Checking bonuses for {name} (base={bracket_base:,.0f}):")
            logging.info(f"      Collective Check: {total_monthly_bracket_base:,.0f} >= {collective_target_toman:,.0f} -> {coll_check}")
            logging.info(f"      Individual Check: {bracket_base:,.0f} >= {individual_target_toman:,.0f} -> {ind_check}")
            logging.info(f"      Top Seller Check: {name} == {top_seller_name} -> {top_check}")
            
            if coll_check: 
                coll_bonus = bracket_base * config.BONUS_PERCENTAGES['collective']
                bonus_details_list.append(f"پاداش جمعی: ... = {coll_bonus:,.0f} تومان")
                bonus_amount += coll_bonus
            if ind_check: 
                ind_bonus = bracket_base * config.BONUS_PERCENTAGES['individual']
                bonus_details_list.append(f"پاداش فردی: ... = {ind_bonus:,.0f} تومان")
                bonus_amount += ind_bonus
            if top_check: 
                top_bonus = bracket_base * config.BONUS_PERCENTAGES['top_seller']
                bonus_details_list.append(f"پاداش تاپ سلر: ... = {top_bonus:,.0f} تومان")
                bonus_amount += top_bonus
                
            p_data['additional_bonus'] = bonus_amount
            p_data['total_commission'] += bonus_amount
            logging.info(f"    => Total Bonus for {name}: {bonus_amount:,.0f}. New Total Commission: {p_data['total_commission']:,.0f}")
            
            if bonus_amount > 0:
                bonus_details_header = "\n" + ("-"*10) + " جزئیات پاداش " + ("-"*10)
                bonus_details_list.insert(0, bonus_details_header)
                bonus_details_list.append(f"مجموع پاداش: {bonus_amount:,.0f} تومان")
                bonus_details_str = "\n".join(bonus_details_list)
                for txn in p_data['transactions']:
                    txn['calculation_details'] += bonus_details_str
                    
    logging.info("--- Pass 3 Finished. ---")
    return results, config

def summarize_results(results, commissions_paid_df, config):
    summary = {}
    paid_summary = {}
    if commissions_paid_df is not None and not commissions_paid_df.empty:
        paid_summary = (pd.to_numeric(commissions_paid_df['مبلغ پرداخت شده'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).groupby(commissions_paid_df['نام']).sum() * config.CURRENCY_CONVERSION_FACTOR).to_dict()
    
    for month_data in results.values():
        for person_name, person_data in month_data.get('persons', {}).items():
            person_summary = summary.setdefault(person_name, {'person_name': person_name, 'commission_model': person_data.get('model'), 'total_original_commission': 0, 'total_additional_bonus': 0})
            original_commission = person_data['total_commission'] - person_data.get('additional_bonus', 0)
            person_summary['total_original_commission'] += original_commission
            person_summary['total_additional_bonus'] += person_data.get('additional_bonus', 0)

    for person_name, data in summary.items():
        data['total_payable_commission'] = data['total_original_commission'] + data['total_additional_bonus']
        data['total_paid_commission'] = paid_summary.get(person_name, 0)
        data['remaining_balance'] = data['total_payable_commission'] - data['total_paid_commission']
        
    logging.info(f"--- Summarization complete. Generated summary for {len(summary)} people. ---")
    return summary