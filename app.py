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
TABBYCAT_TOKEN = "30d6f2baab640998ac14594b7459337d8c463e67"

HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

# Store import progress
import_progress = {}

def discover_api_endpoint():
    """Try every possible API path to find the right one"""
    # Common API path patterns
    paths = [
        "/api/v1/institutions/",
        "/api/institutions/",
        "/api/v1/institutions",
        "/api/institutions",
        "/institutions/api/",
        "/api/v1/participants/institutions/",
        "/api/participants/institutions/",
        "/api/v1/database/institutions/",
        "/api/database/institutions/",
        "/rest/v1/institutions/",
        "/rest/institutions/",
        "/v1/institutions/",
        "/institutions/",
        "/api/v1/institution/",
        "/api/institution/",
        "/api/v1/",
        "/api/",
        "/admin/api/v1/institutions/",
        "/admin/api/institutions/",
    ]
    
    results = []
    for path in paths:
        url = f"{TABBYCAT_URL}{path}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            status = response.status_code
            is_working = status in [200, 201, 405]  # 405 means endpoint exists but wrong method
            results.append({
                "url": url,
                "status": status,
                "working": is_working,
                "response": response.text[:100] if is_working else ""
            })
            if is_working:
                print(f"✅ Found: {url} (Status: {status})")
                return url
        except Exception as e:
            results.append({"url": url, "status": "error", "working": False, "response": str(e)})
    
    return results

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title>
        <style>
            body { font-family: Arial; padding: 30px; background: #f0f0f0; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #333; }
            .btn { background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
            .btn:hover { background: #45a049; }
            select, input[type="file"] { padding: 10px; margin: 10px 0; width: 100%; }
            .info { background: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 12px; margin-top: 10px; }
            .warning { background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107; margin: 10px 0; }
        </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Tabbycat Importer</h1>
                <p>Upload your CSV file to import data into your tournament.</p>
                
                <div class="warning">
                    <strong>⚠️ API Discovery:</strong> Click "Find API" below to auto-detect the correct API endpoint.
                </div>
                
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
                <p><a href="/find-api" class="btn" style="background: #007bff;">🔍 Find API Endpoint</a></p>
                <div class="info">
                    <p><strong>Debug Info:</strong></p>
                    <p>URL: https://17thvmdc.calicotab.com</p>
                    <p>Token: 30d6f2baab640998ac14594b7459337d8c463e67</p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/find-api')
def find_api():
    """Auto-discover the API endpoint"""
    results = discover_api_endpoint()
    
    html = """
    <html>
        <head><title>API Discovery</title></head>
        <body style="font-family: Arial; padding: 20px; background: #f0f0f0;">
            <div style="max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1>🔍 API Discovery Results</h1>
    """
    
    if isinstance(results, str):
        # Found a working endpoint
        html += f"""
                <div style="background: #d4edda; padding: 15px; border-radius: 5px;">
                    <h2 style="color: #155724;">✅ Found Working API!</h2>
                    <p><strong>Endpoint:</strong> {results}</p>
                    <p>This endpoint is working. Your imports should now work.</p>
                </div>
                <p><a href="/">Back to Home</a></p>
        """
    else:
        # No working endpoint found
        html += """
                <div style="background: #f8d7da; padding: 15px; border-radius: 5px;">
                    <h2 style="color: #721c24;">❌ No Working API Found</h2>
                    <p>None of the API paths worked. This means:</p>
                    <ul>
                        <li>The API might be disabled on your Calico instance</li>
                        <li>Your token might not have API permissions</li>
                        <li>The API is at a custom path not in our list</li>
                    </ul>
                </div>
                <h3>Attempted Paths:</h3>
                <ul>
        """
        for result in results:
            status_color = "green" if result["working"] else "red"
            html += f"""
                    <li style="color: {status_color};">
                        {result['url']} → Status: {result['status']}
                        {f"✅" if result['working'] else "❌"}
                    </li>
            """
        html += """
                </ul>
                <p><a href="/">Back to Home</a></p>
        """
    
    html += """
            </div>
        </body>
    </html>
    """
    return html

def create_institution(name, code):
    """Try multiple API endpoints to create an institution"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
    payload = {"name": str(name).strip(), "code": clean_code}
    
    # Try all possible endpoint patterns
    paths = [
        "/api/v1/institutions/",
        "/api/institutions/",
        "/api/v1/institutions",
        "/api/institutions",
        "/institutions/api/",
        "/api/v1/participants/institutions/",
        "/api/participants/institutions/",
    ]
    
    for path in paths:
        endpoint = f"{TABBYCAT_URL}{path}"
        try:
            response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "All API endpoints failed. API may be disabled."}

def sanitize_code(code):
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def get_institution_by_code(code):
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    paths = [
        "/api/v1/institutions/",
        "/api/institutions/",
    ]
    
    for path in paths:
        try:
            response = requests.get(f"{TABBYCAT_URL}{path}", headers=HEADERS, timeout=10)
            for inst in response.json():
                if inst.get("code") == clean_code:
                    return inst.get("url")
        except:
            continue
    return None

def create_team(team_data):
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
    
    paths = [
        "/api/v1/teams/",
        "/api/teams/",
    ]
    
    for path in paths:
        try:
            response = requests.post(f"{TABBYCAT_URL}{path}", json=payload, headers=HEADERS, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "API request failed"}

def create_adjudicator(adj_data):
    institution_code = sanitize_code(str(adj_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code) if institution_code else None
    
    payload = {"name": str(adj_data.get('name', '')).strip()}
    
    if inst_url:
        payload["institution"] = inst_url
    if adj_data.get('email') and not pd.isna(adj_data.get('email')):
        payload["email"] = str(adj_data.get('email')).strip()
    if adj_data.get('gender') and not pd.isna(adj_data.get('gender')):
        payload["gender"] = str(adj_data.get('gender')).strip()
    
    paths = [
        "/api/v1/adjudicators/",
        "/api/adjudicators/",
    ]
    
    for path in paths:
        try:
            response = requests.post(f"{TABBYCAT_URL}{path}", json=payload, headers=HEADERS, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "API request failed"}

def create_speaker(speaker_data):
    team_name = str(speaker_data.get('team', '')).strip()
    
    paths = [
        "/api/v1/teams/",
        "/api/teams/",
    ]
    
    for path in paths:
        try:
            response = requests.get(f"{TABBYCAT_URL}{path}", headers=HEADERS, timeout=10)
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
            response = requests.post(speaker_endpoint, json=speaker_payload, headers=HEADERS, timeout=10)
            
            if response.status_code in [200, 201]:
                return {"success": True}
            elif response.status_code == 400 and "already exists" in str(response.text).lower():
                return {"success": True, "existing": True}
        except:
            continue
    
    return {"success": False, "error": "API request failed"}

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
        
        # Start background import
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
                    <p>The import is running in the background.</p>
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
                institution = str(row['institution']).strip().upper()
                code_name = str(row['code name']).strip()
                if institution and code_name:
                    team_data = {
                        "institution": institution,
                        "code name": code_name,
                        "team_name (human)": row.get('team_name (human)', '') if not pd.isna(row.get('team_name (human)', '')) else '',
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
                        adj_data["institution"] = str(row['institution']).strip().upper()
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
            
            # Small delay to prevent API rate limiting
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
