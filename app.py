from flask import Flask, request, jsonify
import pandas as pd
import requests
import re
import os

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Your Calico credentials
TABBYCAT_URL = "https://17thvmdc.calicotab.com"  # Your tournament URL
TABBYCAT_TOKEN = "30d6f2baab640998ac14594b7459337d8c463e67"  # Your token

# API Headers
HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

def sanitize_code(code):
    """Clean institution code - remove spaces and special characters"""
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def create_institution(name, code):
    """Create an institution in Calico"""
    endpoint = f"{TABBYCAT_URL}/api/v1/institutions/"
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
            return {"success": False, "error": f"Status {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_institution_by_code(code):
    """Get institution URL by code"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    try:
        response = requests.get(f"{TABBYCAT_URL}/api/v1/institutions/", headers=HEADERS, timeout=30)
        for inst in response.json():
            if inst.get("code") == clean_code:
                return inst.get("url")
        return None
    except:
        return None

def create_team(team_data):
    """Create a team in Calico"""
    endpoint = f"{TABBYCAT_URL}/api/v1/teams/"
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
            return {"success": False, "error": f"Status {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_adjudicator(adj_data):
    """Create an adjudicator in Calico"""
    endpoint = f"{TABBYCAT_URL}/api/v1/adjudicators/"
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
            return {"success": False, "error": f"Status {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_speaker(speaker_data):
    """Create a speaker in Calico"""
    team_name = str(speaker_data.get('team', '')).strip()
    
    try:
        response = requests.get(f"{TABBYCAT_URL}/api/v1/teams/", headers=HEADERS, timeout=30)
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
            return {"success": False, "error": f"Status {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title></head>
        <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
            <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1 style="color: #333;">🚀 Tabbycat Importer</h1>
                <p>Upload your CSV or Excel file to import data into your tournament.</p>
                
                <form method="POST" enctype="multipart/form-data" action="/upload">
                    <p>
                        <label><strong>Select File:</strong></label><br>
                        <input type="file" name="file" accept=".csv,.xlsx,.xls" required style="padding: 10px; width: 100%;">
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
                <p style="color: #666; font-size: 14px;">
                    <strong>File format:</strong> CSV or Excel with the required columns for your import type.<br>
                    <strong>Institutions:</strong> name, code<br>
                    <strong>Teams:</strong> institution, code name, team_name (human)<br>
                    <strong>Adjudicators:</strong> name, institution, email, gender<br>
                    <strong>Speakers:</strong> name, team, email, gender
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return "No file uploaded", 400
        
        file = request.files['file']
        if file.filename == '':
            return "No file selected", 400
        
        # Check file extension
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            return "Invalid file type. Use CSV or Excel.", 400
        
        # Get import type
        import_type = request.form.get('import_type', 'institutions')
        
        # Save the file
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        
        # Read the file
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Make column names lowercase
        df.columns = [col.strip().lower() for col in df.columns]
        
        # Process based on import type
        results = process_import(df, import_type)
        
        # Clean up
        os.remove(filepath)
        
        # Build result HTML
        errors_html = ""
        if results.get('errors'):
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
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"Error: {str(e)}", 500

def process_import(df, import_type):
    """Process the dataframe based on import type"""
    results = {"total_rows": len(df), "created": 0, "existing": 0, "errors": []}
    
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
                    if result.get("existing"):
                        results["existing"] += 1
                    else:
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
                    "team_name (human)": row.get('team_name (human)', '') if not pd.isna(row.get('team_name (human)', '')) else '',
                    "reference": row.get('reference', '') if not pd.isna(row.get('reference', '')) else '',
                    "short_reference": row.get('short_reference', '') if not pd.isna(row.get('short_reference', '')) else '',
                    "use_institution_prefix": row.get('use_institution_prefix', True) if not pd.isna(row.get('use_institution_prefix', True)) else True
                }
                result = create_team(team_data)
                if result["success"]:
                    if result.get("existing"):
                        results["existing"] += 1
                    else:
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
                if 'institution' in df.columns and not pd.isna(row['institution']):
                    adj_data["institution"] = str(row['institution']).strip()
                if 'email' in df.columns and not pd.isna(row['email']):
                    adj_data["email"] = str(row['email']).strip()
                if 'gender' in df.columns and not pd.isna(row['gender']):
                    adj_data["gender"] = str(row['gender']).strip()
                
                result = create_adjudicator(adj_data)
                if result["success"]:
                    if result.get("existing"):
                        results["existing"] += 1
                    else:
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
                    "email": row.get('email', '') if not pd.isna(row.get('email', '')) else '',
                    "gender": row.get('gender', '') if not pd.isna(row.get('gender', '')) else ''
                }
                result = create_speaker(speaker_data)
                if result["success"]:
                    if result.get("existing"):
                        results["existing"] += 1
                    else:
                        results["created"] += 1
                else:
                    results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
            else:
                results["errors"].append(f"Row {idx+2}: Missing name or team")
    
    return results

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
