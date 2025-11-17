# ==============================================================================
# app/calculator/validator.py
# ------------------------------------------------------------------------------
# Handles the validation of the uploaded Excel file's structure and data types.
# ==============================================================================

import pandas as pd
from .schema import EXPECTED_SHEETS

def validate_excel_file(filepath):
    """
    Validates the structure and basic data types of the uploaded Excel file.

    Args:
        filepath (str): The path to the uploaded .xlsx file.

    Returns:
        tuple: A tuple containing:
            - dict: A dictionary of pandas DataFrames if validation is successful.
            - list: A list of human-readable error messages if validation fails.
    """
    errors = []
    dataframes = {}

    try:
        xls = pd.ExcelFile(filepath)
        sheet_names = xls.sheet_names
    except Exception as e:
        errors.append(f"فایل اکسل نامعتبر است یا قابل خواندن نیست. خطای فنی: {e}")
        return None, errors

    # 1. Check for presence of all required sheets
    for sheet_name in EXPECTED_SHEETS:
        if sheet_name not in sheet_names:
            errors.append(f"شیت ضروری '{sheet_name}' در فایل اکسل یافت نشد.")

    if errors:
        return None, errors  # Stop validation if sheets are missing

    # 2. Check each sheet for required columns and data types
    for sheet_name, rules in EXPECTED_SHEETS.items():
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)

            # 2a. Check for required columns
            missing_columns = [col for col in rules['required_columns'] if col not in df.columns]
            if missing_columns:
                errors.append(f"در شیت '{sheet_name}'، ستون‌های ضروری زیر یافت نشدند: {', '.join(missing_columns)}")
                continue  # Move to the next sheet

            # 2b. Check numeric columns for non-numeric values
            for col in rules['numeric_columns']:
                # Coerce to numeric, making non-numbers NaN
                numeric_series = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
                # Find rows where the original value was not empty but the numeric version is NaN
                invalid_rows = df[numeric_series.isna() & df[col].notna()]

                if not invalid_rows.empty:
                    for index in invalid_rows.index:
                        value = invalid_rows.loc[index, col]
                        errors.append(
                            f"خطا در شیت '{sheet_name}'، ردیف اکسل {index + 2}: "
                            f"مقدار '{value}' در ستون '{col}' باید یک عدد باشد."
                        )

            dataframes[sheet_name] = df

        except Exception as e:
            errors.append(f"خطایی در هنگام خواندن شیت '{sheet_name}' رخ داد. خطای فنی: {e}")

    if errors:
        return None, errors

    return dataframes, []