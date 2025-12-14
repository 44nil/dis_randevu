from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import Appointment
from app.extensions import db
from datetime import datetime, timedelta

user_bp = Blueprint('user', __name__)

# İşlem Süreleri
PROCEDURE_DURATIONS = {
    'Muayene': 30,
    'Diş Taşı Temizliği': 30,
    'Diş Çekimi': 30,
    'Dolgu': 45,
    'Kanal Tedavisi': 60,
    'İmplant': 90
}

def check_conflict(start, end):
    """Çakışma kontrolü: İptal edilmemiş herhangi bir randevu ile çakışıyor mu?"""
    return Appointment.query.filter(
        Appointment.start_time < end,
        Appointment.end_time > start,
        Appointment.status != 'cancelled'
    ).first()

# --- HASTA PANELİ (DASHBOARD) ---
@user_bp.route('/dashboard')
@login_required
def dashboard():
    # Sadece hastanın KENDİ randevularını getir
    my_appointments = Appointment.query.filter_by(user_id=current_user.id)\
        .order_by(Appointment.start_time.desc()).all()
    
    # DÜZELTME: Dosya ismi 'user_dashboard_new.html' olarak güncellendi
    # VEKLEME: Template içinde kullanılan 'today' değişkeni eklendi
    return render_template('user_dashboard_new.html', 
                         user=current_user, 
                         appointments=my_appointments,
                         today=datetime.now()) 

# --- TAKVİM VERİSİ (GİZLİLİK FİLTRELİ) ---
@user_bp.route('/api/user/calendar')
@login_required
def get_calendar_events():
    # Tüm aktif randevuları çek
    all_appointments = Appointment.query.filter(Appointment.status != 'cancelled').all()
    events = []
    
    for appt in all_appointments:
        # Bu randevu benim mi?
        is_mine = (appt.user_id == current_user.id)
        
        events.append({
            'id': appt.id,
            # Başkasının randevusuysa ismini gizle, 'DOLU' yaz
            'title': appt.title if is_mine else "DOLU", 
            'start': appt.start_time.isoformat(),
            'end': appt.end_time.isoformat(),
            # Benimki İndigo (Mavi), Başkasınınki Gri
            'color': '#4f46e5' if is_mine else '#9ca3af', 
            'display': 'block',
            'extendedProps': {
                'is_mine': is_mine # Frontend'de tıklamayı yönetmek için
            }
        })
        
    return jsonify(events)

# --- RANDEVU OLUŞTURMA ---
@user_bp.route('/api/user/appointment/create', methods=['POST'])
@login_required
def create_appointment():
    try:
        data = request.form
        date_part = data.get('appt_date')
        time_part = data.get('appt_time')
        title = data.get('title')
        
        # 1. Zamanı Hesapla
        start_time = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M')
        duration = PROCEDURE_DURATIONS.get(title, 30)
        end_time = start_time + timedelta(minutes=duration)
        
        # 2. Çakışma Kontrolü
        if check_conflict(start_time, end_time):
            return jsonify({'status': 'error', 'message': 'Seçtiğiniz saat maalesef dolu. Lütfen başka bir saat seçin.'}), 400
            
        # 3. Kayıt (current_user.id ile otomatik bağla)
        new_appt = Appointment(
            title=title,
            start_time=start_time,
            end_time=end_time,
            user_id=current_user.id,     # <--- Otomatik Bağlantı
            guest_name=current_user.full_name, 
            guest_phone=current_user.phone,
            notes=data.get('notes'),
            status='confirmed'
        )
        
        db.session.add(new_appt)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Randevunuz başarıyla oluşturuldu!'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500