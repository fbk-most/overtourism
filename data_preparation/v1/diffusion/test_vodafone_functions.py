#!/usr/bin/env python3
"""
Quick test to verify the VodafoneData functions work correctly
"""

from VodafoneData import extract_date_info, extract_date_and_weekday_case_null_day

def test_functions():
    print("Testing VodafoneData functions...")
    print("=" * 50)
    
    # Test extract_date_info (for July/August format)
    print("Testing extract_date_info:")
    test_samples_regular = [
        "202408 01-15 - Feriale",
        "202407 16-31 - Festivo", 
        "202407 01-15 - Prefestivo",
    ]
    
    for sample in test_samples_regular:
        result = extract_date_info(sample)
        print(f"  '{sample}' -> {result}")
        if result is not None:
            date_str, is_weekday = result
            print(f"    Date: {date_str}, Is Weekday: {is_weekday} (type: {type(is_weekday)})")
    
    print("\nTesting extract_date_and_weekday_case_null_day:")
    test_samples_null = [
        "202410 - Prefestivo",
        "202410 - Feriale", 
        "202410 - Festivo"
    ]
    
    for sample in test_samples_null:
        result = extract_date_and_weekday_case_null_day(sample)
        print(f"  '{sample}' -> {result}")
        if result is not None:
            date_str, is_weekday = result
            print(f"    Date: {date_str}, Is Weekday: {is_weekday} (type: {type(is_weekday)})")

if __name__ == "__main__":
    test_functions()
