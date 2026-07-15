from flask import Flask, request, jsonify
import pandas as pd
import requests
import re
import os
import time
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

# Store import progress
import_progress = {}

def sanitize_code(code):
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def fix_institution_code(code):
    """Fix common institution code mismatches"""
    code = str(code).strip().upper()
    fixes = {
        'VSU': 'VSIU',
        'USJ-R': 'USJR',
        'USJ R': 'USJR',
        'MSUM': 'MSU-M',
        'MSU-MAIN': 'MSU-M',
        'MSU MAIN': 'MSU-M',
        'MSUII': 'MSU-IIT',
        'MSU-IIT': 'MSU-IIT',
        'UPMIN': 'UPMIN',
        'XU': 'XU',
        'ADDU': 'ADDU',
        'ADZU': 'ADZU',
        'CHMSU': 'CHMSU',
        'CPU': 'CPU',
        'UPC': 'UPC',
        'UPV': 'UPV',
        'USJR': 'USJR',
    }
    return fixes.get(code, code)

def get_api_endpoints(resource_type):
    """Return possible API endpoints for each resource type"""
    base_url = TABBYCAT_URL
    
    endpoints = {
        'institutions': [
            f"{base_url}/api/v1/institutions/",
            f"{base_url}/api/institutions/",
        ],
        'teams': [
            f"{base_url}/api/v1/teams/",
            f"{base_url}/api/teams/",
            f"{base_url}/api/v1/participants/teams/",
            f"{base_url}/api/participants/teams/",
            f"{base_url}/api/v1/database/teams/",
            f"{base_url}/api/database/teams/",
            f"{base_url}/api/v1/tournament/teams/",
            f"{base_url}/api/tournament/teams/",
        ],
        'adjudicators': [
            f"{base_url}/api/v1/adjudicators/",
            f"{base_url}/api/adjudicators/",
            f"{base_url}/api/v1/participants/adjudicators/",
            f"{base_url}/api/participants/adjudicators/",
            f"{base_url}/api/v1/database/adjudicators/",
            f"{base_url}/api/database/adjudicators/",
        ],
        'speakers': [
            f"{base_url}/api/v1/speakers/",
            f"{base_url}/api/speakers/",
            f"{base_url}/api/v1/participants/speakers/",
            f"{base_url}/api/participants/speakers/",
        ]
    }
    return endpoints.get(resource_type, [])

