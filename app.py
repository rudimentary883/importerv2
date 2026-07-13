import os
import re
import requests
import pandas as pd
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Get Tabbycat credentials from environment variables
TABBYCAT_URL = os.getenv('TABBYCAT_URL', 'https://your-tabbycat-instance.com')
TABBYCAT_TOKEN = os.getenv('TABBYCAT_TOKEN', 'your-admin-token-here')

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_code(code):
    """Clean institution code - remove special characters and spaces"""
    if pd.isna(code) or code == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def create_institution(name, code):
    """Create an institution in Tabbycat"""
    endpoint = f"{TABBYCAT_URL}/api/v1/institutions"
    clean_code = sanitize_code(code)
    payload = {"name": str(name).strip(), "code": clean_code}
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "url": response.json().get("url"), "code": clean_code}
    except requests.exceptions.RequestException as e:
        # Check if institution already exists
        if response and response.status_code == 400 and "already exists" in str(response.text).lower():
            # Try to find existing institution
            try:
                get_response = requests.get(
                    f"{TABBYCAT_URL}/api/v1/institutions",
                    headers=HEADERS,
                    timeout=30
                )
                get_response.raise_for_status()
                institutions = get_response.json()
                for inst in institutions:
                    if inst.get("code") == clean_code:
                        return {"success": True, "url": inst.get("url"), "code": clean_code, "existing": True}
            except:
                pass
        return {"success": False, "error": str(e)}

