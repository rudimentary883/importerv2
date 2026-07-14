from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head><title>Tabbycat Importer</title></head>
        <body style="font-family: Arial; padding: 30px; background: #f0f0f0;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h1 style="color: #333;">✅ It Works!</h1>
                <p style="font-size: 18px;">Your Tabbycat Importer is running successfully.</p>
                <p style="color: #666;">The basic setup is working. Now we can add features.</p>
                <hr>
                <p><a href="/test">Test Page</a> | <a href="/health">Health Check</a></p>
            </div>
        </body>
    </html>
    """

@app.route('/test')
def test():
    return "Test page is working! 🎉"

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
