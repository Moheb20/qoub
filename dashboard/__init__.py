from flask import Flask
from dashboard.routes import dashboard_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your-super-secret-key'
    app.register_blueprint(dashboard_bp)
    return app
