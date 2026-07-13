import os
import re
import warnings
warnings.filterwarnings('ignore')
import requests
import pandas as pd
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
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
    if pd.isna(code) or str(code).strip() == '':
        return ''
    # Remove any special characters, keep only letters and numbers
    clean = re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())
    return clean

def create_institution(name, code):
    """Create an institution in Tabbycat"""
    endpoint = f"{TABBYCAT_URL}/api/v1/institutions"
    clean_code = sanitize_code(code)
    
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
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

def process_institutions(filepath):
    """Process institutions from spreadsheet (Format: id, name, code)"""
    try:
        # Read the file
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Log what columns we found
        print(f"Columns found: {df.columns.tolist()}")
        print(f"Number of rows: {len(df)}")
        
        # Check required columns - make case-insensitive
        df.columns = [col.strip().lower() for col in df.columns]
        
        required_cols = ['name', 'code']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        # Clean the data
        df = df.fillna('')
        
        results = {
            "success": True,
            "total_rows": len(df),
            "created": 0,
            "errors": [],
            "details": []
        }
        
        # Process each row
        for idx, row in df.iterrows():
            # Get name and code
            name = str(row['name']).strip()
            code = str(row['code']).strip()
            
            # Skip empty rows
            if not name or not code:
                results["errors"].append(f"Row {idx+2}: Missing name or code (name='{name}', code='{code}')")
                continue
            
            print(f"Processing: {name} ({code})")
            
            result = create_institution(name, code)
            if result["success"]:
                results["created"] += 1
                status = "Already existed" if result.get("existing") else "Created"
                results["details"].append(f"{name} ({code}) - {status}")
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        # Free memory
        del df
        gc.collect()
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def get_institution_by_code(code):
    """Get institution URL by its code with caching"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    if not hasattr(get_institution_by_code, 'cache'):
        get_institution_by_code.cache = {}
    
    if clean_code in get_institution_by_code.cache:
        return get_institution_by_code.cache[clean_code]
    
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
                get_institution_by_code.cache[clean_code] = inst.get("url")
                return inst.get("url")
        get_institution_by_code.cache[clean_code] = None
        return None
    except:
        return None

def create_team(team_data):
    """Create a team in Tabbycat"""
    endpoint = f"{TABBYCAT_URL}/api/v1/teams"
    institution_code = sanitize_code(str(team_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code)
    
    if not inst_url:
        return {"success": False, "error": f"Institution '{institution_code}' not found"}
    
    team_name = team_data.get('team_name (human)', '')
    if not team_name or pd.isna(team_name):
        team_name = team_data.get('code name', '')
    
    payload = {
        "name": str(team_name).strip(),
        "institution": inst_url,
        "use_institution_prefix": bool(team_data.get('use_institution_prefix', True))
    }
    
    if team_data.get('reference') and not pd.isna(team_data.get('reference')):
        payload["reference"] = str(team_data.get('reference')).strip()
    if team_data.get('short_reference') and not pd.isna(team_data.get('short_reference')):
        payload["short_reference"] = str(team_data.get('short_reference')).strip()
    if team_data.get('emoji') and not pd.isna(team_data.get('emoji')):
        payload["emoji"] = str(team_data.get('emoji')).strip()
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

def create_adjudicator(adj_data):
    """Create an adjudicator in Tabbycat"""
    endpoint = f"{TABBYCAT_URL}/api/v1/adjudicators"
    institution_code = sanitize_code(str(adj_data.get('institution', '')))
    inst_url = get_institution_by_code(institution_code) if institution_code else None
    
    payload = {"name": str(adj_data.get('name', '')).strip()}
    
    if inst_url:
        payload["institution"] = inst_url
    if adj_data.get('email') and not pd.isna(adj_data.get('email')):
        payload["email"] = str(adj_data.get('email')).strip()
    if adj_data.get('gender') and not pd.isna(adj_data.get('gender')):
        payload["gender"] = str(adj_data.get('gender')).strip()
    if adj_data.get('base_score') is not None and not pd.isna(adj_data.get('base_score')):
        try:
            payload["base_score"] = float(adj_data.get('base_score'))
        except:
            pass
    if adj_data.get('independent') is not None and not pd.isna(adj_data.get('independent')):
        if isinstance(adj_data.get('independent'), str):
            payload["independent"] = adj_data.get('independent').strip().upper() == 'TRUE'
        else:
            payload["independent"] = bool(adj_data.get('independent'))
    if adj_data.get('adj_core') is not None and not pd.isna(adj_data.get('adj_core')):
        if isinstance(adj_data.get('adj_core'), str):
            payload["adj_core"] = adj_data.get('adj_core').strip().upper() == 'TRUE'
        else:
            payload["adj_core"] = bool(adj_data.get('adj_core'))
    if adj_data.get('notes') and not pd.isna(adj_data.get('notes')):
        payload["notes"] = str(adj_data.get('notes')).strip()
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

def create_speaker(speaker_data):
    """Create a speaker in Tabbycat"""
    team_name = str(speaker_data.get('team', '')).strip()
    endpoint = f"{TABBYCAT_URL}/api/v1/teams"
    
    try:
        response = requests.get(endpoint, headers=HEADERS, timeout=30)
        response.raise_for_status()
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
        if speaker_data.get('phone') and not pd.isna(speaker_data.get('phone')):
            speaker_payload["phone"] = str(speaker_data.get('phone')).strip()
        if speaker_data.get('anonymous') is not None and not pd.isna(speaker_data.get('anonymous')):
            if isinstance(speaker_data.get('anonymous'), str):
                speaker_payload["anonymous"] = speaker_data.get('anonymous').strip().upper() == 'TRUE'
            else:
                speaker_payload["anonymous"] = bool(speaker_data.get('anonymous'))
        if speaker_data.get('initials match') and not pd.isna(speaker_data.get('initials match')):
            speaker_payload["initials_match"] = str(speaker_data.get('initials match')).strip()
        
        speaker_endpoint = f"{team_url}/speakers"
        response = requests.post(speaker_endpoint, json=speaker_payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

def process_adjudicators(filepath):
    """Process adjudicators from spreadsheet"""
    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        df.columns = [col.strip().lower() for col in df.columns]
        
        if 'name' not in df.columns:
            return {"success": False, "error": "Missing required column: 'name'"}
        
        df = df.fillna('')
        results = {"success": True, "total_rows": len(df), "created": 0, "errors": [], "details": []}
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            if not name:
                results["errors"].append(f"Row {idx+2}: Missing name")
                continue
            
            adj_data = {"name": name}
            
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
                results["details"].append(f"{name} ({adj_data.get('institution', 'No institution')})")
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        del df
        gc.collect()
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def process_teams(filepath):
    """Process teams from spreadsheet"""
    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        df.columns = [col.strip().lower() for col in df.columns]
        
        required_cols = ['institution', 'code name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        df = df.fillna('')
        results = {"success": True, "total_rows": len(df), "created": 0, "errors": [], "details": []}
        
        for idx, row in df.iterrows():
            institution = str(row['institution']).strip()
            if not institution:
                results["errors"].append(f"Row {idx+2}: Missing institution")
                continue
            
            team_data = {
                "institution": institution,
                "reference": row.get('reference', '') if not pd.isna(row.get('reference', '')) else '',
                "short_reference": row.get('short_reference', '') if not pd.isna(row.get('short_reference', '')) else '',
                "code name": str(row['code name']).strip(),
                "use_institution_prefix": row.get('use_institution_prefix', True) if not pd.isna(row.get('use_institution_prefix', True)) else True,
                "emoji": row.get('emoji', '') if not pd.isna(row.get('emoji', '')) else '',
                "team_name (human)": row.get('team_name (human)', '') if not pd.isna(row.get('team_name (human)', '')) else ''
            }
            
            if not team_data["code name"]:
                results["errors"].append(f"Row {idx+2}: Missing code name")
                continue
            
            result = create_team(team_data)
            if result["success"]:
                results["created"] += 1
                team_display = team_data["team_name (human)"] or team_data["code name"]
                results["details"].append(f"{team_display} ({institution})")
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        del df
        gc.collect()
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def process_speakers(filepath):
    """Process speakers from spreadsheet"""
    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        df.columns = [col.strip().lower() for col in df.columns]
        
        required_cols = ['name', 'team']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"success": False, "error": f"Missing columns: {', '.join(missing_cols)}"}
        
        df = df.fillna('')
        results = {"success": True, "total_rows": len(df), "created": 0, "errors": [], "details": []}
        
        for idx, row in df.iterrows():
            name = str(row['name']).strip()
            team = str(row['team']).strip()
            
            if not name or not team:
                results["errors"].append(f"Row {idx+2}: Missing name or team")
                continue
            
            speaker_data = {
                "name": name,
                "team": team,
                "gender": row.get('gender', '') if not pd.isna(row.get('gender', '')) else '',
                "email": row.get('email', '') if not pd.isna(row.get('email', '')) else '',
                "phone": row.get('phone', '') if not pd.isna(row.get('phone', '')) else '',
                "anonymous": row.get('anonymous', False) if not pd.isna(row.get('anonymous', False)) else False,
                "initials match": row.get('initials match', '') if not pd.isna(row.get('initials match', '')) else ''
            }
            
            if 'anonymous' in df.columns and not pd.isna(row['anonymous']):
                if isinstance(row['anonymous'], str):
                    speaker_data["anonymous"] = row['anonymous'].strip().upper() == 'TRUE'
                else:
                    speaker_data["anonymous"] = bool(row['anonymous'])
            
            result = create_speaker(speaker_data)
            if result["success"]:
                results["created"] += 1
                results["details"].append(f"{name} → {team}")
            else:
                results["errors"].append(f"Row {idx+2}: {result.get('error', 'Unknown error')}")
        
        del df
        gc.collect()
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        
        try:
            os.remove(filepath)
        except:
            pass
        
        if results["success"]:
            flash(f'✅ Import complete! {results.get("created", 0)} items created.', 'success')
        else:
            flash(f'❌ Import failed: {results.get("error", "Unknown error")}', 'danger')
        
        return render_template('index.html', results=results, import_type=import_type)
    
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "message": "Tabbycat Importer is running"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
