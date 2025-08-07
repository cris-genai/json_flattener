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
    page_title="JSON Flattener",
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

def create_download_files(flattened_data: Dict[str, Any], filename_base: str):
    """Create downloadable files in different formats."""
    
    # Create DataFrame
    df = pd.DataFrame([
        {'Field': format_field_name(field), 'Value': str(value) if value is not None else 'null'}
        for field, value in flattened_data.items()
    ])
    
    # TSV content
    tsv_content = df.to_csv(sep='\t', index=False)
    
    # CSV content  
    csv_content = df.to_csv(index=False)
    
    # Excel content - with error handling
    excel_content = None
    try:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Flattened_Data', index=False)
        excel_content = excel_buffer.getvalue()
    except ImportError:
        # If openpyxl is not available, create a simple Excel-compatible CSV
        excel_content = csv_content.encode('utf-8')
    
    # JSON content (flattened)
    json_content = json.dumps({
        format_field_name(field): value for field, value in flattened_data.items()
    }, indent=2, ensure_ascii=False)
    
    return {
        'tsv': tsv_content,
        'csv': csv_content, 
        'excel': excel_content,
        'json': json_content,
        'dataframe': df
    }

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
                            
                            # Create download files
                            files = create_download_files(flattened, uploaded_file.name.replace('.json', ''))
                            
                            st.success(f"✅ Flattened into **{len(flattened)} fields**")
                            
                            # Store in session state
                            st.session_state['flattened_data'] = flattened
                            st.session_state['files'] = files
                            st.session_state['filename'] = uploaded_file.name
                
                # Show results if available
                if 'flattened_data' in st.session_state and 'files' in st.session_state:
                    st.subheader("📄 Results")
                    
                    # Preview
                    df = st.session_state['files']['dataframe']
                    st.dataframe(df.head(20), use_container_width=True)
                    
                    if len(df) > 20:
                        st.info(f"Showing first 20 rows. Total: {len(df)} rows")
                    
                    # Download and Copy Options
                    st.subheader("⬇️ Download & Copy Options")
                    
                    files = st.session_state['files']
                    base_filename = st.session_state['filename'].replace('.json', '')
                    
                    # One-click copy buttons
                    st.write("**📋 One-Click Copy to Clipboard:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # TSV Copy Button
                        st.write("**📝 TSV Format (Perfect for Excel):**")
                        tsv_component = create_clipboard_component(
                            files['tsv'], 
                            "📝 Copy", 
                            "Copied to clipboard!"
                        )
                        components.html(tsv_component, height=70)
                        
                        st.write("")
                        
                        
                    st.write("---")  # Divider
                    
                    # Preview section
                    st.subheader("👀 Preview Data")
                    with st.expander("Preview flattened data", expanded=False):
                        st.dataframe(files['dataframe'], use_container_width=True)
                    
                    # Download buttons section
                    st.write("**💾 Download Files:**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.download_button(
                            label="📝 Download TSV",
                            data=files['tsv'],
                            file_name=f"{base_filename}_flattened.tsv",
                            mime="text/tab-separated-values"
                        )
                    
                    with col2:
                        st.download_button(
                            label="📄 Download CSV", 
                            data=files['csv'],
                            file_name=f"{base_filename}_flattened.csv",
                            mime="text/csv"
                        )
                    
                    with col3:
                        try:
                            if files['excel']:
                                st.download_button(
                                    label="📊 Download Excel",
                                    data=files['excel'],
                                    file_name=f"{base_filename}_flattened.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            else:
                                st.download_button(
                                    label="📊 Download CSV (Excel)",
                                    data=files['csv'],
                                    file_name=f"{base_filename}_flattened.csv",
                                    mime="text/csv",
                                    help="Excel format not available - downloading as CSV"
                                )
                        except:
                            st.download_button(
                                label="📊 Download CSV (Excel)",
                                data=files['csv'],
                                file_name=f"{base_filename}_flattened.csv",
                                mime="text/csv",
                                help="Excel format not available - downloading as CSV"
                            )
                    
                    with col4:
                        st.download_button(
                            label="🔧 Download JSON",
                            data=files['json'],
                            file_name=f"{base_filename}_flattened.json", 
                            mime="application/json"
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
                        files = create_download_files(flattened, "pasted_json")
                        
                        st.success(f"✅ Flattened into **{len(flattened)} fields**")
                        
                        # Show preview and copy options
                        st.dataframe(files['dataframe'].head(10), use_container_width=True)
                        
                        # One-click copy for pasted JSON
                        st.write("**📋 One-Click Copy:**")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            tsv_component = create_clipboard_component(
                                files['tsv'],
                                "📝 Copy",
                                "Copied!"
                            )
                            components.html(tsv_component, height=70)
                            
                        # Download options
                        st.write("**💾 Download Options:**")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.download_button(
                                label="📝 TSV",
                                data=files['tsv'],
                                file_name="pasted_json_flattened.tsv"
                            )
                        
                        with col2:
                            st.download_button(
                                label="📄 CSV",
                                data=files['csv'], 
                                file_name="pasted_json_flattened.csv"
                            )
                        
                        with col3:
                            try:
                                if files['excel'] and len(files['excel']) > len(files['csv']):
                                    st.download_button(
                                        label="📊 Excel",
                                        data=files['excel'],
                                        file_name="pasted_json_flattened.xlsx"
                                    )
                                else:
                                    st.download_button(
                                        label="📊 CSV (Excel)",
                                        data=files['csv'],
                                        file_name="pasted_json_flattened.csv",
                                        help="Excel format not available - downloading as CSV"
                                    )
                            except:
                                st.download_button(
                                    label="📊 CSV (Excel)",
                                    data=files['csv'],
                                    file_name="pasted_json_flattened.csv",
                                    help="Excel format not available"
                                )
                            
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}")

if __name__ == "__main__":
    main()
