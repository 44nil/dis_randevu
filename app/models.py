from app.extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default='patient') # 'admin' veya 'patient'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # İlişkiler
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    treatments = db.relationship('Treatment', backref='patient', lazy=True)

    # --- EKLENEN KISIM ---
    @property
    def is_admin(self):
        return self.role == 'admin'

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Kayıtlı hasta ise ID
    
    title = db.Column(db.String(100)) # İşlem Adı
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    
    # Misafir Bilgileri
    guest_name = db.Column(db.String(100))
    guest_phone = db.Column(db.String(20))
    
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='confirmed')

    def to_dict(self):
        """Takvim için veri formatı"""
        display_title = self.guest_name if self.guest_name else (self.patient.full_name if self.patient else "Dolu")
        
        return {
            'id': self.id,
            'title': display_title, 
            'start': self.start_time.isoformat(),
            'end': self.end_time.isoformat(),
            'color': '#dc3545' if self.status == 'cancelled' else '#4f46e5',
            'extendedProps': {
                'procedure': self.title,
                'guest_name': self.guest_name or (self.patient.full_name if self.patient else ""),
                'guest_phone': self.guest_phone or (self.patient.phone if self.patient else ""),
                'notes': self.notes or "",
                'user_id': self.user_id 
            }
        }

class Treatment(db.Model):
    """Hasta Tedavi Geçmişi Tablosu"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    procedure_name = db.Column(db.String(100)) # Yapılan İşlem
    tooth_number = db.Column(db.String(10))    # Diş No
    cost = db.Column(db.Float, default=0.0)    # Ücret
    payment_received = db.Column(db.Float, default=0.0) # Alınan Ödeme
    notes = db.Column(db.Text)                 # Doktor notları
    date = db.Column(db.DateTime, default=datetime.utcnow)