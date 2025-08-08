import streamlit as st
import json
import pandas as pd
import io
from typing import Any, Dict, Union
import zipfile
from datetime import datetime
import streamlit.components.v1 as components

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
        "Corporate Name": data.get("corporate_name", ""),
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
        "Corporate Name": data.get("corporate_name", ""),
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
    st.title("📊 JSON Flattener")
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
    tab1, tab2, tab3 = st.tabs(["📤 Single Upload", "📁 Batch Upload", "✏️ Paste JSON"])
    
    with tab1:
        st.header("Upload Single JSON File")
        
        uploaded_file = st.file_uploader(
            "Choose a JSON file",
            type=['json'],
            help="Upload a .json file to flatten its structure"
        )
        
        if uploaded_file is not None:
            try:
                # Read the file
                content = uploaded_file.read().decode('utf-8')
                json_data = json.loads(content)
                
                # Display file info
                st.success(f"✅ Successfully loaded: **{uploaded_file.name}**")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("📊 Structure Analysis")
                    analysis = analyze_json_structure(json_data)
                    
                    st.metric("Arrays Found", len(analysis['arrays']))
                    st.metric("Nested Objects", len(analysis['nested_objects']))
                    st.metric("Primitive Fields", analysis['primitive_fields'])
                    
                    if analysis['arrays']:
                        st.write("**Arrays detected:**")
                        for arr in analysis['arrays'][:5]:  # Show first 5
                            st.write(f"• `{arr['path']}` ({arr['length']} items)")
                        if len(analysis['arrays']) > 5:
                            st.write(f"... and {len(analysis['arrays'])-5} more")
                
                with col2:
                    st.subheader("🔧 Processing")
                    
                    if st.button("🚀 Flatten JSON", type="primary"):
                        with st.spinner("Flattening JSON data..."):
                            # Flatten the data
                            flattened = flatten_json_data(json_data)
                            
                            # Check if this looks like SEC GIS data
                            sec_gis_data = None
                            detection_keys = ['corporate_name', 'sec_registration_number', 'director_officer_name_1', 'business_trade_name', 'document_type']
                            found_keys = [key for key in detection_keys if key in json_data]
                            
                            st.write(f"**DEBUG**: Looking for SEC GIS keys: {detection_keys}")
                            st.write(f"**DEBUG**: Found keys in JSON: {found_keys}")
                            st.write(f"**DEBUG**: All JSON keys: {list(json_data.keys())}")
                            
                            if found_keys:
                                st.info(f"🏢 SEC GIS detection successful! Found keys: {found_keys}")
                                sec_gis_data = map_sec_gis_fields(json_data)
                                st.write(f"**DEBUG**: SEC GIS data generated with {len(sec_gis_data)} fields")
                                
                                # Show first few SEC GIS fields for debugging
                                with st.expander("**DEBUG**: View first 5 SEC GIS fields"):
                                    first_5 = dict(list(sec_gis_data.items())[:5])
                                    for k, v in first_5.items():
                                        st.write(f"- **{k}**: {v}")
                            else:
                                st.write("**DEBUG**: No SEC GIS detection keys found - using standard format only")
                            # Create download files
                            files = create_download_files(flattened, uploaded_file.name.replace('.json', ''), sec_gis_data)
                            
                            st.write(f"**DEBUG**: Files dict keys: {list(files.keys())}")
                            
                            st.success(f"✅ Flattened into **{len(flattened)} fields**")
                            if sec_gis_data:
                                st.success(f"📋 SEC GIS format: **{len(sec_gis_data)} Philippine SEC fields**")
                                # Debug check
                                if 'sec_gis_tsv' in files:
                                    st.write("**DEBUG**: SEC GIS TSV data created successfully")
                                    st.write(f"**DEBUG**: SEC GIS TSV length: {len(files['sec_gis_tsv']) if files['sec_gis_tsv'] else 0}")
                                else:
                                    st.error("**DEBUG**: SEC GIS TSV data not found in files")
                            
                            # Store in session state
                            st.session_state['flattened_data'] = flattened
                            st.session_state['sec_gis_data'] = sec_gis_data
                            st.session_state['files'] = files
                            st.session_state['filename'] = uploaded_file.name
                
                # Show results if available
                if 'flattened_data' in st.session_state and 'files' in st.session_state:
                    st.subheader("📄 Results")
                    
                    files = st.session_state['files']
                    base_filename = st.session_state['filename'].replace('.json', '')
                    sec_gis_data = st.session_state.get('sec_gis_data')
                    
                    # Format Selection - Simple approach without complex state management
                    if sec_gis_data and 'sec_gis_tsv' in files and files['sec_gis_tsv']:
                        st.info("🏢 SEC GIS format detected! Choose your preferred format:")
                        
                        # Simple radio selection - default to SEC GIS format
                        format_choice = st.radio(
                            "Choose format:",
                            ["📊 Standard Format", "🏢 SEC GIS Format"],
                            horizontal=True,
                            index=1  # Default to SEC GIS Format (index 1)
                        )
                        
                        # Set active data based on current selection (no session state needed)
                        if format_choice == "🏢 SEC GIS Format":
                            active_tsv = files['sec_gis_tsv']
                            active_csv = files['sec_gis_csv'] 
                            active_excel = files['sec_gis_excel']
                            active_df = files['sec_gis_dataframe']
                            format_desc = "SEC GIS"
                            st.success("✅ **SEC GIS Format Active** - Philippine SEC compliance ready!")
                        else:
                            active_tsv = files['tsv']
                            active_csv = files['csv']
                            active_excel = files['excel']
                            active_df = files['dataframe']
                            format_desc = "Standard"
                            st.info("ℹ️ **Standard Format Active** - Technical JSON field names")
                    else:
                        # No SEC GIS data available, use standard format only
                        active_tsv = files['tsv']
                        active_csv = files['csv']
                        active_excel = files['excel']
                        active_df = files['dataframe']
                        format_desc = "Standard"
                        st.info("ℹ️ **Standard Format** - No SEC GIS data detected")
                    
                    # Show current format metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Fields", len(active_df))
                    with col2:
                        st.metric("Current Format", format_desc)
                    with col3:
                        if format_desc == "SEC GIS":
                            st.metric("Compliance", "Philippine SEC ✓")
                        else:
                            st.metric("Type", "Technical")
                    
                    # Preview
                    st.write(f"**📋 Preview ({format_desc} Format):**")
                    st.dataframe(active_df.head(10), use_container_width=True)
                    
                    if len(active_df) > 10:
                        st.caption(f"Showing first 10 rows. Total: {len(active_df)} rows")
                    
                    # Show field name examples
                    if sec_gis_data:
                        with st.expander("🔍 Compare field name formats"):
                            ex_col1, ex_col2 = st.columns(2)
                            with ex_col1:
                                st.write("**📊 Standard Format:**")
                                st.code("corporate_name")
                                st.code("directors_officers_0_name") 
                                st.code("sec_registration_number")
                            with ex_col2:
                                st.write("**🏢 SEC GIS Format:**")
                                st.code("Corporate Name")
                                st.code("Director/Officer 1 Name")
                                st.code("SEC Registration Number")
                    
                    # Download and Copy Options
                    st.subheader(f"⬇️ Download & Copy Options - {format_desc} Format")
                    
                    # One-click copy buttons
                    st.write("**📋 One-Click Copy to Clipboard:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # TSV Copy Button
                        st.write("**📝 TSV Format (Perfect for Excel):**")
                        tsv_component = create_clipboard_component(
                            active_tsv, 
                            "📝 Copy TSV", 
                            f"{format_desc} TSV copied to clipboard!"
                        )
                        components.html(tsv_component, height=70)
                        
                        st.write("")
                        
                        # Table Copy Button
                        st.write("**📊 Formatted Table:**")
                        table_text = active_df.to_string(index=False, max_colwidth=60)
                        table_component = create_clipboard_component(
                            table_text,
                            "📊 Copy Table",
                            f"{format_desc} table copied to clipboard!"
                        )
                        components.html(table_component, height=70)
                    
                    with col2:
                        # CSV Copy Button
                        st.write("**📄 CSV Format:**")
                        csv_component = create_clipboard_component(
                            active_csv,
                            "📄 Copy CSV",
                            f"{format_desc} CSV copied to clipboard!"
                        )
                        components.html(csv_component, height=70)
                        
                        st.write("")
                        
                        # JSON Copy Button (only for standard format)
                        if format_desc == "Standard" or format_desc == "Standard (Fallback)":
                            st.write("**🔧 Flattened JSON:**")
                            json_component = create_clipboard_component(
                                files['json'],
                                "🔧 Copy JSON",
                                "JSON copied to clipboard!"
                            )
                            components.html(json_component, height=70)
                        else:
                            st.write("**🏢 SEC GIS Benefits:**")
                            st.success("✓ Philippine SEC compliant field names")
                    
                    st.write("---")  # Divider
                    
                    # Download buttons section
                    st.write(f"**💾 Download Files ({format_desc} Format):**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    suffix = "_sec_gis" if format_desc == "SEC GIS" else ""
                    
                    with col1:
                        st.download_button(
                            label="📝 Download TSV",
                            data=active_tsv,
                            file_name=f"{base_filename}{suffix}_flattened.tsv",
                            mime="text/tab-separated-values"
                        )
                    
                    with col2:
                        st.download_button(
                            label="📄 Download CSV", 
                            data=active_csv,
                            file_name=f"{base_filename}{suffix}_flattened.csv",
                            mime="text/csv"
                        )
                    
                    with col3:
                        try:
                            if active_excel:
                                st.download_button(
                                    label="📊 Download Excel",
                                    data=active_excel,
                                    file_name=f"{base_filename}{suffix}_flattened.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            else:
                                st.download_button(
                                    label="📊 Download CSV (Excel)",
                                    data=active_csv,
                                    file_name=f"{base_filename}{suffix}_flattened.csv",
                                    mime="text/csv",
                                    help="Excel format not available - downloading as CSV"
                                )
                        except:
                            st.download_button(
                                label="📊 Download CSV (Excel)",
                                data=active_csv,
                                file_name=f"{base_filename}{suffix}_flattened.csv",
                                mime="text/csv",
                                help="Excel format not available - downloading as CSV"
                            )
                    
                    with col4:
                        if format_desc == "Standard" or format_desc == "Standard (Fallback)":
                            st.download_button(
                                label="🔧 Download JSON",
                                data=files['json'],
                                file_name=f"{base_filename}_flattened.json", 
                                mime="application/json"
                            )
                        else:
                            st.download_button(
                                label="🏢 Both Formats",
                                data=files['excel'] if files.get('excel') else files['csv'].encode('utf-8'),
                                file_name=f"{base_filename}_both_formats.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                help="Downloads both standard and SEC GIS formats in one Excel file"
                            )
                        
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON file: {e}")
            except Exception as e:
                st.error(f"❌ Error processing file: {e}")
    
    with tab2:
        st.header("Batch Upload Multiple JSON Files")
        
        uploaded_files = st.file_uploader(
            "Choose multiple JSON files",
            type=['json'],
            accept_multiple_files=True,
            help="Upload multiple .json files to process them all at once"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} files uploaded")
            
            if st.button("🚀 Process All Files", type="primary"):
                progress_bar = st.progress(0)
                results = []
                
                for i, file in enumerate(uploaded_files):
                    try:
                        content = file.read().decode('utf-8')
                        json_data = json.loads(content)
                        flattened = flatten_json_data(json_data)
                        
                        results.append({
                            'filename': file.name,
                            'flattened_data': flattened,
                            'status': 'success',
                            'fields_count': len(flattened)
                        })
                        
                    except Exception as e:
                        results.append({
                            'filename': file.name,
                            'status': 'error',
                            'error': str(e)
                        })
                    
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                # Show results summary
                st.subheader("📊 Processing Results")
                
                success_count = sum(1 for r in results if r['status'] == 'success')
                error_count = len(results) - success_count
                
                col1, col2 = st.columns(2)
                col1.metric("✅ Successful", success_count)
                col2.metric("❌ Errors", error_count)
                
                # Create batch download
                if success_count > 0:
                    st.subheader("⬇️ Download All Results")
                    
                    # Create ZIP file with all results
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for result in results:
                            if result['status'] == 'success':
                                base_name = result['filename'].replace('.json', '')
                                files = create_download_files(result['flattened_data'], base_name)
                                
                                # Add files to ZIP
                                zip_file.writestr(f"{base_name}_flattened.csv", files['csv'])
                                zip_file.writestr(f"{base_name}_flattened.tsv", files['tsv'])
                                zip_file.writestr(f"{base_name}_flattened.json", files['json'])
                    
                    zip_buffer.seek(0)
                    
                    st.download_button(
                        label="📦 Download All (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"flattened_json_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip"
                    )
                
                # Show detailed results
                if error_count > 0:
                    with st.expander("❌ View Errors"):
                        for result in results:
                            if result['status'] == 'error':
                                st.error(f"**{result['filename']}**: {result['error']}")
    
    with tab3:
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
                                "📝 Copy TSV",
                                f"{format_name} TSV copied!"
                            )
                            components.html(tsv_component, height=70)
                            
                            table_text = active_df.to_string(index=False, max_colwidth=50)
                            table_component = create_clipboard_component(
                                table_text,
                                "📊 Copy Table", 
                                f"{format_name} table copied!"
                            )
                            components.html(table_component, height=70)
                        
                        with col2:
                            csv_component = create_clipboard_component(
                                active_csv,
                                "📄 Copy CSV",
                                f"{format_name} CSV copied!"
                            )
                            components.html(csv_component, height=70)
                            
                            if format_name == "Standard":
                                json_component = create_clipboard_component(
                                    files['json'],
                                    "🔧 Copy JSON",
                                    "JSON copied!"
                                )
                                components.html(json_component, height=70)
                            else:
                                st.info("🏢 SEC GIS format for Philippine compliance")
                        
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

if __name__ == "__main__":
    main()