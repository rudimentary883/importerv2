import os
import re
import warnings
warnings.filterwarnings('ignore')
import requests
import pandas as pd
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import gc

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Get Tabbycat credentials
TABBYCAT_BASE_URL = os.getenv('TABBYCAT_URL', 'https://calicotab.com')
TABBYCAT_BASE_URL = TABBYCAT_BASE_URL.rstrip('/')
TABBYCAT_TOKEN = os.getenv('TABBYCAT_TOKEN', '')

TABBYCAT_API_URL = f"{TABBYCAT_BASE_URL}/api/v1"

print("=" * 60)
print("🔍 TABBYCAT IMPORTER - STARTUP CHECK")
print("=" * 60)
print(f"📡 TABBYCAT_BASE_URL: {TABBYCAT_BASE_URL}")
print(f"📡 TABBYCAT_API_URL: {TABBYCAT_API_URL}")
print(f"🔑 TABBYCAT_TOKEN: {TABBYCAT_TOKEN[:15]}... (first 15 chars)")
print("=" * 60)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================
# HTML TEMPLATES (Fixed - no curly braces in CSS)
# ============================================================

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Tabbycat Importer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .upload-area { border: 2px dashed #ddd; padding: 30px; text-align: center; border-radius: 8px; margin: 20px 0; }
        .btn { background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        .btn:hover { background: #45a049; }
        select, input[type="file"] { padding: 10px; margin: 10px 0; width: 100%; }
        .status { padding: 15px; margin: 10px 0; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .result-box { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .error-list { color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Tabbycat Importer</h1>
        <p>Upload CSV files to import institutions, teams, adjudicators, and speakers.</p>
        
        <div class="upload-area">
            <form method="POST" enctype="multipart/form-data" action="/upload">
                <p><strong>Select CSV or Excel file:</strong></p>
                <input type="file" name="file" accept=".csv,.xlsx,.xls" required>
                
                <p><strong>Import Type:</strong></p>
                <select name="import_type" required>
                    <option value="institutions">🏛️ Institutions</option>
                    <option value="teams">👥 Teams</option>
                    <option value="adjudicators">⚖️ Adjudicators</option>
                    <option value="speakers">🎤 Speakers</option>
                </select>
                
                <br><br>
                <button type="submit" class="btn">🚀 Start Import</button>
            </form>
        </div>
        
        <div class="info">
            <strong>📝 File Format Requirements:</strong><br>
            <strong>Institutions:</strong> name, code<br>
            <strong>Teams:</strong> institution, reference, short_reference, code name, use_institution_prefix, team_name (human)<br>
            <strong>Adjudicators:</strong> name, institution, email, gender<br>
            <strong>Speakers:</strong> name, team, email, gender
        </div>
        
        <div style="margin-top: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px;">
            <p><strong>🔗 API URL:</strong> {api_url}</p>
            <p><strong>🔑 Token:</strong> {token_preview}...</p>
            <p><a href="/health">Health Check</a></p>
        </div>
    </div>
</body>
</html>
"""

RESULT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Import Complete</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .success-box { background: #d4edda; padding: 15px; border-radius: 5px; margin: 10px 0; color: #155724; border: 1px solid #c3e6cb; }
        .error-box { background: #f8d7da; padding: 15px; border-radius: 5px; margin: 10px 0; color: #721c24; border: 1px solid #f5c6cb; }
        .btn { background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #45a049; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Import Complete</h1>
        <div class="success-box">
            <strong>Rows Processed:</strong> {total_rows}<br>
            <strong>Items Created:</strong> {created}<br>
            <strong>Errors:</strong> {error_count}
        </div>
        {errors_html}
        <p><a href="/" class="btn">Import Another File</a></p>
        <p><a href="/">Back to Home</a></p>
    </div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Error</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #721c24; }
        .error-box { background: #f8d7da; padding: 15px; border-radius: 5px; margin: 10px 0; color: #721c24; border: 1px solid #f5c6cb; }
        .btn { background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #45a049; }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Error</h1>
        <div class="error-box">
            <p>{error_message}</p>
        </div>
        <p><a href="/" class="btn">Go Back</a></p>
    </div>
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Main page with upload form"""
    token_preview = TABBYCAT_TOKEN[:10] if TABBYCAT_TOKEN else 'NOT SET'
    return INDEX_HTML.format(api_url=TABBYCAT_API_URL, token_preview=token_preview)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and import"""
    if 'file' not in request.files:
        return ERROR_HTML.format(error_message="No file selected"), 400
    
    file = request.files['file']
    if file.filename == '':
        return ERROR_HTML.format(error_message="No file selected"), 400
    
    if not allowed_file(file.filename):
        return ERROR_HTML.format(error_message="Invalid file type. Use CSV or Excel."), 400
    
    import_type = request.form.get('import_type', 'institutions')
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        # Read the file
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        df.columns = [col.strip().lower() for col in df.columns]
        
        # Process based on import type
        result = process_file(df, import_type)
        
        # Clean up
        try:
            os.remove(filepath)
        except:
            pass
        
        # Format errors
        errors_html = ""
        if result.get('errors'):
            error_items = ''.join([f'<li>{e}</li>' for e in result['errors'][:20]])
            if len(result['errors']) > 20:
                error_items += f'<li>... and {len(result["errors"]) - 20} more errors</li>'
            errors_html = f'<div class="error-box"><strong>⚠️ Errors:</strong><ul>{error_items}</ul></div>'
        
        return RESULT_HTML.format(
            total_rows=result.get('total_rows', 0),
            created=result.get('created', 0),
            error_count=len(result.get('errors', [])),
            errors_html=errors_html
        )
        
    except Exception as e:
        try:
            os.remove(filepath)
        except:
            pass
        return ERROR_HTML.format(error_message=str(e)), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "message": "Tabbycat Importer is running"})

# ============================================================
# PROCESSING FUNCTIONS
# ============================================================

def process_file(df, import_type):
    """Process the dataframe based on import type"""
    results = {"total_rows": len(df), "created": 0, "errors": []}
    
    if import_type == 'institutions':
        if 'name' not in df.columns or 'code' not in df.columns:
            results["errors"].append("Missing 'name' or 'code' columns")
            return results
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            code = str(row['code']).strip()
            if name and code:
                result = create_institution(name, code)
                if result["success"]:
                    results["created"] += 1
                else:
                    results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
            else:
                results["errors"].append(f"Row {idx+2}: Missing name or code")
    
    elif import_type == 'teams':
        if 'institution' not in df.columns or 'code name' not in df.columns:
            results["errors"].append("Missing 'institution' or 'code name' columns")
            return results
        
        for idx, row in df.iterrows():
            institution = str(row['institution']).strip()
            code_name = str(row['code name']).strip()
            if institution and code_name:
                team_data = {
                    "institution": institution,
                    "code name": code_name,
                    "team_name (human)": row.get('team_name (human)', ''),
                    "reference": row.get('reference', ''),
                    "short_reference": row.get('short_reference', ''),
                    "use_institution_prefix": row.get('use_institution_prefix', True)
                }
                result = create_team(team_data)
                if result["success"]:
                    results["created"] += 1
                else:
                    results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
            else:
                results["errors"].append(f"Row {idx+2}: Missing institution or code name")
    
    elif import_type == 'adjudicators':
        if 'name' not in df.columns:
            results["errors"].append("Missing 'name' column")
            return results
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            if name:
                adj_data = {"name": name}
                if 'institution' in df.columns:
                    adj_data["institution"] = str(row['institution']).strip()
                if 'email' in df.columns:
                    adj_data["email"] = str(row['email']).strip()
                if 'gender' in df.columns:
                    adj_data["gender"] = str(row['gender']).strip()
                
                result = create_adjudicator(adj_data)
                if result["success"]:
                    results["created"] += 1
                else:
                    results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
            else:
                results["errors"].append(f"Row {idx+2}: Missing name")
    
    elif import_type == 'speakers':
        if 'name' not in df.columns or 'team' not in df.columns:
            results["errors"].append("Missing 'name' or 'team' columns")
            return results
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            team = str(row['team']).strip()
            if name and team:
                speaker_data = {
                    "name": name,
                    "team": team,
                    "email": row.get('email', ''),
                    "gender": row.get('gender', '')
                }
                result = create_speaker(speaker_data)
                if result["success"]:
                    results["created"] += 1
                else:
                    results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
            else:
                results["errors"].append(f"Row {idx+2}: Missing name or team")
    
    return results

# ============================================================
# API FUNCTIONS
# ============================================================

def sanitize_code(code):
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def create_institution(name, code):
    endpoint = f"{TABBYCAT_API_URL}/institutions/"
    clean_code = sanitize_code(code)
    
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
    payload = {"name": str(name).strip(), "code": clean_code}
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        if response.status_code in [200, 201]:
            return {"success": True}
        elif response.status_code == 400 and "already exists" in str(response.text).lower():
            return {"success": True, "existing": True}
        else:
            return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_institution_by_code(code):
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    try:
        response = requests.get(f"{TABBYCAT_API_URL}/institutions/", headers=HEADERS, timeout=30)
        for inst in response.json():
            if inst.get("code") == clean_code:
                return inst.get("url")
        return None
    except:
        return None

def create_team(team_data):
    endpoint = f"{TABBYCAT_API_URL}/teams/"
    institution_code = sanitize_code(str(team_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code)
    
    if not inst_url:
        return {"success": False, "error": f"Institution '{institution_code}' not found"}
    
    team_name = team_data.get('team_name (human)', '') or team_data.get('code name', '')
    
    payload = {
        "name": str(team_name).strip(),
        "institution": inst_url,
        "use_institution_prefix": bool(team_data.get('use_institution_prefix', True))
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        if response.status_code in [200, 201]:
            return {"success": True}
        elif response.status_code == 400 and "already exists" in str(response.text).lower():
            return {"success": True, "existing": True}
        else:
            return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_adjudicator(adj_data):
    endpoint = f"{TABBYCAT_API_URL}/adjudicators/"
    institution_code = sanitize_code(str(adj_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code) if institution_code else None
    
    payload = {"name": str(adj_data.get('name', '')).strip()}
    
    if inst_url:
        payload["institution"] = inst_url
    if adj_data.get('email') and not pd.isna(adj_data.get('email')):
        payload["email"] = str(adj_data.get('email')).strip()
    if adj_data.get('gender') and not pd.isna(adj_data.get('gender')):
        payload["gender"] = str(adj_data.get('gender')).strip()
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        if response.status_code in [200, 201]:
            return {"success": True}
        elif response.status_code == 400 and "already exists" in str(response.text).lower():
            return {"success": True, "existing": True}
        else:
            return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_speaker(speaker_data):
    team_name = str(speaker_data.get('team', '')).strip()
    
    try:
        response = requests.get(f"{TABBYCAT_API_URL}/teams/", headers=HEADERS, timeout=30)
        teams = response.json()
        
        team_url = None
        for team in teams:
            if team.get('name') == team_name:
                team_url = team.get('url')
                break
        
        if not team_url:
            return {"success": False, "error": f"Team '{team_name}' not found"}
        
        speaker_payload = {"name": str(speaker_data.get('name', '')).strip()}
        
        if speaker_data.get('email') and not pd.isna(speaker_data.get('email')):
            speaker_payload["email"] = str(speaker_data.get('email')).strip()
        if speaker_data.get('gender') and not pd.isna(speaker_data.get('gender')):
            speaker_payload["gender"] = str(speaker_data.get('gender')).strip()
        
        speaker_endpoint = f"{team_url}/speakers/"
        response = requests.post(speaker_endpoint, json=speaker_payload, headers=HEADERS, timeout=30)
        
        if response.status_code in [200, 201]:
            return {"success": True}
        elif response.status_code == 400 and "already exists" in str(response.text).lower():
            return {"success": True, "existing": True}
        else:
            return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
