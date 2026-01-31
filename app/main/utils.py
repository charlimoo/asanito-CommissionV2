# start of app/main/utils.py
# ==============================================================================
# app/main/utils.py
# ------------------------------------------------------------------------------
# Utilities for preparing data for the frontend reports.
# Updated to support Full Excel Flow columns (Potential vs Payable).
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
    summary keys needed by the frontend templates.
    """
    for month_key, month_data in results.items():
        total_monthly_net = 0
        total_monthly_commission = 0

        for person_name, person_data in month_data.get('persons', {}).items():
            person_total_net = 0
            person_unpaid_commission = 0
            person_potential_commission = 0 # NEW: For "Commission on Base"
            person_data['roles_summary'] = {}

            # Ensure keys exist
            if 'monthly_collection_ratio' not in person_data:
                person_data['monthly_collection_ratio'] = 0.0
            if 'potential_bonus' not in person_data:
                person_data['potential_bonus'] = 0.0
            if 'total_paid_amount' not in person_data:
                person_data['total_paid_amount'] = sum(t.get('paid_amount', 0) for t in person_data.get('transactions', []))

            for txn in person_data.get('transactions', []):
                person_total_net += txn.get('net_value', 0)
                person_unpaid_commission += txn.get('commission_remaining', 0)
                person_potential_commission += txn.get('full_commission', 0) # Summing the 100% commission
                
                role_summary = person_data['roles_summary'].setdefault(txn.get('role'), {
                    'total_sales': 0, 'total_commission': 0, 'transaction_count': 0
                })
                role_summary['total_sales'] += txn.get('commission_base', 0)
                role_summary['total_commission'] += txn.get('payable_commission', 0)
                role_summary['transaction_count'] += 1

            # Save calculated aggregates
            person_data['total_net_sales'] = person_total_net
            person_data['unpaid_commission'] = person_unpaid_commission
            person_data['total_potential_commission'] = person_potential_commission # New field available for report
            person_data['bracket_range_str'] = get_bracket_range_string(person_data.get('bracket_base', 0), person_data.get('model', ''))

            total_monthly_net += person_total_net
            total_monthly_commission += person_data.get('total_commission', 0)
        
        month_data['total_net_sales'] = total_monthly_net
        month_data['total_commission'] = total_monthly_commission
    
    return results

def prepare_frontend_data(results, summary_data, additional_commissions_df, filter_person_name=None):
    """
    Transforms and AGGREGATES the raw engine output into a structured dictionary
    optimized for the frontend.
    """
    # --- STEP 1: Perform all aggregations on the FULL dataset first ---
    results = _perform_frontend_aggregation(results)
    
    person_list = sorted(list(summary_data.keys()))
    months = sorted(list(results.keys()))

    # Chart Data Preparation
    chart_data = {
        'labels': months, 'datasets': {'total_sales': [], 'targets': [], 'persons': {}}
    }
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

    # Person-Centric Monthly Report
    person_monthly_report = {}
    for person in person_list:
        person_monthly_report[person] = {'months': {}, 'total_unpaid': summary_data.get(person, {}).get('remaining_balance', 0)}
    
    for month, month_data in results.items():
        for person_name, person_data in month_data['persons'].items():
            if person_name in person_monthly_report:
                # Calculate Original (Payable Commission without Bonus)
                original_commission = person_data['total_commission'] - person_data.get('additional_bonus', 0)
                
                # We already calculated these in _perform_frontend_aggregation
                monthly_potential_commission = person_data.get('total_potential_commission', 0)
                monthly_pending_commission = person_data.get('unpaid_commission', 0)
                
                person_monthly_report[person_name]['months'][month] = {
                    'bracket_base': person_data['bracket_base'],
                    'original_commission': original_commission, # This is "Payable Commission"
                    'additional_bonus': person_data.get('additional_bonus', 0), # Payable Bonus
                    'total_commission': person_data['total_commission'], # Final Total
                    'total_net_sales': person_data['total_net_sales'],
                    
                    'full_commission': monthly_potential_commission, # Potential Commission (on Base)
                    'pending_commission': monthly_pending_commission,
                    
                    'monthly_collection_ratio': person_data.get('monthly_collection_ratio', 0),
                    'total_paid_amount': person_data.get('total_paid_amount', 0),
                    'potential_bonus': person_data.get('potential_bonus', 0) # Potential Bonus (on Base)
                }

    frontend_data = {
        'personList': person_list,
        'overallSummary': list(summary_data.values()),
        'detailedReport': results,
        'personMonthlyReport': person_monthly_report,
        'chartData': chart_data
    }

    # --- STEP 2: Filter if requested ---
    if filter_person_name and filter_person_name in person_list:
        frontend_data['personList'] = [filter_person_name]
        frontend_data['overallSummary'] = [s for s in frontend_data['overallSummary'] if s['person_name'] == filter_person_name]
        
        filtered_detailed_report = {}
        for month, month_data in frontend_data['detailedReport'].items():
            if filter_person_name in month_data.get('persons', {}):
                new_month_data = month_data.copy()
                new_month_data['persons'] = {filter_person_name: month_data['persons'][filter_person_name]}
                filtered_detailed_report[month] = new_month_data
        frontend_data['detailedReport'] = filtered_detailed_report

        frontend_data['personMonthlyReport'] = {
            filter_person_name: frontend_data['personMonthlyReport'][filter_person_name]
        }

        filtered_persons_chart_data = {
            filter_person_name: frontend_data['chartData']['datasets']['persons'][filter_person_name]
        }
        frontend_data['chartData']['datasets']['persons'] = filtered_persons_chart_data

    return frontend_data
# end of app/main/utils.py