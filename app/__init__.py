from flask import Flask
from flask_socketio import SocketIO
from .config import Config
from .database import init_tracking_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Initialize database
    init_tracking_db()
    
    # Register blueprints
    from .routes import main_bp
    app.register_blueprint(main_bp)
    
    return app, socketio