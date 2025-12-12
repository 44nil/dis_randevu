from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Appointment, User, Treatment
from app.extensions import db
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

# --- İŞLEM SÜRELERİ (Dakika) ---
PROCEDURE_DURATIONS = {
    'Muayene': 30,             
    'Diş Taşı Temizliği': 30,
    'Diş Çekimi': 30,
    'Dolgu': 45,
    'Kanal Tedavisi': 60,
    'İmplant': 90
}

# --- ÇAKIŞMA KONTROLÜ ---
def check_conflict(start, end, ignore_id=None):
    query = Appointment.query.filter(
        Appointment.start_time < end,
        Appointment.end_time > start,
        Appointment.status != 'cancelled'
    )
    if ignore_id: query = query.filter(Appointment.id != ignore_id)
    return query.first()

# --- DASHBOARD (GELİŞMİŞ VERSİYON) ---
@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    
    # 1. BUGÜNKÜ İSTATİSTİKLER
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Bugünkü randevular
    todays_appointments = Appointment.query.filter(
        Appointment.start_time >= today_start,
        Appointment.start_time <= today_end,
        Appointment.status != 'cancelled'
    ).order_by(Appointment.start_time).all()
    
    # 2. FİNANSAL ÖZET (Basit Ciro Hesabı)
    # Bu ay yapılan tedavilerin toplam ücreti
    first_day_month = today.replace(day=1)
    monthly_treatments = Treatment.query.filter(Treatment.date >= first_day_month).all()
    monthly_income = sum(t.cost for t in monthly_treatments)
    
    # 3. GENEL İSTATİSTİKLER
    total_patients = User.query.filter_by(role='patient').count()
    
    return render_template('admin_dashboard.html', 
                         appointments=todays_appointments,
                         monthly_income=monthly_income,
                         total_patients=total_patients,
                         today=today)

@admin_bp.route('/admin/calendar')
@login_required
def calendar_view():
    return render_template('sessions_calendar.html')

@admin_bp.route('/admin/appointments-list')
@login_required
def appointment_list():
    appointments = Appointment.query.order_by(Appointment.start_time.desc()).all()
    return render_template('admin_appointments.html', appointments=appointments)

# --- HASTA KARTI (DETAY) SAYFASI ---
@admin_bp.route('/admin/patient/<int:user_id>')
@login_required
def patient_detail(user_id):
    patient = User.query.get_or_404(user_id)
    # Hastanın tüm geçmiş randevuları
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.start_time.desc()).all()
    # Hastanın tüm tedavileri
    treatments = Treatment.query.filter_by(user_id=user_id).order_by(Treatment.date.desc()).all()
    return render_template('admin_patient_detail.html', patient=patient, appointments=appointments, treatments=treatments)

# --- API ROTALARI ---
@admin_bp.route('/api/appointments')
def get_appointments():
    appointments = Appointment.query.filter(Appointment.status != 'cancelled').all()
    return jsonify([appt.to_dict() for appt in appointments])

# app/routes/admin_routes.py içindeki create_appointment fonksiyonunu bununla değiştirin:

@admin_bp.route('/api/appointments/create', methods=['POST'])
@login_required
def create_appointment():
    try:
        data = request.form
        date_part = data.get('appt_date')
        time_part = data.get('appt_time')
        title = data.get('title')
        guest_name = data.get('guest_name')
        guest_phone = data.get('guest_phone')
        
        # 1. Tarih ve Süre
        start_time = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M')
        duration = PROCEDURE_DURATIONS.get(title, 30)
        end_time = start_time + timedelta(minutes=duration)
        
        # 2. Çakışma Kontrolü
        if check_conflict(start_time, end_time):
            return jsonify({'status': 'error', 'message': 'Bu saatte başka randevu var!'}), 400
            
        # 3. HASTA KAYDI (Optimize Edildi)
        user = User.query.filter_by(username=guest_phone).first()
        if not user:
            user = User(
                username=guest_phone,
                email=f"{guest_phone}@hasta.com",
                full_name=guest_name,
                phone=guest_phone,
                role='patient',
                password_hash="auto_generated"
            )
            db.session.add(user)
            db.session.flush() # <--- HIZLANDIRICI: Commit yapmadan ID üretir
            
        # 4. RANDEVUYU KAYDET
        new_appt = Appointment(
            title=title,
            start_time=start_time,
            end_time=end_time,
            user_id=user.id,
            guest_name=guest_name,
            guest_phone=guest_phone,
            notes=data.get('notes'),
            status='confirmed'
        )
        
        db.session.add(new_appt)
        db.session.commit() # <--- TEK SEFERDE KAYIT (Daha hızlı)
        
        return jsonify({'status': 'success', 'message': 'Randevu oluşturuldu!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
@admin_bp.route('/api/appointments/<int:id>/update', methods=['POST'])
@login_required
def update_appointment(id):
    appt = Appointment.query.get_or_404(id)
    try:
        data = request.form
        
        # Temel Bilgileri Güncelle
        if data.get('title'): appt.title = data.get('title')
        if data.get('guest_name'): appt.guest_name = data.get('guest_name')
        if data.get('guest_phone'): appt.guest_phone = data.get('guest_phone')
        if data.get('notes'): appt.notes = data.get('notes')
            
        # Tarih/Saat Değişimi
        if data.get('appt_date') and data.get('appt_time'):
            new_start = datetime.strptime(f"{data.get('appt_date')} {data.get('appt_time')}", '%Y-%m-%d %H:%M')
            duration = PROCEDURE_DURATIONS.get(appt.title, 30)
            new_end = new_start + timedelta(minutes=duration)
            
            if check_conflict(new_start, new_end, ignore_id=id):
                return jsonify({'status': 'error', 'message': 'Bu saatte çakışma var!'}), 400
                
            appt.start_time = new_start
            appt.end_time = new_end
        
        # --- EKSİK HASTA KAYDI DÜZELTME ---
        # Eğer bu randevunun bir hasta kaydı yoksa, şimdi oluştur.
        current_phone = appt.guest_phone
        if not appt.user_id and current_phone:
            user = User.query.filter_by(username=current_phone).first()
            if not user:
                user = User(
                    username=current_phone,
                    email=f"{current_phone}@hasta.com",
                    full_name=appt.guest_name,
                    phone=current_phone,
                    role='patient',
                    password_hash="auto_generated"
                )
                db.session.add(user)
                db.session.flush()
            appt.user_id = user.id

        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Güncellendi.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/api/appointments/<int:id>/delete', methods=['POST'])
@login_required
def delete_appointment(id):
    appt = Appointment.query.get_or_404(id)
    db.session.delete(appt)
    db.session.commit()
    return jsonify({'status': 'success'})

@admin_bp.route('/api/patient/<int:user_id>/add_treatment', methods=['POST'])
@login_required
def add_treatment(user_id):
    try:
        data = request.form
        new_treatment = Treatment(
            user_id=user_id,
            procedure_name=data.get('procedure_name'),
            tooth_number=data.get('tooth_number'),
            cost=float(data.get('cost') or 0),
            payment_received=float(data.get('payment_received') or 0),
            notes=data.get('notes'),
            date=datetime.now()
        )
        db.session.add(new_treatment)
        db.session.commit()
        return redirect(url_for('admin.patient_detail', user_id=user_id))
    except Exception as e:
        return f"Hata: {str(e)}", 500