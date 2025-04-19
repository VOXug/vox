import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure the app
    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_mapping(
            SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
            SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URI', 'sqlite:///vox.db'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TWILIO_ACCOUNT_SID=os.environ.get('TWILIO_ACCOUNT_SID', ''),
            TWILIO_AUTH_TOKEN=os.environ.get('TWILIO_AUTH_TOKEN', ''),
            TWILIO_PHONE_NUMBER=os.environ.get('TWILIO_PHONE_NUMBER', ''),
            OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY', ''),
            UPLOAD_FOLDER=os.path.join(app.root_path, 'static/uploads'),
            AUDIO_FOLDER=os.path.join(app.root_path, 'static/audio'),
            MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB max upload
        )
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Ensure upload folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    CORS(app)
    
    # Register blueprints
    from app.controllers.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    from app.controllers.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    from app.controllers.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    from app.api.routes import api_bp
    app.register_blueprint(api_bp)
    
    # Register error handlers
    from app.controllers.errors import register_error_handlers
    register_error_handlers(app)
    
    # Shell context
    @app.shell_context_processor
    def make_shell_context():
        return {'db': db, 'app': app}
    
    return app
