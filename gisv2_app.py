import streamlit as st
import json
import pandas as pd
import io
from typing import Any, Dict, Union, List, Tuple
import zipfile
from datetime import datetime
import streamlit.components.v1 as components
from difflib import SequenceMatcher

# Set page config
st.set_page_config(
    page_title="GIS JSON Flattener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def create_clipboard_component(text_data, button_text, success_message):
    """Create a working clipboard copy component"""
    
    # Create unique key for this component
    component_key = f"clipboard_{abs(hash(text_data[:100]))}"
    
    # Escape the text data for JavaScript
    escaped_text = text_data.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    
    # HTML and JavaScript for clipboard functionality
    html_code = f"""
    <div style="margin: 10px 0;">
        <button id="copyBtn_{component_key}" 
                onclick="copyToClipboard_{component_key}()" 
                style="
                    background-color: #ff4b4b;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                ">
            {button_text}
        </button>
        <span id="status_{component_key}" style="margin-left: 10px; color: green; font-weight: bold;"></span>
    </div>
    
    <script>
        function copyToClipboard_{component_key}() {{
            const text = "{escaped_text}";
            
            if (navigator.clipboard) {{
                navigator.clipboard.writeText(text).then(function() {{
                    document.getElementById('status_{component_key}').innerHTML = '✅ {success_message}';
                    document.getElementById('copyBtn_{component_key}').innerHTML = '✅ Copied!';
                    setTimeout(() => {{
                        document.getElementById('status_{component_key}').innerHTML = '';
                        document.getElementById('copyBtn_{component_key}').innerHTML = '{button_text}';
                    }}, 3000);
                }}, function(err) {{
                    console.error('Clipboard failed: ', err);
                    fallbackCopy_{component_key}(text);
                }});
            }} else {{
                fallbackCopy_{component_key}(text);
            }}
        }}
        
        function fallbackCopy_{component_key}(text) {{
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            
            try {{
                document.execCommand('copy');
                document.getElementById('status_{component_key}').innerHTML = '✅ {success_message}';
                document.getElementById('copyBtn_{component_key}').innerHTML = '✅ Copied!';
                setTimeout(() => {{
                    document.getElementById('status_{component_key}').innerHTML = '';
                    document.getElementById('copyBtn_{component_key}').innerHTML = '{button_text}';
                }}, 3000);
            }} catch (err) {{
                document.getElementById('status_{component_key}').innerHTML = '❌ Copy failed - select text below';
                const preElement = document.createElement('pre');
                preElement.style.cssText = 'border:1px solid #ccc;padding:10px;max-height:200px;overflow:auto;background:#f9f9f9;margin:10px 0;user-select:all;';
                preElement.textContent = text;
                document.getElementById('copyBtn_{component_key}').parentNode.appendChild(preElement);
            }}
            
            document.body.removeChild(textArea);
        }}
    </script>
    """
    
    return html_code

def flatten_json_data(json_data: Union[str, Dict]) -> Dict[str, Any]:
    """
    Flattens a JSON object (including arrays and nested objects) into a flat dictionary.
    """
    
    def flatten_dict(obj: Any, parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """Recursively flatten nested dictionaries and arrays."""
        items = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{parent_key}{sep}{key}" if parent_key else key
                items.extend(flatten_dict(value, new_key, sep).items())
                
        elif isinstance(obj, list):
            if len(obj) == 0:
                items.append((parent_key, "[]"))
            else:
                for i, item in enumerate(obj):
                    new_key = f"{parent_key}{sep}{i}"
                    if isinstance(item, (dict, list)):
                        items.extend(flatten_dict(item, new_key, sep).items())
                    else:
                        items.append((new_key, item))
        else:
            items.append((parent_key, obj))
            
        return dict(items)
    
    # Parse JSON if it's a string
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")
    else:
        data = json_data
    
    return flatten_dict(data)

def format_field_name(field_name: str) -> str:
    """Convert snake_case field names to Title Case for better readability."""
    return field_name.replace('_', ' ').title()

def analyze_json_structure(json_data: Union[str, Dict]) -> Dict[str, Any]:
    """Analyze the structure of JSON to understand arrays and nested objects."""
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    def analyze_recursive(obj: Any, path: str = "") -> Dict[str, Any]:
        analysis = {
            'arrays': [],
            'nested_objects': [],
            'primitive_fields': 0
        }
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(value, list):
                    analysis['arrays'].append({
                        'path': current_path,
                        'length': len(value),
                        'type': 'array'
                    })
                    # Analyze array contents
                    for item in value[:1]:  # Sample first item
                        sub_analysis = analyze_recursive(item, f"{current_path}[0]")
                        analysis['arrays'].extend(sub_analysis['arrays'])
                        analysis['nested_objects'].extend(sub_analysis['nested_objects'])
                        analysis['primitive_fields'] += sub_analysis['primitive_fields']
                elif isinstance(value, dict):
                    analysis['nested_objects'].append(current_path)
                    sub_analysis = analyze_recursive(value, current_path)
                    analysis['arrays'].extend(sub_analysis['arrays'])
                    analysis['nested_objects'].extend(sub_analysis['nested_objects'])
                    analysis['primitive_fields'] += sub_analysis['primitive_fields']
                else:
                    analysis['primitive_fields'] += 1
        
        return analysis
    
    return analyze_recursive(data)

def map_sec_gis_fields(json_data: Union[str, Dict]) -> Dict[str, Any]:
    """
    Maps JSON data to SEC GIS field format
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    # SEC GIS Field mapping - following exact arrangement
    field_mapping = {
        "Document Type": data.get("document_type", ""),
        "For the year": data.get("for_the_year", ""),
        "Corporate Name": data.get("business_trade_name", ""),
        "Business/Trade Name": data.get("business_trade_name", ""),
        "Date Registered": data.get("date_registered", ""),
        "Fiscal Year End": data.get("fiscal_year_end", ""),
        "SEC Registration Number": data.get("sec_registration_number", ""),
        "Corporate TIN": data.get("corporate_tin", ""),
        "Website/URL": data.get("website_url", ""),
        "Principal Office Address": data.get("principal_office_address", ""),
        "Business Address": data.get("business_address", ""),
        "Official e-mail address": data.get("official_email", ""),
        "Alternate Email Address": data.get("alternate_email", ""),
        "Official Mobile Number": data.get("official_mobile", ""),
        "Alternate Mobile Number": data.get("alternate_mobile", ""),
        "Primary Purpose/Industry": data.get("primary_purpose_industry", ""),
        "Industry Classification": data.get("industry_classification", ""),
        "Geographical Code": data.get("geographical_code", ""),
        "Parent Company Name": data.get("parent_company_name", ""),
        "Parent Company SEC Reg. No.": data.get("parent_company_sec_reg_no", ""),
        "Parent Company Address": data.get("parent_company_address", ""),
        "Subsidiary/Affiliate": data.get("subsidiary_affiliate", ""),
        "Subsidiary/Affiliate SEC Reg. No.": data.get("subsidiary_affiliate_sec_reg_no", ""),
        "Subsidiary/Affiliate Address": data.get("subsidiary_affiliate_address", ""),
        "External Auditor": data.get("external_auditor", ""),
        "Auditor SEC Accreditation Number": data.get("auditor_sec_accreditation_number", ""),
        "Covered Person (AML)": data.get("covered_person_aml", ""),
        "AMLA Category 1": data.get("amla_category_1", ""),
        "AMLA Category 2": data.get("amla_category_2", ""),
        "AMLA Category 3": data.get("amla_category_3", ""),
        "AMLA Category 4": data.get("amla_category_4", ""),
        "AMLA Category 5": data.get("amla_category_5", ""),
        "AMLA Category 6": data.get("amla_category_6", ""),
        "AMLA Category 7": data.get("amla_category_7", ""),
        "AMLA Category 8": data.get("amla_category_8", ""),
        "AMLA Compliance Status": data.get("amla_compliance_status", ""),
        "Corporate Name (2)": data.get("business_trade_name", ""),
        "Corporate Name (3)": data.get("business_trade_name", ""),
        "Auth Capital Stock - Type of Shares 1": data.get("auth_capital_stock_type_of_shares_1", ""),
        "Auth Capital Stock - Number of Shares 1": data.get("auth_capital_stock_number_of_shares_1", ""),
        "Auth Capital Stock - Par / Stated Value 1": data.get("auth_capital_stock_par_stated_value_1", ""),
        "Auth Capital Stock - Amount (PhP) 1": data.get("auth_capital_stock_amount_php_1", ""),
        "Filipino Subscribed Capital - Type of Shares 1": data.get("filipino_subscribed_capital_type_of_shares_1", ""),
        "Filipino Subscribed Capital - Number of Shares 1": data.get("filipino_subscribed_capital_number_of_shares_1", ""),
        "Filipino Subscribed Capital - Par / Stated Value 1": data.get("filipino_subscribed_capital_par_stated_value_1", ""),
        "Filipino Subscribed Capital - Amount (PhP) 1": data.get("filipino_subscribed_capital_amount_php_1", ""),
        "Foreign Subscribed Capital - Type of Shares 1": data.get("foreign_subscribed_capital_type_of_shares_1", ""),
        "Foreign Subscribed Capital - Number of Shares 1": data.get("foreign_subscribed_capital_number_of_shares_1", ""),
        "Foreign Subscribed Capital - Par / Stated Value 1": data.get("foreign_subscribed_capital_par_stated_value_1", ""),
        "Foreign Subscribed Capital - Amount (PhP) 1": data.get("foreign_subscribed_capital_amount_php_1", ""),
        "Subscribed Capital_% Foreigh Equity": data.get("subscribed_capital_foreign_equity_percentage", ""),
        "Subscribed Capital_Total": data.get("subscribed_capital_total", ""),
        "Filipino Paid-Up Capital - Type of Shares 1": data.get("filipino_paid_up_capital_type_of_shares_1", ""),
        "Filipino Paid-up Capital Number of Shares 1": data.get("filipino_paid_up_capital_number_of_shares_1", ""),
        "Filipino Paid-Up Capital - Par / Stated Value 1": data.get("filipino_paid_up_capital_par_stated_value_1", ""),
        "Filipino Paid-Up Capital - Amount (PhP) 1": data.get("filipino_paid_up_capital_amount_php_1", ""),
        "Foreign Paid-Up Capital - Type of Shares 1": data.get("foreign_paid_up_capital_type_of_shares_1", ""),
        "Foreign Paid-up Capital Number of Shares 1": data.get("foreign_paid_up_capital_number_of_shares_1", ""),
        "Foreign Paid-Up Capital - Par / Stated Value 1": data.get("foreign_paid_up_capital_par_stated_value_1", ""),
        "Foreign Paid-Up Capital - Amount (PhP) 1": data.get("foreign_paid_up_capital_amount_php_1", ""),
        "Paid-up Capital_% Foreigh Equity": data.get("paid_up_capital_foreign_equity_percentage", ""),
        "Paid-Up Capital_Total": data.get("paid_up_capital_total", ""),
        "Corporate Name (4)": data.get("business_trade_name", ""),
        "Corporate Name (5)": data.get("business_trade_name", ""),
        "Corporate Name (6)": data.get("business_trade_name", ""),
    }
    
    # Add Directors/Officers - up to 20 entries as per Pydantic model
    for i in range(1, 21):  # 1-20 Director/Officer entries
        field_mapping[f"Director/Officer {i} Name"] = data.get(f"director_officer_name_{i}", "")
        field_mapping[f"Director/Officer {i} Address"] = data.get(f"director_officer_address_{i}", "")
        field_mapping[f"Director/Officer {i} Nationality"] = data.get(f"director_officer_nationality_{i}", "")
        field_mapping[f"Director/Officer {i} INC'R"] = data.get(f"director_officer_inc_r_{i}", "")
        field_mapping[f"Director/Officer {i} Board"] = data.get(f"director_officer_board_{i}", "")
        field_mapping[f"Director/Officer {i} Gender"] = data.get(f"director_officer_gender_{i}", "")
        field_mapping[f"Director/Officer {i} Stock Holder"] = data.get(f"director_officer_stock_holder_{i}", "")
        field_mapping[f"Director/Officer {i} Officer"] = data.get(f"director_officer_officer_{i}", "")
        field_mapping[f"Director/Officer {i} Exec Comm."] = data.get(f"director_officer_exec_comm_{i}", "")
        field_mapping[f"Director/Officer {i} TIN"] = data.get(f"director_officer_tin_{i}", "")
    
    # Continue with remaining fields
    field_mapping.update({
        "Total Number of Stockholders": data.get("total_number_stockholders", ""),
        "Number of Stockholders with ≥100 shares": data.get("number_stockholders_100_plus_shares", ""),
        "Total Assets (Latest Audited FS)": data.get("total_assets", ""),
    })
    
    # Add Stockholders - up to 10 entries as per Pydantic model
    for i in range(1, 11):  # 1-10 Stockholder entries
        field_mapping[f"Stockholder {i} Name"] = data.get(f"stockholder_name_{i}", "")
        field_mapping[f"Stockholder {i} Nationality"] = data.get(f"stockholder_nationality_{i}", "")
        field_mapping[f"Stockholder {i} Address"] = data.get(f"stockholder_address_{i}", "")
        field_mapping[f"Stockholder {i} Total Shares Subscribed_No."] = data.get(f"stockholder_shares_subscribed_number_{i}", "")
        field_mapping[f"Stockholder {i} Total Shares Subscribed_Amount (PHP)"] = data.get(f"stockholder_shares_subscribed_amount_{i}", "")
        field_mapping[f"Stockholder {i} % of Ownership"] = data.get(f"stockholder_ownership_percentage_{i}", "")
        field_mapping[f"Stockholder {i} Amount Paid (PHP)"] = data.get(f"stockholder_amount_paid_{i}", "")
        field_mapping[f"Stockholder {i} TIN"] = data.get(f"stockholder_tin_{i}", "")
    
    # Add remaining financial and other information
    field_mapping.update({
        "Subscribed Capital_Total (PHP) (from Stockholder detail pages)": data.get("subscribed_capital_total_from_stockholders", ""),
        "Paid-Up Capital_Total (PHP) (from Stockholder detail pages)": data.get("paid_up_capital_total_from_stockholders", ""),
        "Subscribed Capital_Total (PHP) (from Stockholder detail pages)": data.get("filipino_subscribed_capital_amount_php_1", ""),
        "Paid-Up Capital_Total (PHP) (from Stockholder detail pages)": data.get("filipino_paid_up_capital_amount_php_1", ""),
        "Unrestricted Retained Earnings (PHP)": data.get("unrestricted_retained_earnings", ""),
        "Prior year Dividends_Cash (PHP)": data.get("prior_year_dividends_cash", ""),
        "Prior year Dividends_Stock (PHP)": data.get("prior_year_dividends_stock", ""),
        "Prior year Dividends_Property (PHP)": data.get("prior_year_dividends_property", ""),
        "Prior year Dividends_Total (PHP)": data.get("prior_year_dividends_total", ""),
        "Share Issuance_Date": data.get("share_issuance_date", ""),
        "Share Issuance_No": data.get("share_issuance_number", ""),
        "Share Issuance_Amount (PHP)": data.get("share_issuance_amount", ""),
        "SEC License Type": data.get("sec_license_type", ""),
        "SEC Licnese Date": data.get("sec_license_date", ""),
        "SEC Ops start": data.get("sec_ops_start", ""),
        "BSP License Type": data.get("bsp_license_type", ""),
        "BSP Licnese Date": data.get("bsp_license_date", ""),
        "BSP Ops start": data.get("bsp_ops_start", ""),
        "IC License Type": data.get("ic_license_type", ""),
        "IC Licnese Date": data.get("ic_license_date", ""),
        "IC Ops start": data.get("ic_ops_start", ""),
        "Total Comp (PHP)": data.get("total_compensation", ""),
        "No Officers": data.get("number_officers", ""),
        "No Employees": data.get("number_employees", ""),
        "Total Manpower": data.get("total_manpower", ""),
        "UBO_Name": data.get("ubo_name", ""),
        "UBO_Address": data.get("ubo_address", ""),
        "UBO_Naitonality": data.get("ubo_nationality", ""),
        "UBO_DOB": data.get("ubo_dob", ""),
        "UBO_TIN": data.get("ubo_tin", ""),
        "UBO_% ownership": data.get("ubo_ownership_percentage", ""),
        "UBO_Type": data.get("ubo_type", ""),
        "UBO_Category": data.get("ubo_category", ""),
    })
    
    # Clean null values
    cleaned_mapping = {}
    for field, value in field_mapping.items():
        if value is None or str(value).lower() == "null":
            cleaned_mapping[field] = ""
        else:
            cleaned_mapping[field] = str(value)
    
    return cleaned_mapping

def normalize_value(value: Any) -> str:
    """Normalize values for comparison by handling nulls, case, and whitespace."""
    if value is None:
        return ""
    
    str_value = str(value).strip()
    
    # Handle various null representations
    # if str_value.lower() in ['null', 'n/a', 'na', 'none', '']:
    #     return ""
    
    return str_value

def similarity_score(val1: str, val2: str) -> float:
    """Calculate similarity score between two strings (0.0 to 1.0)."""
    if val1 == val2:
        return 1.0
    return SequenceMatcher(None, val1.lower(), val2.lower()).ratio()

def compare_with_ground_truth(flattened_data: Dict[str, Any], ground_truth_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare flattened JSON data with ground truth values from a DataFrame.
    Handles repeated field names in ground truth by mapping them to numbered JSON fields.
    
    Args:
        flattened_data: Dictionary of flattened JSON field-value pairs
        ground_truth_df: DataFrame with field names and ground truth values (Field column + at least 1 value column)
    
    Returns:
        DataFrame with comparison results including match status and similarity scores
    """
    
    # Ensure the DataFrame has the expected structure
    if 'Field' not in ground_truth_df.columns:
        st.error("Ground truth data must have a 'Field' column")
        return pd.DataFrame()
    
    # Get the first column after 'Field' as ground truth
    value_columns = [col for col in ground_truth_df.columns if col != 'Field']
    if len(value_columns) < 1:
        st.error("Ground truth data must have at least 1 value column (ground truth)")
        return pd.DataFrame()
    
    truth_col = value_columns[0]  # Use first value column as ground truth
    
    comparison_results = []
    
    # Track field name occurrences for mapping to numbered JSON fields
    field_counters = {}
    
    for _, row in ground_truth_df.iterrows():
        field_name = row['Field']
        truth_value = normalize_value(row[truth_col])
        
        # Skip empty rows
        if not field_name or field_name.strip() == "":
            continue
        
        # Count occurrences of this field name for proper mapping
        if field_name not in field_counters:
            field_counters[field_name] = 0
        field_counters[field_name] += 1
        current_count = field_counters[field_name]
        
        # Get corresponding value from flattened JSON
        flattened_value = ""
        
        # Standard field mapping (no numbers)
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
        
        # Add specific field name mappings for common cases
        field_mappings = {
            # Basic company info
            'Document Type': 'document_type',
            'For the year': 'for_the_year',
            'Corporate Name': 'business_trade_name',
            'Business/Trade Name': 'business_trade_name',
            'Date Registered': 'date_registered',
            'Fiscal Year End': 'fiscal_year_end',
            'SEC Registration Number': 'sec_registration_number',
            'Corporate TIN': 'corporate_tin',
            'Website/URL': 'website_url',
            'Principal Office Address': 'principal_office_address',
            'Business Address': 'business_address',
            'Official e-mail address': 'official_email',
            'Alternate Email Address': 'alternate_email',
            'Official Mobile Number': 'official_mobile',
            'Alternate Mobile Number': 'alternate_mobile',
            'Primary Purpose/Industry': 'primary_purpose_industry',
            'Industry Classification': 'industry_classification',
            'Geographical Code': 'geographical_code',
            
            # Parent/Subsidiary info
            'Parent Company Name': 'parent_company_name',
            'Parent Company SEC Reg. No.': 'parent_company_sec_reg_no',
            'Parent Company Address': 'parent_company_address',
            'Subsidiary/Affiliate': 'subsidiary_affiliate',
            'Subsidiary/Affiliate SEC Reg. No.': 'subsidiary_affiliate_sec_reg_no',
            'Subsidiary/Affiliate Address': 'subsidiary_affiliate_address',
            
            # Auditor info
            'External Auditor': 'external_auditor',
            'Auditor SEC Accreditation Number': 'auditor_sec_accreditation_number',
            
            # AML/AMLA info
            'Covered Person (AML)': 'covered_person_aml',
            'AMLA Category 1': 'amla_category_1',
            'AMLA Category 2': 'amla_category_2',
            'AMLA Category 3': 'amla_category_3',
            'AMLA Category 4': 'amla_category_4',
            'AMLA Category 5': 'amla_category_5',
            'AMLA Category 6': 'amla_category_6',
            'AMLA Category 7': 'amla_category_7',
            'AMLA Category 8': 'amla_category_8',
            'AMLA Compliance Status': 'amla_compliance_status',
            
            # Capital structure (specific mappings)
            'Auth Capital Stock - Type of Shares 1': 'auth_capital_stock_type_of_shares_1',
            'Auth Capital Stock - Number of Shares 1': 'auth_capital_stock_number_of_shares_1',
            'Auth Capital Stock - Par / Stated Value 1': 'auth_capital_stock_par_stated_value_1',
            'Auth Capital Stock - Amount (PhP) 1': 'auth_capital_stock_amount_php_1',
            'Authorized Capital Stock': 'auth_capital_stock_amount_php_1',
            
            # Filipino Subscribed Capital
            'Filipino Subscribed Capital - Type of Shares 1': 'filipino_subscribed_capital_type_of_shares_1',
            'Filipino Subscribed Capital - Number of Shares 1': 'filipino_subscribed_capital_number_of_shares_1',
            'Filipino Subscribed Capital - Par / Stated Value 1': 'filipino_subscribed_capital_par_stated_value_1',
            'Filipino Subscribed Capital - Amount (PhP) 1': 'filipino_subscribed_capital_amount_php_1',
            
            # Foreign Subscribed Capital
            'Foreign Subscribed Capital - Type of Shares 1': 'foreign_subscribed_capital_type_of_shares_1',
            'Foreign Subscribed Capital - Number of Shares 1': 'foreign_subscribed_capital_number_of_shares_1',
            'Foreign Subscribed Capital - Par / Stated Value 1': 'foreign_subscribed_capital_par_stated_value_1',
            'Foreign Subscribed Capital - Amount (PhP) 1': 'foreign_subscribed_capital_amount_php_1',
            
            # Filipino Paid-Up Capital
            'Filipino Paid-Up Capital - Type of Shares 1': 'filipino_paid_up_capital_type_of_shares_1',
            'Filipino Paid-up Capital Number of Shares 1': 'filipino_paid_up_capital_number_of_shares_1',
            'Filipino Paid-Up Capital - Par / Stated Value 1': 'filipino_paid_up_capital_par_stated_value_1',
            'Filipino Paid-Up Capital - Amount (PhP) 1': 'filipino_paid_up_capital_amount_php_1',
            
            # Foreign Paid-Up Capital
            'Foreign Paid-Up Capital - Type of Shares 1': 'foreign_paid_up_capital_type_of_shares_1',
            'Foreign Paid-up Capital Number of Shares 1': 'foreign_paid_up_capital_number_of_shares_1',
            'Foreign Paid-Up Capital - Par / Stated Value 1': 'foreign_paid_up_capital_par_stated_value_1',
            'Foreign Paid-Up Capital - Amount (PhP) 1': 'foreign_paid_up_capital_amount_php_1',
            
            # Legacy mappings for backward compatibility
            'Subscribed Capital_Filipino': 'filipino_subscribed_capital_amount_php_1',
            'Subscribed Capital_Foreign': 'foreign_subscribed_capital_amount_php_1',
            'Subscribed Capital_% Foreigh Equity': 'subscribed_capital_foreign_equity_percentage',
            'Subscribed Capital_Total': 'filipino_subscribed_capital_amount_php_1',  # Map to existing field
            'Paid-up Capital_Filipino': 'filipino_paid_up_capital_amount_php_1',
            'Paid-up Capital_Foreign': 'foreign_paid_up_capital_amount_php_1',
            'Paid-up Capital_% Foreigh Equity': 'paid_up_capital_foreign_equity_percentage',
            'Paid-up Capital_% Foreign Equity': 'paid_up_capital_foreign_equity_percentage',
            'Paid-Up Capital_Total': 'filipino_paid_up_capital_amount_php_1',  # Map to existing field
            
            # Director/Officer fields
            'Director/Officer_Name': 'director_officer_name',
            'Director/Officer_Address': 'director_officer_address',
            'Director/Officer_Nationality': 'director_officer_nationality',
            'Director/Officer_INC\'R': 'director_officer_inc_r',
            'Director/Officer_Board': 'director_officer_board',
            'Director/Officer_Gender': 'director_officer_gender',
            'Director/Officer_Stock Holder': 'director_officer_stock_holder',
            'Director/Officer_Officer': 'director_officer_officer',
            'Director/Officer_Exec Comm.': 'director_officer_exec_comm',
            'Director/Officer_TIN': 'director_officer_tin',
            
            # Stockholder info
            'Total Number of Stockholders': 'total_number_stockholders',
            'Number of Stockholders with ≥100 shares': 'number_stockholders_100_plus_shares',
            'Total Assets (Latest Audited FS)': 'total_assets',
            
            # Stockholder details
            'Stockholder_Name': 'stockholder_name',
            'Stockholder_Nationality': 'stockholder_nationality',
            'Stockholder_Address': 'stockholder_address',
            'Stockholder_Total Shares Subscribed_No.': 'stockholder_shares_subscribed_number',
            'Stockholder_Total Shares Subscribed_Amount (PHP)': 'stockholder_shares_subscribed_amount',
            'Stockholder_% of Ownership': 'stockholder_ownership_percentage',
            'Stockholder_Amount Paid (PHP)': 'stockholder_amount_paid',
            'Stockholder_TIN': 'stockholder_tin',
            
            # Financial info - map to existing fields or mark as truly missing
            'Subscribed Capital_Total (PHP) (from Stockholder detail pages)': 'filipino_subscribed_capital_amount_php_1',
            'Paid-Up Capital_Total (PHP) (from Stockholder detail pages)': 'filipino_paid_up_capital_amount_php_1', 
            'Unrestricted Retained Earnings (PHP)': '',  # Truly missing from JSON
            'Prior year Dividends_Cash (PHP)': 'prior_year_dividends_cash',
            'Prior year Dividends_Stock (PHP)': 'prior_year_dividends_stock',
            'Prior year Dividends_Property (PHP)': 'prior_year_dividends_property',
            'Prior year Dividends_Total (PHP)': 'prior_year_dividends_total',
            'Share Issuance_Date': 'share_issuance_date',
            'Share Issuance_No': 'share_issuance_number',
            'Share Issuance_Amount (PHP)': 'share_issuance_amount',
            
            # License info
            'SEC License Type': 'sec_license_type',
            'SEC Licnese Date': 'sec_license_date',
            'SEC Ops start': 'sec_ops_start',
            'BSP License Type': 'bsp_license_type',
            'BSP Licnese Date': 'bsp_license_date',
            'BSP Ops start': 'bsp_ops_start',
            'IC License Type': 'ic_license_type',
            'IC Licnese Date': 'ic_license_date',
            'IC Ops start': 'ic_ops_start',
            
            # Employment/Compensation
            'Total Comp (PHP)': 'total_compensation',
            'No Officers': 'number_officers',
            'No Employees': 'number_employees',
            'Total Manpower': 'total_manpower',
            
            # UBO info
            'UBO_Name': 'ubo_name',
            'UBO_Address': 'ubo_address',
            'UBO_Naitonality': 'ubo_nationality',  # Handle typo in ground truth
            'UBO_DOB': 'ubo_dob',
            'UBO_TIN': 'ubo_tin',
            'UBO_% ownership': 'ubo_ownership_percentage',
            'UBO_Type': 'ubo_type',
            'UBO_Category': 'ubo_category',
            
            # Additional specific mappings for problematic fields
            'Director/Officer_INC\'R': 'director_officer_inc_r',
            'Director/Officer_Exec Comm.': 'director_officer_exec_comm',
            'Stockholder_Total Shares Subscribed_No.': 'stockholder_shares_subscribed_number',
            'Stockholder_Total Shares Subscribed_Amount (PHP)': 'stockholder_shares_subscribed_amount',
            'Stockholder_Amount Paid (PHP)': 'stockholder_amount_paid',
            'Share Issuance_Date': 'share_issuance_date',
            'Share Issuance_No': 'share_issuance_number',
        }
        
        # Check if we have a specific mapping for this field
        if field_name in field_mappings:
            mapped_field = field_mappings[field_name]
            if mapped_field:  # Only add non-empty mappings
                base_transforms.insert(0, mapped_field)
        
        # Add all transformations to possible keys
        possible_keys.extend(base_transforms)
        
        # Remove duplicates while preserving order
        seen = set()
        possible_keys = [x for x in possible_keys if not (x in seen or seen.add(x))]
        
        # Special handling for fields that appear multiple times (Directors/Officers, Stockholders, etc.)
        if field_name.startswith(('Director/Officer', 'Stockholder', 'AMLA Category')):
            # Get the base field mapping first
            if field_name in field_mappings and field_mappings[field_name]:
                base_mapped = field_mappings[field_name]
                numbered_key = f"{base_mapped}_{current_count}"
                possible_keys.insert(0, numbered_key)
            else:
                # Use the most comprehensive transform for numbered fields
                base_key = field_name.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('(', '').replace(')', '').replace('≥', '').replace('.', '').replace("'", '')
                # Map to numbered JSON field based on occurrence count
                numbered_key = f"{base_key}_{current_count}"
                possible_keys.insert(0, numbered_key)
        
        # Special handling for fields that are single entries in JSON but repeated in ground truth
        single_entry_fields = [
            'UBO_', 
            'Corporate Name', 
            'AMLA Compliance Status',
            'Subscribed Capital_Total',
            'Paid-Up Capital_Total',
            'Total Number of Stockholders',
            'Number of Stockholders with ≥100 shares',
            'Total Assets (Latest Audited FS)',
            'Document Type',
            'For the year',
            'Business/Trade Name',
            'Date Registered',
            'Fiscal Year End',
            'SEC Registration Number',
            'Corporate TIN',
            'Website/URL',
            'Principal Office Address',
            'Business Address',
            'Official e-mail address',
            'Alternate Email Address',
            'Official Mobile Number',
            'Alternate Mobile Number',
            'Primary Purpose/Industry',
            'Industry Classification',
            'Geographical Code',
            'Parent Company Name',
            'Parent Company SEC Reg. No.',
            'Parent Company Address',
            'Subsidiary/Affiliate',
            'Subsidiary/Affiliate SEC Reg. No.',
            'Subsidiary/Affiliate Address',
            'External Auditor',
            'Auditor SEC Accreditation Number',
            'Covered Person (AML)'
        ]
        if any(field_name.startswith(prefix) or field_name == prefix for prefix in single_entry_fields) and current_count > 1:
            flattened_value = ""  # These fields beyond first occurrence are empty/missing in JSON
        # Check if field is explicitly marked as missing
        elif field_name in field_mappings and field_mappings[field_name] == '':
            flattened_value = ""  # Explicitly missing
        else:
            # Try to find matching JSON field
            for key in possible_keys:
                if key in flattened_data:
                    flattened_value = normalize_value(flattened_data[key])
                    break
        
        # Calculate similarity score
        flattened_vs_truth = similarity_score(flattened_value, truth_value)
        
        # Determine match status
        exact_match = flattened_value == truth_value
        
        # Overall status
        if exact_match:
            status = "✅ Perfect Match"
        elif flattened_vs_truth > 0.9:
            status = "🟨 Very Close"
        elif flattened_vs_truth > 0.7:
            status = "🟧 Similar"
        elif flattened_value == "":
            status = "❓ Missing in JSON"
        else:
            status = "❌ Mismatch"
        
        # Create display field name with occurrence indicator for repeated fields
        display_field = field_name
        if current_count > 1:
            display_field = f"{field_name} ({current_count})"
        
        comparison_results.append({
            'Field': display_field,
            'JSON Value': flattened_value,
            'Ground Truth': truth_value,
            'Status': status,
            'Similarity Score': f"{flattened_vs_truth:.2%}"
        })
    
    return pd.DataFrame(comparison_results)

def create_comparison_summary(comparison_df: pd.DataFrame) -> Dict[str, Any]:
    """Create a summary of comparison results."""
    if comparison_df.empty:
        return {}
    
    total_fields = len(comparison_df)
    perfect_matches = len(comparison_df[comparison_df['Status'] == '✅ Perfect Match'])
    very_close = len(comparison_df[comparison_df['Status'] == '🟨 Very Close'])
    similar = len(comparison_df[comparison_df['Status'] == '🟧 Similar'])
    missing = len(comparison_df[comparison_df['Status'] == '❓ Missing in JSON'])
    mismatches = len(comparison_df[comparison_df['Status'] == '❌ Mismatch'])
    
    return {
        'total_fields': total_fields,
        'perfect_matches': perfect_matches,
        'very_close': very_close,
        'similar': similar,
        'missing': missing,
        'mismatches': mismatches,
        'accuracy_percentage': (perfect_matches + very_close) / total_fields * 100 if total_fields > 0 else 0
    }

def create_download_files(flattened_data: Dict[str, Any], filename_base: str, sec_gis_data: Dict[str, Any] = None):
    """Create downloadable files in different formats."""
    
    # Debug logging
    print(f"DEBUG: create_download_files called with sec_gis_data: {sec_gis_data is not None}")
    if sec_gis_data:
        print(f"DEBUG: SEC GIS data has {len(sec_gis_data)} fields")
    
    # Create DataFrame for standard flattened data
    df = pd.DataFrame([
        {'Field': format_field_name(field), 'Value': str(value) if value is not None else 'null'}
        for field, value in flattened_data.items()
    ])
    
    # Create DataFrame for SEC GIS format if provided
    sec_gis_df = None
    if sec_gis_data:
        sec_gis_df = pd.DataFrame([
            {'Field': field, 'Value': str(value) if value is not None else ''}
            for field, value in sec_gis_data.items()
        ])
        print(f"DEBUG: SEC GIS DataFrame created with {len(sec_gis_df)} rows")
    
    # TSV content
    tsv_content = df.to_csv(sep='\t', index=False)
    sec_gis_tsv = sec_gis_df.to_csv(sep='\t', index=False) if sec_gis_df is not None else None
    
    # CSV content  
    csv_content = df.to_csv(index=False)
    sec_gis_csv = sec_gis_df.to_csv(index=False) if sec_gis_df is not None else None
    
    # Excel content - with error handling
    excel_content = None
    sec_gis_excel = None
    try:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Flattened_Data', index=False)
            if sec_gis_df is not None:
                sec_gis_df.to_excel(writer, sheet_name='SEC_GIS_Format', index=False)
        excel_content = excel_buffer.getvalue()
        
        if sec_gis_df is not None:
            sec_gis_excel_buffer = io.BytesIO()
            with pd.ExcelWriter(sec_gis_excel_buffer, engine='openpyxl') as writer:
                sec_gis_df.to_excel(writer, sheet_name='SEC_GIS_Format', index=False)
            sec_gis_excel = sec_gis_excel_buffer.getvalue()
            print("DEBUG: SEC GIS Excel created successfully")
            
    except ImportError:
        # If openpyxl is not available, create a simple Excel-compatible CSV
        excel_content = csv_content.encode('utf-8')
        sec_gis_excel = sec_gis_csv.encode('utf-8') if sec_gis_csv else None
        print("DEBUG: Using fallback Excel format (CSV)")
    
    # JSON content (flattened)
    json_content = json.dumps({
        format_field_name(field): value for field, value in flattened_data.items()
    }, indent=2, ensure_ascii=False)
    
    result = {
        'tsv': tsv_content,
        'csv': csv_content, 
        'excel': excel_content,
        'json': json_content,
        'dataframe': df
    }
    
    # Add SEC GIS formats if available
    if sec_gis_data and sec_gis_df is not None:
        result.update({
            'sec_gis_tsv': sec_gis_tsv,
            'sec_gis_csv': sec_gis_csv,
            'sec_gis_excel': sec_gis_excel,
            'sec_gis_dataframe': sec_gis_df
        })
        print(f"DEBUG: Added SEC GIS data to result. Keys: {list(result.keys())}")
    else:
        print("DEBUG: No SEC GIS data added to result")
    
    return result

def main():
    """Main Streamlit app."""
    
    # Title and description
    st.title("📊 GIS JSON Flattener")
    st.markdown("Convert nested JSON data (including arrays and objects) into flat spreadsheet format")
    
    # Check for missing dependencies
    try:
        import openpyxl
        excel_available = True
    except ImportError:
        excel_available = False
        st.warning("⚠️ Excel export requires openpyxl. Add 'openpyxl>=3.1.0' to requirements.txt for full functionality. TSV and CSV work perfectly!")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        1. **Upload JSON file** or paste JSON text
        2. **Preview** the structure analysis
        3. **Click Copy** to copy to clipboard
        4. **Download** files in your preferred format
        
        **Supported formats:**
        - 📝 TSV (Tab-separated)
        - 📄 CSV (Comma-separated) 
        - 📊 Excel (.xlsx)
        - 🔧 JSON (flattened)
        """)
        
        st.header("🔍 Features")
        st.markdown("""
        ✅ **Arrays extraction** - Each array item becomes a separate row  
        ✅ **Nested objects** - Flattened with dot notation  
        ✅ **Multiple formats** - TSV, CSV, Excel, JSON  
        ✅ **Structure analysis** - Shows what was found  
        ✅ **Batch processing** - Upload multiple files
        ✅ **Copy to clipboard** - Easy copying of results
        ✅ **SEC GIS format** - Philippine SEC compliance format
        """)
        
        st.header("🏢 SEC GIS Format")
        st.markdown("""
        **Automatic Detection**: If your JSON contains Philippine corporate data, the app will:
        - 🔍 **Auto-detect** SEC GIS structure
        - 📋 **Map fields** to proper SEC format
        - 🏛️ **Generate compliant** output for SEC filing
        
        **Perfect for**: Philippine corporations, SEC compliance, GIS filing
        """)
        
        st.header("💡 One-Click Copy")
        st.markdown("""
        🚀 **True One-Click Copy**:
        - Click any copy button once
        - Data is **automatically copied** to your clipboard
        - Paste anywhere with **Ctrl+V** (or **Cmd+V**)
        
        **For Excel**: Use **📝 Copy TSV** - creates perfect columns!
        
        **Fallback**: If automatic copy fails, a text box will appear for manual copying.
        """)
    
    # Main content area
    tab1, tab2 = st.tabs(["✏️ Paste JSON", "🔍 Compare with Ground Truth"])

    with tab1:
        st.header("Paste JSON Text")
        
        json_text = st.text_area(
            "Paste your JSON here:",
            height=300,
            placeholder='{"example": "data", "array": [1, 2, 3], "nested": {"key": "value"}}'
        )
        
        if json_text.strip():
            try:
                # Validate JSON
                json_data = json.loads(json_text)
                st.success("✅ Valid JSON detected")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    analysis = analyze_json_structure(json_data)
                    st.metric("Arrays", len(analysis['arrays']))
                    st.metric("Nested Objects", len(analysis['nested_objects']))
                    st.metric("Fields", analysis['primitive_fields'])
                
                with col2:
                    if st.button("🚀 Flatten Pasted JSON", type="primary"):
                        flattened = flatten_json_data(json_data)
                        
                        # Check if this looks like SEC GIS data
                        sec_gis_data = None
                        if any(key in json_data for key in ['corporate_name', 'sec_registration_number', 'director_officer_name_1', 'business_trade_name', 'document_type']):
                            sec_gis_data = map_sec_gis_fields(json_data)
                            st.info("🏢 SEC GIS format detected! Philippine SEC format available.")
                        
                        files = create_download_files(flattened, "pasted_json", sec_gis_data)
                        
                        st.success(f"✅ Flattened into **{len(flattened)} fields**")
                        if sec_gis_data:
                            st.success(f"📋 SEC GIS format: **{len(sec_gis_data)} Philippine SEC fields**")
                        
                        # Format selector for pasted JSON
                        if sec_gis_data:
                            format_choice = st.radio(
                                "Choose format:",
                                ["📊 Standard Flattened", "🏢 SEC GIS Format"],
                                horizontal=True,
                                index=1,  # Default to SEC GIS Format
                                key="paste_format"
                            )
                            
                            # Determine which data to use
                            if format_choice == "🏢 SEC GIS Format":
                                active_tsv = files['sec_gis_tsv']
                                active_csv = files['sec_gis_csv']
                                active_df = files['sec_gis_dataframe']
                                format_name = "SEC GIS"
                            else:
                                active_tsv = files['tsv']
                                active_csv = files['csv']
                                active_df = files['dataframe']
                                format_name = "Standard"
                        else:
                            active_tsv = files['tsv']
                            active_csv = files['csv']
                            active_df = files['dataframe']
                            format_name = "Standard"
                        
                        # Show preview and copy options
                        st.dataframe(active_df.head(10), use_container_width=True)
                        
                        # One-click copy for pasted JSON
                        st.write(f"**📋 One-Click Copy ({format_name}):**")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            tsv_component = create_clipboard_component(
                                active_tsv,
                                "📝 Copy",
                                f"{format_name} Copied!"
                            )
                            components.html(tsv_component, height=70)
                            
                            
                        
                        # Download options
                        st.write(f"**💾 Download Options ({format_name}):**")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.download_button(
                                label="📝 TSV",
                                data=active_tsv,
                                file_name=f"pasted_json_{format_name.lower()}_flattened.tsv"
                            )
                        
                        with col2:
                            st.download_button(
                                label="📄 CSV",
                                data=active_csv, 
                                file_name=f"pasted_json_{format_name.lower()}_flattened.csv"
                            )
                        
                        with col3:
                            if sec_gis_data and files.get('sec_gis_excel'):
                                try:
                                    excel_data = files['sec_gis_excel'] if format_name == "SEC GIS" else files['excel']
                                    if excel_data and len(excel_data) > len(active_csv):
                                        st.download_button(
                                            label="📊 Excel",
                                            data=excel_data,
                                            file_name=f"pasted_json_{format_name.lower()}_flattened.xlsx"
                                        )
                                    else:
                                        st.download_button(
                                            label="📊 CSV (Excel)",
                                            data=active_csv,
                                            file_name=f"pasted_json_{format_name.lower()}_flattened.csv",
                                            help="Excel format not available"
                                        )
                                except:
                                    st.download_button(
                                        label="📊 CSV (Excel)",
                                        data=active_csv,
                                        file_name=f"pasted_json_{format_name.lower()}_flattened.csv",
                                        help="Excel format not available"
                                    )
                            else:
                                st.download_button(
                                    label="📊 CSV (Excel)",
                                    data=active_csv,
                                    file_name=f"pasted_json_{format_name.lower()}_flattened.csv"
                                )
                            
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}")
    
    with tab2:
        st.header("🔍 Compare JSON with Ground Truth")
        st.markdown("Upload your JSON data and ground truth table to compare values and identify discrepancies.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📤 Upload JSON Data")
            json_file = st.file_uploader(
                "Choose JSON file to compare:",
                type=['json'],
                key="compare_json",
                help="Upload the JSON file you want to compare against ground truth"
            )
            
            json_text = st.text_area(
                "Or paste your JSON here:",
                height=200,
                placeholder='{"document_type": "GIS", "corporate_name": "BOOST TECHNOLOGIES INC.", "for_the_year": "2024"}',
                key="compare_json_text",
                help="Paste JSON data directly for comparison"
            )
            
            json_data = None
            flattened_json = None
            
            if json_file:
                try:
                    json_content = json_file.read().decode('utf-8')
                    json_data = json.loads(json_content)
                    flattened_json = flatten_json_data(json_data)
                    
                    st.success(f"✅ JSON loaded: {len(flattened_json)} fields")
                    
                    # Show a preview of JSON fields
                    with st.expander("Preview JSON fields"):
                        preview_fields = dict(list(flattened_json.items())[:10])
                        st.json(preview_fields)
                        if len(flattened_json) > 10:
                            st.caption(f"Showing first 10 fields. Total: {len(flattened_json)} fields.")
                    
                except Exception as e:
                    st.error(f"❌ Error loading JSON: {e}")
            
            elif json_text.strip():
                try:
                    json_data = json.loads(json_text)
                    flattened_json = flatten_json_data(json_data)
                    
                    st.success(f"✅ JSON parsed: {len(flattened_json)} fields")
                    
                    # Show a preview of JSON fields
                    with st.expander("Preview JSON fields"):
                        preview_fields = dict(list(flattened_json.items())[:10])
                        st.json(preview_fields)
                        if len(flattened_json) > 10:
                            st.caption(f"Showing first 10 fields. Total: {len(flattened_json)} fields.")
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ Invalid JSON: {e}")
                except Exception as e:
                    st.error(f"❌ Error parsing JSON: {e}")
        
        with col2:
            st.subheader("📊 Upload Ground Truth Table")
            ground_truth_file = st.file_uploader(
                "Choose ground truth file:",
                type=['csv', 'xlsx', 'tsv'],
                key="compare_ground_truth",
                help="Upload CSV, Excel, or TSV file with 'Field' and ground truth columns"
            )
            
            ground_truth_text = st.text_area(
                "Or paste ground truth data:",
                height=200,
                placeholder="Field\tGround Truth\nDocument Type\tGeneral Information Sheet (GIS)\nFor the year\t2024\nCorporate Name\tBOOST TECHNOLOGIES INC.",
                help="Tab-separated format: Field, Ground Truth"
            )
            
            ground_truth_df = None
            
            if ground_truth_file:
                try:
                    if ground_truth_file.name.endswith('.csv'):
                        ground_truth_df = pd.read_csv(ground_truth_file)
                    elif ground_truth_file.name.endswith('.xlsx'):
                        ground_truth_df = pd.read_excel(ground_truth_file)
                    elif ground_truth_file.name.endswith('.tsv'):
                        ground_truth_df = pd.read_csv(ground_truth_file, sep='\t')
                    
                    st.success(f"✅ Ground truth loaded: {len(ground_truth_df)} rows")
                    st.dataframe(ground_truth_df.head(), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"❌ Error loading ground truth: {e}")
            
            elif ground_truth_text.strip():
                try:
                    from io import StringIO
                    ground_truth_df = pd.read_csv(StringIO(ground_truth_text), sep='\t')
                    st.success(f"✅ Ground truth parsed: {len(ground_truth_df)} rows")
                    st.dataframe(ground_truth_df.head(), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"❌ Error parsing ground truth: {e}")
        
        # Perform comparison if both files are loaded
        if json_data is not None and flattened_json is not None and ground_truth_df is not None and not ground_truth_df.empty:
            st.markdown("---")
            st.subheader("🎯 Comparison Results")
            
            if st.button("🚀 Compare Data", type="primary", key="compare_button"):
                with st.spinner("Comparing JSON data with ground truth..."):
                    
                    # Perform comparison
                    comparison_df = compare_with_ground_truth(flattened_json, ground_truth_df)
                    
                    if not comparison_df.empty:
                        # Create summary
                        summary = create_comparison_summary(comparison_df)
                        
                        # Display summary metrics
                        st.subheader("📈 Comparison Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Fields", summary['total_fields'])
                        with col2:
                            st.metric("Perfect Matches", summary['perfect_matches'], 
                                     delta=f"{summary['perfect_matches']}/{summary['total_fields']}")
                        with col3:
                            st.metric("Accuracy", f"{summary['accuracy_percentage']:.1f}%")
                        with col4:
                            st.metric("Issues Found", summary['mismatches'] + summary['missing'])
                        
                        # Status breakdown
                        st.subheader("📊 Status Breakdown")
                        status_col1, status_col2, status_col3 = st.columns(3)
                        
                        with status_col1:
                            st.metric("✅ Perfect Match", summary['perfect_matches'])
                            st.metric("🟨 Very Close", summary['very_close'])
                        with status_col2:
                            st.metric("🟧 Similar", summary['similar'])
                            st.metric("❓ Missing in JSON", summary['missing'])
                        with status_col3:
                            st.metric("❌ Mismatch", summary['mismatches'])
                        
                        # Detailed comparison table
                        st.subheader("📋 Detailed Comparison")
                        
                        # Filter options
                        filter_col1, filter_col2 = st.columns(2)
                        
                        with filter_col1:
                            status_filter = st.selectbox(
                                "Filter by status:",
                                ["All", "✅ Perfect Match", "🟨 Very Close", "🟧 Similar", "❓ Missing in JSON", "❌ Mismatch"],
                                key="status_filter"
                            )
                        
                        with filter_col2:
                            show_all_columns = st.checkbox("Show all columns", value=False, key="show_all_cols")
                        
                        # Apply filter
                        filtered_df = comparison_df.copy()
                        if status_filter != "All":
                            filtered_df = filtered_df[filtered_df['Status'] == status_filter]
                        
                        # Select columns to display
                        if show_all_columns:
                            display_df = filtered_df
                        else:
                            display_df = filtered_df[['Field', 'JSON Value', 'Ground Truth', 'Status', 'Similarity Score']]
                        
                        # Display the comparison table
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            height=400
                        )
                        
                        st.caption(f"Showing {len(filtered_df)} of {len(comparison_df)} fields")
                        
                        # Download comparison results
                        st.subheader("⬇️ Download Comparison Results")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            csv_data = comparison_df.to_csv(index=False)
                            st.download_button(
                                label="📄 Download CSV",
                                data=csv_data,
                                file_name=f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            try:
                                excel_buffer = io.BytesIO()
                                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                    comparison_df.to_excel(writer, sheet_name='Comparison_Results', index=False)
                                excel_data = excel_buffer.getvalue()
                                
                                st.download_button(
                                    label="📊 Download Excel",
                                    data=excel_data,
                                    file_name=f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            except:
                                st.download_button(
                                    label="📊 Download CSV (Excel)",
                                    data=csv_data,
                                    file_name=f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv",
                                    help="Excel format not available"
                                )
                        
                        with col3:
                            # Copy to clipboard functionality
                            tsv_data = comparison_df.to_csv(sep='\t', index=False)
                            copy_component = create_clipboard_component(
                                tsv_data,
                                "📝 Copy TSV",
                                "Comparison copied!"
                            )
                            components.html(copy_component, height=70)
                        
                        # Insights and recommendations
                        st.subheader("💡 Insights & Recommendations")
                        
                        if summary['accuracy_percentage'] >= 90:
                            st.success("🎉 **Excellent accuracy!** Your JSON data closely matches the ground truth.")
                        elif summary['accuracy_percentage'] >= 75:
                            st.warning("⚠️ **Good accuracy** but some discrepancies found. Review mismatched fields.")
                        else:
                            st.error("❌ **Low accuracy detected.** Significant discrepancies found between JSON and ground truth.")
                        
                        if summary['missing'] > 0:
                            st.info(f"ℹ️ **{summary['missing']} fields missing** from your JSON data. Consider adding these fields.")
                        
                        if summary['mismatches'] > 0:
                            st.info(f"ℹ️ **{summary['mismatches']} fields have significant differences.** Review these for data quality issues.")

if __name__ == "__main__":
    main()