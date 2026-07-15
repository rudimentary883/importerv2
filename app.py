from flask import Flask, request, jsonify
import pandas as pd
import requests
import re
import os
import json

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Your Calico credentials
TABBYCAT_URL = "https://17thvmdc.calicotab.com"
TABBYCAT_TOKEN = "30d6f2baab6409983fe6eb6d0ebdde40e391bd60"

HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

def discover_api_endpoint():
    """Try different API endpoint formats to find the right one"""
    endpoints = [
        f"{TABBYCAT_URL}/api/v1/institutions/",
        f"{TABBYCAT_URL}/api/institutions/",
        f"{TABBYCAT_URL}/institutions/api/",
        f"{TABBYCAT_URL}/api/v1/institutions",
        f"{TABBYCAT_URL}/api/institutions",
        f"{TABBYCAT_URL}/api/v1/",
        f"{TABBYCAT_URL}/api/",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=HEADERS, timeout=10)
            print(f"Testing endpoint: {endpoint}")
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ Found working endpoint: {endpoint}")
                return endpoint
            elif response.status_code == 404:
                print(f"❌ 404 for: {endpoint}")
        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")
    
    return None

def sanitize_code(code):
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def create_institution(name, code):
    """Try multiple API endpoints to create an institution"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
    payload = {"name": str(name).strip(), "code": clean_code}
    
    # Try different endpoint formats
    endpoints = [
        f"{TABBYCAT_URL}/api/v1/institutions/",
        f"{TABBYCAT_URL}/api/institutions/",
        f"{TABBYCAT_URL}/api/v1/institutions",
        f"{TABBYCAT_URL}/api/institutions",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
            elif response.status_code == 404:
                continue  # Try next endpoint
            else:
                # If we got a 200/201, we would have returned above
                # If we got a different error, log it
                print(f"Error with {endpoint}: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"Exception with {endpoint}: {e}")
            continue
    
    return {"success": False, "error": "All API endpoints failed. Check your URL and token."}

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title></head>
        <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
            <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1 style="color: #333;">🚀 Tabbycat Importer</h1>
                <p>Upload your CSV file to import data into your tournament.</p>
                
                <form method="POST" enctype="multipart/form-data" action="/upload">
                    <p>
                        <label><strong>Select CSV File:</strong></label><br>
                        <input type="file" name="file" accept=".csv" required style="padding: 10px; width: 100%;">
                    </p>
                    <p>
                        <label><strong>Import Type:</strong></label><br>
                        <select name="import_type" required style="padding: 10px; width: 100%;">
                            <option value="institutions">Institutions</option>
                            <option value="teams">Teams</option>
                            <option value="adjudicators">Adjudicators</option>
                            <option value="speakers">Speakers</option>
                        </select>
                    </p>
                    <p>
                        <button type="submit" style="background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">
                            Start Import
                        </button>
                    </p>
                </form>
                
                <hr>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 12px;">
                    <p><strong>Debug Info:</strong></p>
                    <p>URL: https://17thvmdc.calicotab.com</p>
                    <p>Token: 30d6f2baab640998ac14594b7459337d8c463e67</p>
                    <p><a href="/test-api" target="_blank">Test API Connection</a></p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/test-api')
def test_api():
    """Test the API connection and show results"""
    results = []
    
    endpoints = [
        f"{TABBYCAT_URL}/api/v1/institutions/",
        f"{TABBYCAT_URL}/api/institutions/",
        f"{TABBYCAT_URL}/api/v1/institutions",
        f"{TABBYCAT_URL}/api/institutions",
    ]
    
    html = "<html><body style='font-family: Arial; padding: 20px;'><h1>API Test Results</h1>"
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=HEADERS, timeout=10)
            status = f"✅ {response.status_code}"
            if response.status_code == 200:
                html += f"<p style='color: green;'>✅ Working: {endpoint}</p>"
            else:
                html += f"<p style='color: orange;'>⚠️ {status}: {endpoint}</p>"
        except Exception as e:
            html += f"<p style='color: red;'>❌ Error: {endpoint} - {str(e)}</p>"
    
    html += "<p><a href='/'>Back to Home</a></p></body></html>"
    return html

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return "No file uploaded", 400
        
        file = request.files['file']
        if file.filename == '':
            return "No file selected", 400
        
        if not file.filename.endswith('.csv'):
            return "Please upload a CSV file.", 400
        
        import_type = request.form.get('import_type', 'institutions')
        
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        
        # Read the CSV
        df = pd.read_csv(filepath)
        df.columns = [col.strip().lower() for col in df.columns]
        
        results = {"total_rows": len(df), "created": 0, "existing": 0, "errors": []}
        
        # Process each row
        for idx, row in df.iterrows():
            if import_type == 'institutions':
                name = str(row['name']).strip()
                code = str(row['code']).strip()
                if name and code:
                    result = create_institution(name, code)
                    if result["success"]:
                        if result.get("existing"):
                            results["existing"] += 1
                        else:
                            results["created"] += 1
                    else:
                        results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown')}")
                else:
                    results["errors"].append(f"Row {idx+2}: Missing name or code")
        
        os.remove(filepath)
        
        # Build result page
        errors_html = ""
        if results['errors']:
            error_items = ''.join([f'<li>{e}</li>' for e in results['errors'][:20]])
            errors_html = f'<h3>⚠️ Errors ({len(results["errors"])}):</h3><ul>{error_items}</ul>'
        
        return f"""
        <html>
            <head><title>Import Complete</title></head>
            <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
                <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h1 style="color: #4CAF50;">✅ Import Complete!</h1>
                    <p><strong>Import Type:</strong> {import_type}</p>
                    <p><strong>Rows Processed:</strong> {results.get('total_rows', 0)}</p>
                    <p><strong>Items Created:</strong> {results.get('created', 0)}</p>
                    <p><strong>Already Existed:</strong> {results.get('existing', 0)}</p>
                    <p><strong>Errors:</strong> {len(results.get('errors', []))}</p>
                    {errors_html}
                    <hr>
                    <p><a href="/" style="color: #4CAF50;">Import Another File</a></p>
                    <p><a href="{TABBYCAT_URL}/database/participants/" target="_blank" style="color: #4CAF50;">View in Database</a></p>
                    <p><a href="/test-api" style="color: #4CAF50;">Test API Connection</a></p>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
