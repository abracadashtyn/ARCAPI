import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config.local import LocalConfig
from config.digitalocean import DigitalOceanConfig

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=None):
    app = Flask(__name__)
    # Auto-detect config based on environment
    if config_class is None:
        env = os.environ.get('FLASK_ENV', 'development')
        if env == 'production':
            config_class = DigitalOceanConfig
        else:
            config_class = LocalConfig
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.models import bp as models_bp
    app.register_blueprint(models_bp)

    from app.tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp)

    from app.api.v0 import bp as api_bp
    app.register_blueprint(api_bp)

    return app