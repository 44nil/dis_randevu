from flask import Flask
from app.extensions import db, login_manager
from flask_migrate import Migrate
from app.models import User
from flask_wtf.csrf import CSRFProtect # Güvenlik modülü

def create_app():
    app = Flask(__name__)
    
    # Ayarlar
    app.config['SECRET_KEY'] = 'gizli-anahtar-123'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dishekimi.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Eklentileri Başlat
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate = Migrate(app, db)
    
    # CSRF Korumasını Aktif Et (Kritik Nokta)
    csrf = CSRFProtect(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprint'leri Kayıt Et
    from app.routes.admin_routes import admin_bp
    from app.routes.user_routes import user_bp
    from app.routes.auth_routes import auth_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)

    return app