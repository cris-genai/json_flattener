#!/usr/bin/env python3
"""
Test script to verify field name mappings work correctly
"""

def create_field_transforms(field_name):
    """Test the field transformation logic"""
    possible_keys = [
        field_name,  # Exact match
    ]
    
    # Create various field name transformations for better matching
    base_transforms = [
        field_name.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace('≥', '').replace('.', '').replace("'", ''),  # Most comprehensive transform
        field_name.replace(' ', '_').replace('/', '_').replace('-', '_'),  # Simple transforms
        field_name.lower().replace(' ', '_'),  # Basic snake case
        field_name.replace(' ', '').lower(),  # Remove all spaces
    ]
    
    # Add all transformations to possible keys
    possible_keys.extend(base_transforms)
    
    # Remove duplicates while preserving order
    seen = set()
    possible_keys = [x for x in possible_keys if not (x in seen or seen.add(x))]
    
    return possible_keys

# Test cases
test_cases = [
    "Covered Person (AML)",
    "Number of Stockholders with ≥100 shares",
    "Director/Officer_Name", 
    "Stockholder_Total Shares Subscribed_Amount (PHP)",
    "SEC Reg. No.",
    "Business/Trade Name",
    "Director/Officer_INC'R",
    "UBO_Name",
    "AMLA Category 1"
]

print("Field Name Mapping Test:")
print("=" * 50)

for field in test_cases:
    transforms = create_field_transforms(field)
    print(f"\nField: '{field}'")
    print("Possible matches:")
    for i, transform in enumerate(transforms, 1):
        print(f"  {i}. {transform}")

# Expected JSON field names
expected_mappings = {
    "Covered Person (AML)": "covered_person_aml",
    "Number of Stockholders with ≥100 shares": "number_stockholders_100_plus_shares", 
    "Director/Officer_Name": "director_officer_name_1",
    "Stockholder_Total Shares Subscribed_Amount (PHP)": "stockholder_shares_subscribed_amount_1",
    "SEC Reg. No.": "sec_registration_number",
    "Business/Trade Name": "business_trade_name",
    "UBO_Name": "ubo_name_1"
}

print("\n" + "=" * 50)
print("EXPECTED MAPPING VERIFICATION:")
print("=" * 50)

for ground_truth_field, expected_json_field in expected_mappings.items():
    transforms = create_field_transforms(ground_truth_field)
    
    # Check if expected field is in transforms
    match_found = any(expected_json_field in transform or transform in expected_json_field for transform in transforms)
    
    print(f"\nGround Truth: '{ground_truth_field}'")
    print(f"Expected JSON: '{expected_json_field}'")
    print(f"Match Found: {'✅ YES' if match_found else '❌ NO'}")
    
    if not match_found:
        print("  Transforms generated:")
        for transform in transforms:
            print(f"    - {transform}")