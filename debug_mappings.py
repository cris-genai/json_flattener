#!/usr/bin/env python3
"""
Debug the field mappings to see what's happening
"""
import json

# Load the JSON data
json_data = {
    "document_type": "General Information Sheet",
    "for_the_year": "2024",
    "business_trade_name": "BOOST TECHNOLOGIES INC.",
    "date_registered": "03/11/2024",
    "fiscal_year_end": "December 01",
    "sec_registration_number": "2024030140928-84",
    "corporate_tin": "010-804-728",
    "covered_person_aml": "No",
    "amla_category_8": "N/A",
    "amla_compliance_status": "No",
    "director_officer_name_1": "NATHAN J. MARASIGAN",
    "director_officer_inc_r_1": "Y",
    "director_officer_exec_comm_1": "N/A",
    "director_officer_name_2": "RUSSELL STANLEY Q. GERONIMO",
    "director_officer_inc_r_2": "Y",
    "director_officer_exec_comm_2": "N/A",
    "stockholder_name_1": "RUSSELL STANLEY Q. GERONIMO",
    "stockholder_shares_subscribed_number_1": 500000,
    "stockholder_shares_subscribed_amount_1": 500000,
    "stockholder_amount_paid_1": 50000,
    "stockholder_name_2": "NATHAN J. MARASIGAN",
    "stockholder_shares_subscribed_number_2": 500000,
    "stockholder_shares_subscribed_amount_2": 500000,
    "stockholder_amount_paid_2": 50000
}

# Test problematic fields
problem_fields = [
    "Corporate Name",
    "Covered Person (AML)",
    "AMLA Category 8",
    "AMLA Compliance Status", 
    "Director/Officer_INC'R",
    "Director/Officer_Exec Comm.",
    "Stockholder_Total Shares Subscribed_No.",
    "Stockholder_Total Shares Subscribed_Amount (PHP)",
    "Stockholder_Amount Paid (PHP)"
]

print("=== DEBUGGING FIELD MAPPINGS ===")
print(f"Available JSON keys: {sorted(json_data.keys())}")
print()

# Test each problematic field
for field_name in problem_fields:
    print(f"Testing field: '{field_name}'")
    
    # Create transformations like the app does
    possible_keys = [field_name]
    
    base_transforms = [
        field_name.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace('≥', '').replace('.', '').replace("'", ''),
        field_name.replace(' ', '_').replace('/', '_').replace('-', '_'),
        field_name.lower().replace(' ', '_'),
        field_name.replace(' ', '').lower(),
    ]
    
    # Add specific mappings
    field_mappings = {
        'Corporate Name': 'business_trade_name',  # Should map to business_trade_name
        'Covered Person (AML)': 'covered_person_aml',
        'AMLA Category 8': 'amla_category_8',
        'AMLA Compliance Status': 'amla_compliance_status',
        'Director/Officer_INC\'R': 'director_officer_inc_r',
        'Director/Officer_Exec Comm.': 'director_officer_exec_comm',
        'Stockholder_Total Shares Subscribed_No.': 'stockholder_shares_subscribed_number',
        'Stockholder_Total Shares Subscribed_Amount (PHP)': 'stockholder_shares_subscribed_amount',
        'Stockholder_Amount Paid (PHP)': 'stockholder_amount_paid',
    }
    
    if field_name in field_mappings:
        mapped_field = field_mappings[field_name]
        if mapped_field:
            base_transforms.insert(0, mapped_field)
    
    possible_keys.extend(base_transforms)
    
    # Remove duplicates
    seen = set()
    possible_keys = [x for x in possible_keys if not (x in seen or seen.add(x))]
    
    # For repeated fields, add numbered versions
    if field_name.startswith(('Director/Officer', 'Stockholder')):
        base_key = field_name.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace("'", '')
        for i in range(1, 3):  # Test _1 and _2
            numbered_key = f"{base_key}_{i}"
            possible_keys.insert(0, numbered_key)
    
    print(f"  Trying keys: {possible_keys[:5]}...")  # Show first 5
    
    # Find matches
    found = False
    for key in possible_keys:
        if key in json_data:
            print(f"  ✅ FOUND: '{key}' = {json_data[key]}")
            found = True
            break
    
    if not found:
        print(f"  ❌ NOT FOUND")
        # Show what keys we have that are similar
        similar_keys = [k for k in json_data.keys() if any(part in k.lower() for part in field_name.lower().split())]
        if similar_keys:
            print(f"     Similar keys in JSON: {similar_keys}")
    
    print()