def get_institution_by_code(code):
    """Get institution URL by its code"""
    clean_code = sanitize_code(code)
    try:
        response = requests.get(
            f"{TABBYCAT_URL}/api/v1/institutions",
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        institutions = response.json()
        for inst in institutions:
            if inst.get("code") == clean_code:
                return inst.get("url")
        return None
    except:
        return None

def create_team(team_data):
    """Create a team in Tabbycat with the exact format from the spreadsheet"""
    endpoint = f"{TABBYCAT_URL}/api/v1/teams"
    
    # Get institution URL by code
    institution_code = sanitize_code(str(team_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code)
    
    if not inst_url:
        return {"success": False, "error": f"Institution '{institution_code}' not found"}
    
    # Build team name - use team_name (human) if available, otherwise use code name
    team_name = team_data.get('team_name (human)', '')
    if not team_name or pd.isna(team_name):
        team_name = team_data.get('code name', '')
    
    payload = {
        "name": str(team_name).strip(),
        "institution": inst_url,
        "reference": str(team_data.get('reference', '')),
        "short_reference": str(team_data.get('short_reference', '')),
        "use_institution_prefix": bool(team_data.get('use_institution_prefix', True))
    }
    
    # Add emoji if present
    if team_data.get('emoji') and not pd.isna(team_data.get('emoji')):
        payload["emoji"] = str(team_data.get('emoji')).strip()
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "response": response.text if response else None}

def create_adjudicator(adj_data):
    """Create an adjudicator in Tabbycat"""
    endpoint = f"{TABBYCAT_URL}/api/v1/adjudicators"
    
    # Get institution URL by code
    institution_code = sanitize_code(str(adj_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code) if institution_code else None
    
    payload = {
        "name": str(adj_data.get('name', '')).strip()
    }
    
    # Add optional fields if they exist and have values
    if inst_url:
        payload["institution"] = inst_url
    if adj_data.get('email') and not pd.isna(adj_data.get('email')):
        payload["email"] = str(adj_data.get('email')).strip()
    if adj_data.get('gender') and not pd.isna(adj_data.get('gender')):
        payload["gender"] = str(adj_data.get('gender')).strip()
    if adj_data.get('base_score') is not None and not pd.isna(adj_data.get('base_score')):
        payload["base_score"] = float(adj_data.get('base_score'))
    if adj_data.get('independent') is not None and not pd.isna(adj_data.get('independent')):
        payload["independent"] = bool(adj_data.get('independent'))
    if adj_data.get('adj_core') is not None and not pd.isna(adj_data.get('adj_core')):
        payload["adj_core"] = bool(adj_data.get('adj_core'))
    if adj_data.get('notes') and not pd.isna(adj_data.get('notes')):
        payload["notes"] = str(adj_data.get('notes')).strip()
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "response": response.text if response else None}

def create_speaker(speaker_data):
    """Create a speaker in Tabbycat (using the team endpoint with speakers)"""
    # Get team by name
    team_name = str(speaker_data.get('team', '')).strip()
    endpoint = f"{TABBYCAT_URL}/api/v1/teams"
    
    try:
        # Try to find existing team
        response = requests.get(endpoint, headers=HEADERS, timeout=30)
        response.raise_for_status()
        teams = response.json()
        
        # Find team by name
        team_url = None
        for team in teams:
            if team.get('name') == team_name:
                team_url = team.get('url')
                break
        
        if not team_url:
            return {"success": False, "error": f"Team '{team_name}' not found"}
        
        # Create speaker (will be added to team)
        # Since Tabbycat's API creates speakers within teams, we'll use the team's speakers endpoint
        speaker_payload = {
            "name": str(speaker_data.get('name', '')).strip()
        }
        
        if speaker_data.get('email') and not pd.isna(speaker_data.get('email')):
            speaker_payload["email"] = str(speaker_data.get('email')).strip()
        if speaker_data.get('gender') and not pd.isna(speaker_data.get('gender')):
            speaker_payload["gender"] = str(speaker_data.get('gender')).strip()
        if speaker_data.get('phone') and not pd.isna(speaker_data.get('phone')):
            speaker_payload["phone"] = str(speaker_data.get('phone')).strip()
        if speaker_data.get('anonymous') is not None and not pd.isna(speaker_data.get('anonymous')):
            speaker_payload["anonymous"] = bool(speaker_data.get('anonymous'))
        if speaker_data.get('initials match') and not pd.isna(speaker_data.get('initials match')):
            speaker_payload["initials_match"] = str(speaker_data.get('initials match')).strip()
        
        # Use the team's speakers endpoint
        speaker_endpoint = f"{team_url}/speakers"
        response = requests.post(speaker_endpoint, json=speaker_payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "response": response.text if response else None}

def process_institutions(filepath):
    """Process institutions from spreadsheet (Format: id, name, code)"""
    try:
        df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
        
        # Check required columns
        required_cols = ['id', 'name', 'code']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        df = df.fillna('')
        results = {
            "success": True,
            "total_rows": len(df),
            "created": 0,
            "errors": [],
            "details": []
        }
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            code = str(row['code']).strip()
            
            if not name or not code:
                results["errors"].append(f"Row {idx+2}: Missing name or code")
                continue
            
            result = create_institution(name, code)
            if result["success"]:
                results["created"] += 1
                results["details"].append({
                    "name": name,
                    "code": code,
                    "status": "Created" if not result.get("existing") else "Already existed"
                })
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_adjudicators(filepath):
    """Process adjudicators from spreadsheet (Format: id, name, institution, email, gender, base_score, independent, adj_core, notes)"""
    try:
        df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
        
        # Expected columns
        expected_cols = ['id', 'name', 'institution', 'email', 'gender', 'base_score', 'independent', 'adj_core', 'notes']
        # Check which columns exist
        available_cols = [col for col in expected_cols if col in df.columns]
        
        if 'name' not in df.columns:
            return {"success": False, "error": "Missing required column: 'name'"}
        
        df = df.fillna('')
        results = {
            "success": True,
            "total_rows": len(df),
            "created": 0,
            "errors": [],
            "details": []
        }
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            if not name:
                results["errors"].append(f"Row {idx+2}: Missing name")
                continue
            
            # Build adjudicator data
            adj_data = {"name": name}
            
            # Only add fields that exist in the dataframe
            if 'institution' in df.columns and not pd.isna(row['institution']):
                adj_data["institution"] = str(row['institution']).strip()
            if 'email' in df.columns and not pd.isna(row['email']):
                adj_data["email"] = str(row['email']).strip()
            if 'gender' in df.columns and not pd.isna(row['gender']):
                adj_data["gender"] = str(row['gender']).strip()
            if 'base_score' in df.columns and not pd.isna(row['base_score']) and row['base_score'] != '':
                try:
                    adj_data["base_score"] = float(row['base_score'])
                except:
                    pass
            if 'independent' in df.columns and not pd.isna(row['independent']):
                if isinstance(row['independent'], str):
                    adj_data["independent"] = row['independent'].strip().upper() == 'TRUE'
                else:
                    adj_data["independent"] = bool(row['independent'])
            if 'adj_core' in df.columns and not pd.isna(row['adj_core']):
                if isinstance(row['adj_core'], str):
                    adj_data["adj_core"] = row['adj_core'].strip().upper() == 'TRUE'
                else:
                    adj_data["adj_core"] = bool(row['adj_core'])
            if 'notes' in df.columns and not pd.isna(row['notes']):
                adj_data["notes"] = str(row['notes']).strip()
            
            result = create_adjudicator(adj_data)
            if result["success"]:
                results["created"] += 1
                results["details"].append({
                    "name": name,
                    "institution": adj_data.get('institution', 'None'),
                    "status": "Created"
                })
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_teams(filepath):
    """Process teams from spreadsheet (Format: id, institution, reference, short_reference, code name, use_institution_prefix, emoji, team_name (human), code name)"""
    try:
        df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
        
        # Check required columns
        required_cols = ['institution', 'code name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        df = df.fillna('')
        results = {
            "success": True,
            "total_rows": len(df),
            "created": 0,
            "errors": [],
            "details": []
        }
        
        # Group by institution to create teams
        for idx, row in df.iterrows():
            institution = str(row['institution']).strip()
            if not institution:
                results["errors"].append(f"Row {idx+2}: Missing institution")
                continue
            
            # Build team data
            team_data = {
                "institution": institution,
                "reference": row.get('reference', ''),
                "short_reference": row.get('short_reference', ''),
                "code name": str(row['code name']).strip(),
                "use_institution_prefix": row.get('use_institution_prefix', True),
                "emoji": row.get('emoji', ''),
                "team_name (human)": row.get('team_name (human)', '')
            }
            
            if not team_data["code name"]:
                results["errors"].append(f"Row {idx+2}: Missing code name")
                continue
            
            result = create_team(team_data)
            if result["success"]:
                results["created"] += 1
                results["details"].append({
                    "team_name": team_data["team_name (human)"] or team_data["code name"],
                    "institution": institution,
                    "code": team_data["code name"],
                    "status": "Created"
                })
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_speakers(filepath):
    """Process speakers from spreadsheet (Format: id, name, gender, email, phone, anonymous, emoji, team, categories, initials match)"""
    try:
        df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
        
        # Check required columns
        required_cols = ['name', 'team']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        df = df.fillna('')
        results = {
            "success": True,
            "total_rows": len(df),
            "created": 0,
            "errors": [],
            "details": []
        }
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            team = str(row['team']).strip()
            
            if not name or not team:
                results["errors"].append(f"Row {idx+2}: Missing name or team")
                continue
            
            # Build speaker data
            speaker_data = {
                "name": name,
                "team": team,
                "gender": row.get('gender', '') if not pd.isna(row.get('gender', '')) else '',
                "email": row.get('email', '') if not pd.isna(row.get('email', '')) else '',
                "phone": row.get('phone', '') if not pd.isna(row.get('phone', '')) else '',
                "anonymous": row.get('anonymous', False) if not pd.isna(row.get('anonymous', False)) else False,
                "initials match": row.get('initials match', '') if not pd.isna(row.get('initials match', '')) else ''
            }
            
            # Handle boolean for anonymous
            if 'anonymous' in df.columns and not pd.isna(row['anonymous']):
                if isinstance(row['anonymous'], str):
                    speaker_data["anonymous"] = row['anonymous'].strip().upper() == 'TRUE'
                else:
                    speaker_data["anonymous"] = bool(row['anonymous'])
            
            result = create_speaker(speaker_data)
            if result["success"]:
                results["created"] += 1
                results["details"].append({
                    "name": name,
                    "team": team,
                    "status": "Created"
                })
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Use CSV or Excel.', 'danger')
            return redirect(request.url)
        
        import_type = request.form.get('import_type')
        if not import_type:
            flash('Please select an import type', 'danger')
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process based on import type
        if import_type == 'institutions':
            results = process_institutions(filepath)
        elif import_type == 'adjudicators':
            results = process_adjudicators(filepath)
        elif import_type == 'teams':
            results = process_teams(filepath)
        elif import_type == 'speakers':
            results = process_speakers(filepath)
        else:
            flash('Invalid import type', 'danger')
            os.remove(filepath)
            return redirect(request.url)
        
        os.remove(filepath)
        
        if results["success"]:
            flash(f'Import complete! {results.get("created", 0)} items created.', 'success')
        else:
            flash(f'Import failed: {results.get("error", "Unknown error")}', 'danger')
        
        return render_template('index.html', results=results, import_type=import_type)
    
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "message": "Tabbycat Importer is running"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)