def get_institution_by_code(code):
    """Get institution URL by code"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    try:
        response = requests.get(f"{TABBYCAT_URL}/api/v1/institutions/", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            for inst in response.json():
                if inst.get("code") == clean_code:
                    return inst.get("url")
        return None
    except Exception as e:
        print(f"❌ Error getting institution: {e}")
        return None

def create_institution(name, code):
    clean_code = sanitize_code(code)
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
    payload = {"name": str(name).strip(), "code": clean_code}
    
    for endpoint in get_api_endpoints('institutions'):
        try:
            response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "All institution endpoints failed"}

def create_team(team_data):
    """Create a team using multiple possible endpoints"""
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
    
    if team_data.get('reference') and not pd.isna(team_data.get('reference')):
        payload["reference"] = str(team_data.get('reference')).strip()
    if team_data.get('short_reference') and not pd.isna(team_data.get('short_reference')):
        payload["short_reference"] = str(team_data.get('short_reference')).strip()
    
    for endpoint in get_api_endpoints('teams'):
        try:
            response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=15)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "All team endpoints failed"}

def create_adjudicator(adj_data):
    """Create an adjudicator using multiple possible endpoints"""
    institution_code = sanitize_code(str(adj_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code) if institution_code else None
    
    payload = {"name": str(adj_data.get('name', '')).strip()}
    
    if inst_url:
        payload["institution"] = inst_url
    if adj_data.get('email') and not pd.isna(adj_data.get('email')):
        payload["email"] = str(adj_data.get('email')).strip()
    if adj_data.get('gender') and not pd.isna(adj_data.get('gender')):
        payload["gender"] = str(adj_data.get('gender')).strip()
    
    for endpoint in get_api_endpoints('adjudicators'):
        try:
            response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=15)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "All adjudicator endpoints failed"}

def create_speaker(speaker_data):
    """Create a speaker in Calico"""
    team_name = str(speaker_data.get('team', '')).strip()
    
    # Find the team first
    team_url = None
    for endpoint in get_api_endpoints('teams'):
        try:
            response = requests.get(endpoint, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                teams = response.json()
                for team in teams:
                    if team.get('name') == team_name:
                        team_url = team.get('url')
                        break
                if team_url:
                    break
        except:
            continue
    
    if not team_url:
        return {"success": False, "error": f"Team '{team_name}' not found"}
    
    speaker_payload = {"name": str(speaker_data.get('name', '')).strip()}
    
    if speaker_data.get('email') and not pd.isna(speaker_data.get('email')):
        speaker_payload["email"] = str(speaker_data.get('email')).strip()
    if speaker_data.get('gender') and not pd.isna(speaker_data.get('gender')):
        speaker_payload["gender"] = str(speaker_data.get('gender')).strip()
    
    try:
        speaker_endpoint = f"{team_url}/speakers/"
        response = requests.post(speaker_endpoint, json=speaker_payload, headers=HEADERS, timeout=10)
        if response.status_code in [200, 201]:
            return {"success": True}
        elif response.status_code == 400 and "already exists" in str(response.text).lower():
            return {"success": True, "existing": True}
        else:
            return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title>
        <style>
            body { font-family: Arial; padding: 30px; background: #f0f0f0; }
            .container { max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #333; }
            .btn { background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
            .btn:hover { background: #45a049; }
            select, input[type="file"] { padding: 10px; margin: 10px 0; width: 100%; }
            .info { background: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 12px; margin-top: 10px; }
        </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Tabbycat Importer</h1>
                <p>Upload your CSV file to import data into your tournament.</p>
                
                <form method="POST" enctype="multipart/form-data" action="/upload">
                    <p>
                        <label><strong>Select CSV File:</strong></label><br>
                        <input type="file" name="file" accept=".csv" required>
                    </p>
                    <p>
                        <label><strong>Import Type:</strong></label><br>
                        <select name="import_type" required>
                            <option value="institutions">Institutions</option>
                            <option value="teams">Teams</option>
                            <option value="adjudicators">Adjudicators</option>
                            <option value="speakers">Speakers</option>
                        </select>
                    </p>
                    <p>
                        <button type="submit" class="btn">🚀 Start Import</button>
                    </p>
                </form>
                
                <hr>
                <div class="info">
                    <p><strong>Debug Info:</strong></p>
                    <p>URL: https://17thvmdc.calicotab.com</p>
                    <p><a href="/test-endpoints" target="_blank">🔍 Test All API Endpoints</a></p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/test-endpoints')
def test_endpoints():
    """Test all API endpoints for all resource types"""
    html = """
    <html>
        <head><title>API Endpoint Test</title></head>
        <body style="font-family: Arial; padding: 20px; background: #f0f0f0;">
            <div style="max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1>🔍 API Endpoint Test</h1>
                <p>Testing all possible endpoints for each resource type...</p>
                <hr>
    """
    
    resource_types = ['institutions', 'teams', 'adjudicators', 'speakers']
    
    for resource_type in resource_types:
        html += f"<h2>{resource_type.upper()}</h2>"
        endpoints = get_api_endpoints(resource_type)
        
        for endpoint in endpoints:
            try:
                # Use GET for testing
                response = requests.get(endpoint, headers=HEADERS, timeout=5)
                if response.status_code == 200:
                    html += f"<p style='color: green;'>✅ {endpoint} - Working (200)</p>"
                elif response.status_code == 405:
                    html += f"<p style='color: orange;'>⚠️ {endpoint} - Exists (405 - POST required)</p>"
                elif response.status_code == 404:
                    html += f"<p style='color: red;'>❌ {endpoint} - Not Found (404)</p>"
                else:
                    html += f"<p style='color: orange;'>⚠️ {endpoint} - Status: {response.status_code}</p>"
            except Exception as e:
                html += f"<p style='color: red;'>❌ {endpoint} - Error: {str(e)}</p>"
    
    html += """
                <hr>
                <p><a href="/">Back to Home</a></p>
            </div>
        </body>
    </html>
    """
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
        job_id = str(int(time.time()))
        
        filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}_{file.filename}")
        file.save(filepath)
        
        import_progress[job_id] = {
            "status": "processing",
            "import_type": import_type,
            "total_rows": 0,
            "processed": 0,
            "created": 0,
            "existing": 0,
            "errors": [],
            "complete": False
        }
        
        import threading
        thread = threading.Thread(target=process_import_background, args=(filepath, import_type, job_id))
        thread.daemon = True
        thread.start()
        
        return f"""
        <html>
            <head><title>Import Started</title></head>
            <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h1 style="color: #4CAF50;">✅ Import Started!</h1>
                    <p><strong>Import Type:</strong> {import_type}</p>
                    <p><strong>Job ID:</strong> {job_id}</p>
                    <p><a href="/status?job_id={job_id}" style="color: #4CAF50;">Check Status</a></p>
                    <p><a href="/" style="color: #4CAF50;">Back to Home</a></p>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"Error: {str(e)}", 500

