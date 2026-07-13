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

# Get Tabbycat credentials - IMPORTANT: Use ONLY the base URL
TABBYCAT_BASE_URL = os.getenv('TABBYCAT_URL', 'https://calicotab.com')
# Remove trailing slash if present
TABBYCAT_BASE_URL = TABBYCAT_BASE_URL.rstrip('/')
TABBYCAT_TOKEN = os.getenv('TABBYCAT_TOKEN', 'your-admin-token-here')

# The API endpoint uses the base URL + /api/v1/
TABBYCAT_API_URL = f"{TABBYCAT_BASE_URL}/api/v1"

print("=" * 60)
print("🔍 TABBYCAT IMPORTER - STARTUP CHECK")
print("=" * 60)
print(f"📡 TABBYCAT_BASE_URL: {TABBYCAT_BASE_URL}")
print(f"📡 TABBYCAT_API_URL: {TABBYCAT_API_URL}")
print(f"🔑 TABBYCAT_TOKEN: {TABBYCAT_TOKEN[:15]}... (first 15 chars)")
if 'your-tabbycat-instance' in TABBYCAT_BASE_URL or 'calicotab.com' not in TABBYCAT_BASE_URL:
    print("⚠️ Make sure TABBYCAT_URL is set to: https://calicotab.com")
print("=" * 60)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HEADERS = {
    "Authorization": f"Token {TABBYCAT_TOKEN}",
    "Content-Type": "application/json"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_code(code):
    if pd.isna(code) or str(code).strip() == '':
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(code).strip().upper())

def create_institution(name, code):
    """Create an institution in Tabbycat - CORRECT API endpoint"""
    # Use the API URL with trailing slash
    endpoint = f"{TABBYCAT_API_URL}/institutions/"
    clean_code = sanitize_code(code)
    
    if not clean_code:
        return {"success": False, "error": "Invalid code"}
    
    payload = {"name": str(name).strip(), "code": clean_code}
    
    print(f"🔍 POST: {endpoint}")
    print(f"   Payload: {payload}")
    
    try:
        response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=30)
        print(f"📊 Status: {response.status_code}")
        print(f"📝 Response: {response.text[:200]}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            return {"success": True, "url": data.get("url"), "code": clean_code}
        elif response.status_code == 400:
            if "already exists" in str(response.text).lower():
                # Try to find existing
                try:
                    get_response = requests.get(
                        f"{TABBYCAT_API_URL}/institutions/",
                        headers=HEADERS,
                        timeout=30
                    )
                    get_response.raise_for_status()
                    for inst in get_response.json():
                        if inst.get("code") == clean_code:
                            return {"success": True, "url": inst.get("url"), "code": clean_code, "existing": True}
                except:
                    pass
            return {"success": False, "error": f"API Error: {response.text}"}
        else:
            return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        print(f"❌ Exception: {e}")
        return {"success": False, "error": str(e)}

def get_institution_by_code(code):
    """Get institution URL by its code"""
    clean_code = sanitize_code(code)
    if not clean_code:
        return None
    
    if not hasattr(get_institution_by_code, 'cache'):
        get_institution_by_code.cache = {}
    
    if clean_code in get_institution_by_code.cache:
        return get_institution_by_code.cache[clean_code]
    
    try:
        response = requests.get(
            f"{TABBYCAT_API_URL}/institutions/",
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        for inst in response.json():
            if inst.get("code") == clean_code:
                get_institution_by_code.cache[clean_code] = inst.get("url")
                return inst.get("url")
        get_institution_by_code.cache[clean_code] = None
        return None
    except:
        return None

# [REST OF THE CODE - SAME AS BEFORE]
# All the other functions (create_team, create_adjudicator, create_speaker,
# process_institutions, process_adjudicators, process_teams, process_speakers,
# index route, health check) remain the same but use TABBYCAT_API_URL instead.

# I'll include the complete code in the full version below
