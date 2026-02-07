# start of app/main/utils.py
# ==============================================================================
# app/main/utils.py
# ------------------------------------------------------------------------------
# Utilities for preparing data for the frontend reports.
# Updated to support the 12-column Full Excel Flow structure.
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
    Iterates through the raw engine results and calculates the 12 key metrics
    for each person in each month. 
    FIXED: Prevents double-counting of Sales Volume (Input Metrics) when a user 
    has multiple roles on the same invoice.
    """
    for month_key, month_data in results.items():
        total_monthly_net = 0
        total_monthly_commission = 0 

        for person_name, person_data in month_data.get('persons', {}).items():
            # Initialize 12-Column Aggregators
            agg_total_declared = 0.0
            agg_total_base = 0.0
            agg_total_acceptable = 0.0
            
            agg_comm_base = 0.0
            agg_comm_acceptable = 0.0
            agg_comm_collected = 0.0
            
            agg_bonus_base = person_data.get('bonus_base', 0.0)
            agg_bonus_acceptable = person_data.get('bonus_acceptable', 0.0)
            agg_bonus_collected = person_data.get('bonus_collected', 0.0)
            
            person_data['roles_summary'] = {}

            # TRACKING SET to prevent double counting inputs per invoice
            # We use invoice_link as primary ID, fallback to company name
            processed_invoices = set()

            # Iterate through transactions to aggregate sums
            for txn in person_data.get('transactions', []):
                
                # --- IDENTIFY UNIQUE INVOICE ---
                # Create a unique key for this invoice within this person's list
                inv_link = txn.get('invoice_link', '')
                company = txn.get('company', '')
                # Use link if available, otherwise company + net_value to differentiate
                unique_key = inv_link if inv_link and inv_link != 'nan' else f"{company}_{txn.get('net_value', 0)}"
                
                # --- 1. Input Metrics (DEDUPLICATED) ---
                # Only add the Sales Volume metrics if we haven't seen this invoice for this person yet
                if unique_key not in processed_invoices:
                    net_val = txn.get('net_value', 0)
                    base_val = txn.get('commission_base', 0)
                    is_accept = txn.get('is_acceptable', False)
                    
                    agg_total_declared += net_val
                    agg_total_base += base_val
                    if is_accept:
                        agg_total_acceptable += base_val
                    
                    processed_invoices.add(unique_key)
                
                # --- 2. Commission Metrics (ALWAYS SUM) ---
                # Commissions are role-based. If I am SN and SC, I get paid for both.
                # So we sum these every time.
                
                comm_base_txn = txn.get('full_commission', 0)
                agg_comm_base += comm_base_txn
                
                if txn.get('is_acceptable', False):
                    agg_comm_acceptable += comm_base_txn
                
                agg_comm_collected += txn.get('payable_commission', 0)

                # Roles Summary Aggregation
                role = txn.get('role', 'Unknown')
                role_summary = person_data['roles_summary'].setdefault(role, {
                    'total_sales': 0, 'total_commission': 0, 'transaction_count': 0
                })
                # Note: We add sales to role summary to show performance PER ROLE, 
                # even if it totals > total_declared in the summary. This is intended for drill-down.
                role_summary['total_sales'] += txn.get('commission_base', 0)
                role_summary['total_commission'] += txn.get('payable_commission', 0)
                role_summary['transaction_count'] += 1

            # 3. Final Calculations
            agg_payable_amount = agg_comm_collected + agg_bonus_collected
            
            agg_remaining_acceptable = (agg_comm_acceptable + agg_bonus_acceptable) - agg_payable_amount
            agg_remaining_base = (agg_comm_base + agg_bonus_base) - agg_payable_amount

            # Update person_data with these new keys
            person_data['total_declared'] = agg_total_declared
            person_data['total_base'] = agg_total_base
            person_data['total_acceptable'] = agg_total_acceptable
            
            person_data['commission_base'] = agg_comm_base
            person_data['commission_acceptable'] = agg_comm_acceptable
            person_data['commission_collected'] = agg_comm_collected
            
            person_data['bonus_base'] = agg_bonus_base
            person_data['bonus_acceptable'] = agg_bonus_acceptable
            person_data['bonus_collected'] = agg_bonus_collected
            
            person_data['payable_amount'] = agg_payable_amount
            person_data['remaining_acceptable'] = agg_remaining_acceptable
            person_data['remaining_base'] = agg_remaining_base
            
            person_data['bracket_range_str'] = get_bracket_range_string(person_data.get('bracket_base', 0), person_data.get('model', ''))

            # Accumulate monthly totals
            total_monthly_net += agg_total_declared
            total_monthly_commission += agg_payable_amount
        
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
    
    # Generate list of all persons found in the data (summary_data comes from DB or Engine summary)
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
        # Chart uses 'bracket_base' which is essentially 'total_acceptable' for tier calculation
        monthly_total_sales = sum(results[month]['persons'].get(p, {}).get('total_acceptable', 0) for p in person_list)
        chart_data['datasets']['total_sales'].append(monthly_total_sales)
        
        for person_name in person_list:
            chart_data['datasets']['persons'][person_name][i] = results[month]['persons'].get(person_name, {}).get('total_acceptable', 0)
        
        target_value = last_valid_target
        if targets_lookup is not None:
            year, month_num = map(int, month.split('-'))
            if (year, month_num) in targets_lookup.index:
                target_data = targets_lookup.loc[(year, month_num)]
                if not pd.isna(target_data.get('تارگت جمعی')): target_value = target_data.get('تارگت جمعی')
        last_valid_target = target_value
        chart_data['datasets']['targets'].append(target_value * 0.1) # Converting Rial to Toman approx if needed

    # Person-Centric Monthly Report
    person_monthly_report = {}
    for person in person_list:
        # Initializing total unpaid/remaining from summary
        person_monthly_report[person] = {
            'months': {}, 
            'total_remaining_acceptable': summary_data.get(person, {}).get('remaining_acceptable', 0)
        }
    
    for month, month_data in results.items():
        for person_name, person_data in month_data['persons'].items():
            if person_name in person_monthly_report:
                person_monthly_report[person_name]['months'][month] = {
                    # Input
                    'total_declared': person_data['total_declared'],
                    'total_base': person_data['total_base'],
                    'total_acceptable': person_data['total_acceptable'],
                    
                    # Commission
                    'commission_base': person_data['commission_base'],
                    'commission_acceptable': person_data['commission_acceptable'],
                    'commission_collected': person_data['commission_collected'],
                    
                    # Bonus
                    'bonus_base': person_data['bonus_base'],
                    'bonus_acceptable': person_data['bonus_acceptable'],
                    'bonus_collected': person_data['bonus_collected'],
                    
                    # Totals
                    'payable_amount': person_data['payable_amount'],
                    'remaining_acceptable': person_data['remaining_acceptable'],
                    'remaining_base': person_data['remaining_base'],
                    
                    # Extra Info
                    'monthly_collection_ratio': person_data.get('monthly_collection_ratio', 0),
                    'total_paid_amount': person_data.get('total_paid_amount', 0),
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