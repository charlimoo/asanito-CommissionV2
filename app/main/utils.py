# ==============================================================================
# app/main/utils.py
# (Updated with Aggregation Logic)
# ==============================================================================
import pandas as pd
from app.models import CommissionRuleSet

def get_bracket_range_string(bracket_base, commission_model):
    """Finds the human-readable string for a given sales bracket."""
    rules_from_db = CommissionRuleSet.query.filter_by(model_name=commission_model).all()
    for rule in rules_from_db:
        if rule.min_sales <= bracket_base < rule.max_sales:
            min_str = f"{rule.min_sales / 1_000_000:,.0f}"
            max_str = "∞" if rule.max_sales >= 999999999999 else f"{rule.max_sales / 1_000_000:,.0f}"
            return f"پله: {min_str} - {max_str} میلیون"
    return "پله: نامشخص"

def _perform_frontend_aggregation(results):
    """
    A reusable function that takes raw engine results and adds aggregated
    summary keys needed by the frontend templates (both web and PDF).
    This function modifies the 'results' dictionary in place.
    """
    for month_key, month_data in results.items():
        total_monthly_net = 0
        total_monthly_commission = 0

        for person_name, person_data in month_data.get('persons', {}).items():
            person_total_net = 0
            person_unpaid_commission = 0
            person_data['roles_summary'] = {}

            for txn in person_data.get('transactions', []):
                person_total_net += txn.get('net_value', 0)
                person_unpaid_commission += txn.get('commission_remaining', 0)
                
                role_summary = person_data['roles_summary'].setdefault(txn.get('role'), {
                    'total_sales': 0, 'total_commission': 0, 'transaction_count': 0
                })
                role_summary['total_sales'] += txn.get('commission_base', 0)
                role_summary['total_commission'] += txn.get('payable_commission', 0)
                role_summary['transaction_count'] += 1

            person_data['total_net_sales'] = person_total_net
            person_data['unpaid_commission'] = person_unpaid_commission
            person_data['bracket_range_str'] = get_bracket_range_string(person_data.get('bracket_base', 0), person_data.get('model', ''))

            total_monthly_net += person_total_net
            total_monthly_commission += person_data.get('total_commission', 0)
        
        month_data['total_net_sales'] = total_monthly_net
        month_data['total_commission'] = total_monthly_commission
    
    return results # Return the modified results dictionary

def prepare_frontend_data(results, summary_data, additional_commissions_df):
    """
    Transforms and AGGREGATES the raw engine output into a structured dictionary
    optimized for the frontend.
    """
    # --- AGGREGATION PASS ---
    results = _perform_frontend_aggregation(results)
    # This pass calculates all the SUMs and COUNTs needed by the UI.
    for month_key, month_data in results.items():
        total_monthly_net = 0
        total_monthly_commission = 0

        for person_name, person_data in month_data['persons'].items():
            person_total_net = 0
            person_unpaid_commission = 0
            
            person_data['roles_summary'] = {}

            for txn in person_data['transactions']:
                person_total_net += txn.get('net_value', 0) # Use .get() for safety
                
                # --- THIS IS THE FIX ---
                # Use .get() with a default value of 0.
                person_unpaid_commission += txn.get('commission_remaining', 0)
                # --- END OF FIX ---
                
                role_summary = person_data['roles_summary'].setdefault(txn['role'], {
                    'total_sales': 0, 'total_commission': 0, 'transaction_count': 0
                })
                role_summary['total_sales'] += txn.get('commission_base', 0)
                role_summary['total_commission'] += txn.get('payable_commission', 0)
                role_summary['transaction_count'] += 1

            person_data['total_net_sales'] = person_total_net
            person_data['unpaid_commission'] = person_unpaid_commission
            person_data['bracket_range_str'] = get_bracket_range_string(person_data.get('bracket_base', 0), person_data.get('model', ''))
            
            total_monthly_net += person_total_net
            # Use .get() here as well for total commission
            total_monthly_commission += person_data.get('total_commission', 0)
        
        month_data['total_net_sales'] = total_monthly_net
        month_data['total_commission'] = total_monthly_commission

    # --- The rest of the function remains mostly the same, but uses the new aggregated data ---
    
    person_list = sorted(list(summary_data.keys()))
    months = sorted(list(results.keys()))

    # Chart Data Preparation (no changes needed here)
    chart_data = {
        'labels': months, 'datasets': {'total_sales': [], 'targets': [], 'persons': {}}
    }
    # ... (rest of chart data preparation logic is the same)
    for person in person_list: chart_data['datasets']['persons'][person] = [0] * len(months)
    targets_lookup = additional_commissions_df.set_index(['سال', 'ماه']) if not additional_commissions_df.empty else None
    last_valid_target = 0
    for i, month in enumerate(months):
        monthly_total_sales = sum(results[month]['persons'].get(p, {}).get('bracket_base', 0) for p in person_list)
        chart_data['datasets']['total_sales'].append(monthly_total_sales)
        for person_name in person_list:
            chart_data['datasets']['persons'][person_name][i] = results[month]['persons'].get(person_name, {}).get('bracket_base', 0)
        
        target_value = last_valid_target
        if targets_lookup is not None:
            year, month_num = map(int, month.split('-'))
            if (year, month_num) in targets_lookup.index:
                target_data = targets_lookup.loc[(year, month_num)]
                if not pd.isna(target_data.get('تارگت جمعی')): target_value = target_data.get('تارگت جمعی')
        last_valid_target = target_value
        chart_data['datasets']['targets'].append(target_value * 0.1)

    # Person-Centric Monthly Report (now includes total_net_sales)
    person_monthly_report = {}
    for person in person_list:
        person_monthly_report[person] = {'months': {}, 'total_unpaid': summary_data.get(person, {}).get('remaining_balance', 0)}
    
    for month, month_data in results.items():
        for person_name, person_data in month_data['persons'].items():
            if person_name in person_monthly_report:
                original_commission = person_data['total_commission'] - person_data.get('additional_bonus', 0)
                person_monthly_report[person_name]['months'][month] = {
                    'bracket_base': person_data['bracket_base'],
                    'original_commission': original_commission,
                    'additional_bonus': person_data.get('additional_bonus', 0),
                    'total_commission': person_data['total_commission'],
                    'total_net_sales': person_data['total_net_sales'] # <-- ADDED
                }

    frontend_data = {
        'personList': person_list,
        'overallSummary': list(summary_data.values()),
        'detailedReport': results,
        'personMonthlyReport': person_monthly_report,
        'chartData': chart_data
    }
    return frontend_data