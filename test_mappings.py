#!/usr/bin/env python3
"""
Test the field mappings with actual JSON data
"""
import json

# Load the JSON data
with open('updated_sample_json.json', 'r') as f:
    json_data = json.load(f)

print("JSON fields available:")
for key in sorted(json_data.keys()):
    print(f"  {key}")

print(f"\nTotal JSON fields: {len(json_data)}")

# Test specific problematic fields
test_fields = [
    "Corporate Name",
    "Covered Person (AML)",
    "AMLA Category 1", 
    "Director/Officer_Name",
    "Stockholder_Name",
    "Subscribed Capital_Total",
    "Paid-Up Capital_Total",
    "Number of Stockholders with ≥100 shares"
]

print("\nField mapping test:")
print("=" * 50)

for field in test_fields:
    # Test the mapping logic
    found_keys = []
    
    # Basic transforms
    transforms = [
        field,
        field.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace('≥', '').replace('.', '').replace("'", ''),
        field.replace(' ', '_').replace('/', '_').replace('-', '_'),
        field.lower().replace(' ', '_'),
    ]
    
    # Check specific mappings
    field_mappings = {
        'Corporate Name': 'business_trade_name',
        'Covered Person (AML)': 'covered_person_aml',
        'AMLA Category 1': 'amla_category_1',
        'Director/Officer_Name': 'director_officer_name_1',
        'Stockholder_Name': 'stockholder_name_1',
        'Subscribed Capital_Total': 'filipino_subscribed_capital_amount_php_1',
        'Paid-Up Capital_Total': 'filipino_paid_up_capital_amount_php_1',
        'Number of Stockholders with ≥100 shares': 'number_stockholders_100_plus_shares'
    }
    
    if field in field_mappings:
        transforms.insert(0, field_mappings[field])
    
    # Find matches
    for transform in transforms:
        if transform in json_data:
            found_keys.append(transform)
    
    print(f"\nField: '{field}'")
    if found_keys:
        print(f"✅ Found matches: {found_keys}")
        for key in found_keys[:1]:  # Show first match
            print(f"   Value: {json_data[key]}")
    else:
        print(f"❌ No matches found")
        print(f"   Tried: {transforms[:3]}...")  # Show first 3 attempts