def process_import_background(filepath, import_type, job_id):
    try:
        df = pd.read_csv(filepath)
        df.columns = [col.strip().lower() for col in df.columns]
        
        total_rows = len(df)
        import_progress[job_id]["total_rows"] = total_rows
        
        results = {"created": 0, "existing": 0, "errors": []}
        
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
            
            elif import_type == 'teams':
                institution = fix_institution_code(str(row['institution']).strip().upper())
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
                        results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown')}")
                else:
                    results["errors"].append(f"Row {idx+2}: Missing institution or code name")
            
            elif import_type == 'adjudicators':
                name = str(row['name']).strip()
                if name:
                    adj_data = {"name": name}
                    if 'institution' in df.columns and not pd.isna(row['institution']):
                        adj_data["institution"] = fix_institution_code(str(row['institution']).strip().upper())
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
                        results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown')}")
                else:
                    results["errors"].append(f"Row {idx+2}: Missing name")
            
            elif import_type == 'speakers':
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
                        results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown')}")
                else:
                    results["errors"].append(f"Row {idx+2}: Missing name or team")
            
            import_progress[job_id]["processed"] += 1
            import_progress[job_id]["created"] = results["created"]
            import_progress[job_id]["existing"] = results["existing"]
            import_progress[job_id]["errors"] = results["errors"]
            
            time.sleep(0.3)
        
        try:
            os.remove(filepath)
        except:
            pass
        
        import_progress[job_id]["complete"] = True
        import_progress[job_id]["status"] = "complete"
        import_progress[job_id]["created"] = results["created"]
        import_progress[job_id]["existing"] = results["existing"]
        import_progress[job_id]["errors"] = results["errors"]
        
    except Exception as e:
        import_progress[job_id]["status"] = "error"
        import_progress[job_id]["errors"].append(str(e))
        try:
            os.remove(filepath)
        except:
            pass

@app.route('/status')
def status():
    job_id = request.args.get('job_id')
    
    if not job_id:
        return """
        <html>
            <body style="font-family: Arial; padding: 20px;">
                <h1>Import Status</h1>
                <p>No job ID provided. <a href="/">Go back to home</a> and start an import.</p>
            </body>
        </html>
        """
    
    if job_id not in import_progress:
        return f"""
        <html>
            <body style="font-family: Arial; padding: 20px;">
                <h1>Job Not Found</h1>
                <p>Job ID {job_id} not found.</p>
                <p><a href="/">Back to Home</a></p>
            </body>
        </html>
        """
    
    progress = import_progress[job_id]
    
    if progress["complete"]:
        errors_html = ""
        if progress.get("errors"):
            error_items = ''.join([f'<li>{e}</li>' for e in progress["errors"][:20]])
            errors_html = f'<h3>⚠️ Errors ({len(progress["errors"])}):</h3><ul>{error_items}</ul>'
        
        return f"""
        <html>
            <head><title>Import Complete</title></head>
            <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
                <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h1 style="color: #4CAF50;">✅ Import Complete!</h1>
                    <p><strong>Import Type:</strong> {progress['import_type']}</p>
                    <p><strong>Rows Processed:</strong> {progress['processed']}</p>
                    <p><strong>Items Created:</strong> {progress['created']}</p>
                    <p><strong>Already Existed:</strong> {progress['existing']}</p>
                    <p><strong>Errors:</strong> {len(progress.get('errors', []))}</p>
                    {errors_html}
                    <hr>
                    <p><a href="/" style="color: #4CAF50;">Import Another File</a></p>
                    <p><a href="{TABBYCAT_URL}/database/participants/" target="_blank" style="color: #4CAF50;">View in Database</a></p>
                    <p><a href="/test-endpoints" style="color: #4CAF50;">Test API Endpoints</a></p>
                </div>
            </body>
        </html>
        """
    else:
        percent = int((progress['processed'] / progress['total_rows']) * 100) if progress['total_rows'] > 0 else 0
        return f"""
        <html>
            <head><title>Import Progress</title></head>
            <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h1>⏳ Import In Progress</h1>
                    <p><strong>Import Type:</strong> {progress['import_type']}</p>
                    <p><strong>Progress:</strong> {progress['processed']} / {progress['total_rows']} rows ({percent}%)</p>
                    <p><strong>Created:</strong> {progress['created']}</p>
                    <p><strong>Already Existed:</strong> {progress['existing']}</p>
                    <p><strong>Errors:</strong> {len(progress.get('errors', []))}</p>
                    <div style="width: 100%; background: #f0f0f0; border-radius: 5px; height: 20px;">
                        <div style="width: {percent}%; background: #4CAF50; height: 20px; border-radius: 5px;"></div>
                    </div>
                    <p style="margin-top: 10px;"><a href="/status?job_id={job_id}" style="color: #4CAF50;">Refresh Status</a></p>
                    <p><a href="/">Back to Home</a></p>
                </div>
            </body>
        </html>
        """

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
