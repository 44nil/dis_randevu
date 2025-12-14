from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Appointment, User, Treatment
from app.extensions import db
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

# --- İŞLEM SÜRELERİ ---
PROCEDURE_DURATIONS = {
    'Muayene': 30, 'Diş Taşı Temizliği': 30, 'Diş Çekimi': 30,
    'Dolgu': 45, 'Kanal Tedavisi': 60, 'İmplant': 90
}

def check_conflict(start, end, ignore_id=None):
    query = Appointment.query.filter(Appointment.start_time < end, Appointment.end_time > start, Appointment.status != 'cancelled')
    if ignore_id: query = query.filter(Appointment.id != ignore_id)
    return query.first()

# --- DASHBOARD ---
@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    todays_appointments = Appointment.query.filter(Appointment.start_time >= today_start, Appointment.start_time <= today_end, Appointment.status != 'cancelled').order_by(Appointment.start_time).all()
    monthly_treatments = Treatment.query.filter(Treatment.date >= today.replace(day=1)).all()
    monthly_income = sum(t.cost for t in monthly_treatments)
    total_patients = User.query.filter_by(role='patient').count()
    return render_template('admin_dashboard.html', appointments=todays_appointments, monthly_income=monthly_income, total_patients=total_patients, today=today)

# --- TAKVİM ---
@admin_bp.route('/admin/calendar')
@login_required
def calendar_view():
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    return render_template('sessions_calendar.html')

# --- RANDEVU LİSTESİ ---
@admin_bp.route('/admin/appointments-list')
@login_required
def appointment_list():
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    appointments = Appointment.query.order_by(Appointment.start_time.desc()).all()
    return render_template('admin_appointments.html', appointments=appointments)

# --- HASTA LİSTESİ ---
@admin_bp.route('/admin/patients-list')
@login_required
def patients_list():
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    patients = User.query.filter_by(role='patient').order_by(User.created_at.desc()).all()
    return render_template('admin_patients.html', patients=patients)

# --- HASTA DETAY ---
@admin_bp.route('/admin/patient/<int:user_id>')
@login_required
def patient_detail(user_id):
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    patient = User.query.get_or_404(user_id)
    all_patients = User.query.filter_by(role='patient').order_by(User.full_name).all()
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.start_time.desc()).all()
    treatments = Treatment.query.filter_by(user_id=user_id).order_by(Treatment.date.desc()).all()
    return render_template('admin_patient_detail.html', patient=patient, all_patients=all_patients, appointments=appointments, treatments=treatments)

# --- YENİ EKLENEN: RANDEVU DETAY ---
@admin_bp.route('/admin/appointment/<int:appt_id>')
@login_required
def appointment_detail(appt_id):
    if not current_user.is_admin: return redirect(url_for('user.dashboard'))
    appointment = Appointment.query.get_or_404(appt_id)
    # Eğer kayıtlı hasta ise bilgilerini al, değilse None döner
    patient = appointment.patient
    return render_template('admin_appointment_detail.html', appointment=appointment, patient=patient)

# --- API ---
@admin_bp.route('/api/appointments')
@login_required
def get_appointments():
    if not current_user.is_admin: return jsonify({'error': 'Unauthorized'}), 403
    appointments = Appointment.query.filter(Appointment.status != 'cancelled').all()
    events = []
    for appt in appointments:
        display_title = appt.guest_name if appt.guest_name else (appt.patient.full_name if appt.patient else "Bilinmeyen")
        events.append({
            'id': appt.id, 'title': f"{display_title} - {appt.title}",
            'start': appt.start_time.isoformat(), 'end': appt.end_time.isoformat(),
            'extendedProps': {
                'guest_name': appt.guest_name or (appt.patient.full_name if appt.patient else ""),
                'guest_phone': appt.guest_phone or (appt.patient.phone if appt.patient else ""),
                'procedure': appt.title, 'notes': appt.notes or ""
            }
        })
    return jsonify(events)

@admin_bp.route('/api/appointments/create', methods=['POST'])
@login_required
def create_appointment():
    try:
        data = request.form
        start_time = datetime.strptime(f"{data.get('appt_date')} {data.get('appt_time')}", '%Y-%m-%d %H:%M')
        duration = PROCEDURE_DURATIONS.get(data.get('title'), 30)
        end_time = start_time + timedelta(minutes=duration)
        if check_conflict(start_time, end_time): return jsonify({'status': 'error', 'message': 'Bu saatte başka randevu var!'}), 400
        user_id = None
        if data.get('guest_phone'):
            user = User.query.filter_by(username=data.get('guest_phone')).first()
            if not user:
                user = User(username=data.get('guest_phone'), email=f"{data.get('guest_phone')}@hasta.com", full_name=data.get('guest_name'), phone=data.get('guest_phone'), role='patient', password_hash="auto")
                db.session.add(user)
                db.session.flush()
            user_id = user.id
        new_appt = Appointment(title=data.get('title'), start_time=start_time, end_time=end_time, user_id=user_id, guest_name=data.get('guest_name'), guest_phone=data.get('guest_phone'), notes=data.get('notes'), status='confirmed')
        db.session.add(new_appt)
        db.session.commit()
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
        if data.get('guest_name'): appt.guest_name = data.get('guest_name')
        if data.get('guest_phone'): appt.guest_phone = data.get('guest_phone')
        if data.get('title'): appt.title = data.get('title')
        if data.get('notes'): appt.notes = data.get('notes')
        if data.get('appt_date') and data.get('appt_time'):
            new_start = datetime.strptime(f"{data.get('appt_date')} {data.get('appt_time')}", '%Y-%m-%d %H:%M')
            duration = PROCEDURE_DURATIONS.get(appt.title, 30)
            new_end = new_start + timedelta(minutes=duration)
            if check_conflict(new_start, new_end, ignore_id=id): return jsonify({'status': 'error', 'message': 'Çakışma var!'}), 400
            appt.start_time = new_start
            appt.end_time = new_end
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Güncellendi.'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/api/appointments/<int:id>/delete', methods=['POST'])
@login_required
def delete_appointment(id):
    db.session.delete(Appointment.query.get_or_404(id))
    db.session.commit()
    return jsonify({'status': 'success'})

@admin_bp.route('/api/patient/<int:user_id>/add_treatment', methods=['POST'])
@login_required
def add_treatment(user_id):
    try:
        data = request.form
        db.session.add(Treatment(user_id=user_id, procedure_name=data.get('procedure_name'), tooth_number=data.get('tooth_number'), cost=float(data.get('cost') or 0), payment_received=float(data.get('payment_received') or 0), notes=data.get('notes'), date=datetime.now()))
        db.session.commit()
        return redirect(url_for('admin.patient_detail', user_id=user_id))
    except Exception as e: return f"Hata: {str(e)}", 500

# --- AYARLAR SAYFASI ---
@admin_bp.route('/admin/settings')
@login_required
def settings():
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    return render_template('admin_settings.html')