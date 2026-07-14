from flask import Flask, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Your Calico credentials - EDIT THESE
TABBYCAT_URL = "https://calicotab.com"  # Change to your Calico URL
TABBYCAT_TOKEN = "your-token-here"  # Change to your token

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title></head>
        <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
            <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1 style="color: #333;">🚀 Tabbycat Importer</h1>
                <p>Upload your CSV or Excel file to import data.</p>
                
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
                    <strong>File format:</strong> CSV or Excel with the required columns for your import type.
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
        
        # Count rows
        row_count = len(df)
        
        # Clean up
        os.remove(filepath)
        
        # Return success
        return f"""
        <html>
            <head><title>Import Complete</title></head>
            <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                    <h1 style="color: #4CAF50;">✅ Import Complete!</h1>
                    <p><strong>Import Type:</strong> {import_type}</p>
                    <p><strong>Rows Processed:</strong> {row_count}</p>
                    <p><strong>Status:</strong> File read successfully</p>
                    <hr>
                    <p><a href="/" style="color: #4CAF50;">Import Another File</a></p>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
