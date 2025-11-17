import pytest
import pandas as pd
import os
import logging
import json

# --- Configuration at the top for easy editing ---

REAL_DATA_FILENAME = 'real_data.xlsx'

# Mode 1: Audit specific row numbers from the Excel file
AUDIT_ROW_NUMBERS = [28, 52] 

# Mode 2: Trace all calculations for a single person
TRACE_PERSON_NAME = 'پریناز لواسانی'

# Optional filter for Mode 2: Specify a month ('YYYY-MM') to trace, or set to None to trace all months.
# Example: '1404-4' to only see logs and summaries for Month 4.
TRACE_MONTH_FILTER = '1404-5' # SET TO None TO SEE ALL MONTHS FOR THE PERSON

# --- Fixtures (app_with_db and live_dataframes are unchanged) ---
@pytest.fixture(scope="module")
def app_with_db():
    from app import create_app, db
    from app.seed import seed_data
    app = create_app()
    app.config.update({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        print("\n--- Setting up in-memory database and seeding rules... ---")
        db.create_all()
        seed_data()
        print("--- Database setup complete. ---\n")
        yield app
        db.drop_all()

@pytest.fixture(scope="module")
def live_dataframes():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, REAL_DATA_FILENAME)
    if not os.path.exists(filepath):
        pytest.fail(f"Real data file not found: '{filepath}'")
    try:
        xls = pd.ExcelFile(filepath)
        sheet_names = xls.sheet_names
        dataframes = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in sheet_names}
        return dataframes
    except Exception as e:
        pytest.fail(f"Failed to read the Excel file '{filepath}'. Error: {e}")

# --- THE AUDIT TESTS ---

@pytest.mark.audit_rows
def test_audit_specific_rows(live_dataframes, app_with_db, caplog):
    """
    AUDIT MODE 1: Runs the engine on the FULL live Excel file and shows
    detailed logs ONLY for the selected AUDIT_ROW_NUMBERS.
    """
    from app.calculator.engine import CalculationConfig, calculate_commissions
    
    print("\n\n" + "="*20 + " RUNNING AUDIT MODE 1: SPECIFIC ROWS " + "="*20)

    CalculationConfig._instance = None
    
    with caplog.at_level(logging.DEBUG):
        calculate_commissions(live_dataframes)

    print("\n--- DETAILED AUDIT LOGS FOR SELECTED ROWS ---")
    if not AUDIT_ROW_NUMBERS:
        print("No rows selected for audit. Please populate AUDIT_ROW_NUMBERS.")
        
    for row_num in AUDIT_ROW_NUMBERS:
        found_log = False
        for record in caplog.get_records('call'):
            if record.levelno == logging.DEBUG and f"Audit Log for Row {row_num}" in record.message:
                print(record.message)
                found_log = True
                break
        if not found_log:
            print(f"\n--- No detailed audit log found for Excel Row {row_num}. It may have been skipped or not logged at DEBUG level. ---")
    
    print("\n--- ROW AUDIT TEST COMPLETE ---")
    assert True


@pytest.mark.trace_person
def test_trace_single_person(live_dataframes, app_with_db, caplog):
    """
    AUDIT MODE 2: Runs the engine on the FULL live Excel file and shows
    all relevant logs and final summaries for a single person, with an optional month filter.
    """
    from app.calculator.engine import CalculationConfig, calculate_commissions, summarize_results
    
    mode_title = f"TRACING PERSON: '{TRACE_PERSON_NAME}'"
    if TRACE_MONTH_FILTER:
        mode_title += f" FOR MONTH: {TRACE_MONTH_FILTER}"
    print("\n\n" + "="*20 + f" RUNNING AUDIT MODE 2: {mode_title} " + "="*20)
    
    CalculationConfig._instance = None
    
    with caplog.at_level(logging.DEBUG):
        results, config = calculate_commissions(live_dataframes)
        summary = summarize_results(results, live_dataframes.get('Commissions paid'), config)

    # --- 1. Filter and Print All Relevant Audit Logs for the Person and Month ---
    print(f"\n--- DETAILED AUDIT LOGS FOR TRANSACTIONS INVOLVING '{TRACE_PERSON_NAME}'" + (f" IN MONTH {TRACE_MONTH_FILTER}" if TRACE_MONTH_FILTER else "") + " ---")
    
    sales_df = live_dataframes['Sales data']
    person_row_indices = []
    role_columns = ['بازاریاب', 'مذاکره کننده ارشد', 'هماهنگ کننده فروش']
    
    for index, row in sales_df.iterrows():
        # Check if the person is in this row
        is_person_in_row = any(str(row.get(col, '')).strip() == TRACE_PERSON_NAME for col in role_columns)
        if not is_person_in_row:
            continue
            
        # If there's a month filter, check if the row's month matches
        if TRACE_MONTH_FILTER:
            try:
                row_month_key = f"{int(row.get('سال'))}-{int(row.get('ماه'))}"
                if row_month_key != TRACE_MONTH_FILTER:
                    continue
            except (ValueError, TypeError):
                continue # Skip rows with bad date format
        
        person_row_indices.append(index + 2)
    
    # Now, print the logs for the filtered rows
    if not person_row_indices:
        print("No transactions found for the specified person and month filter.")
    else:
        for row_num in sorted(list(set(person_row_indices))):
            for record in caplog.get_records('call'):
                if record.levelno == logging.DEBUG and f"Audit Log for Row {row_num}" in record.message:
                    print(record.message)
                    break
    
    # --- 2. Print the Month-by-Month Breakdown for the Person (respecting the filter) ---
    print(f"\n\n--- MONTHLY CALCULATION BREAKDOWN FOR '{TRACE_PERSON_NAME}' ---")
    
    found_months = False
    for month_key in sorted(results.keys()):
        # If there is a filter, skip months that don't match
        if TRACE_MONTH_FILTER and month_key != TRACE_MONTH_FILTER:
            continue

        person_data = results[month_key].get('persons', {}).get(TRACE_PERSON_NAME)
        if person_data:
            found_months = True
            original = person_data['total_commission'] - person_data.get('additional_bonus', 0)
            bonus = person_data.get('additional_bonus', 0)
            
            print(f"\n  Month: {month_key}")
            print(f"    - Bracket Base      : {person_data.get('bracket_base', 0):,.0f} Toman")
            print(f"    - Original Commission: {original:,.0f} Toman")
            print(f"    - Additional Bonus  : {bonus:,.0f} Toman")
            print(f"    - TOTAL FOR MONTH   : {person_data['total_commission']:,.0f} Toman")

    if not found_months:
        print("No monthly summary data found for the specified person and filter.")

    # --- 3. Print the Final (Overall) Summary for the Person ---
    # This summary is always for the full calculation, not just the filtered month.
    print(f"\n\n--- OVERALL FINAL SUMMARY FOR '{TRACE_PERSON_NAME}' (All Months) ---")
    person_summary = summary.get(TRACE_PERSON_NAME)
    if person_summary:
        print(json.dumps(person_summary, indent=2, ensure_ascii=False))
    else:
        print("Person not found in final summary.")

    print("\n--- PERSON TRACE TEST COMPLETE ---")
    assert True