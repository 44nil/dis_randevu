from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 1. Veritabanı tablolarını oluştur
    db.create_all()
    print("Veritabanı tabloları oluşturuldu.")

    # 2. Yönetici (Diş Hekimi) Kullanıcısını oluştur
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='hekim@klinik.com',
            full_name='Diş Hekimi',
            role='admin',
            password_hash=generate_password_hash('123456') # Şifre: 123456
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin kullanıcısı oluşturuldu. Kullanıcı adı: admin, Şifre: 123456")
    else:
        print("Admin kullanıcısı zaten var.")