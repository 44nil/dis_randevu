import os
import json
import base64
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
@auth_bp.route('/login')
def login():
    # Eğer kullanıcı zaten içerideyse (ve çıkış yapmıyorsa) yönlendir
    force_signout = request.args.get('force_signout')
    
    if current_user.is_authenticated and force_signout != 'true':
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    
    # Clerk Publishable Key'i template'e gönder
    clerk_pub_key = os.environ.get('CLERK_PUBLISHABLE_KEY')
    
    # force_signout parametresini template'e ilet (string olarak 'true' veya 'false')
    return render_template('login.html', 
                         clerk_pub_key=clerk_pub_key, 
                         force_signout=force_signout or 'false')

def decode_clerk_token(token):
    try:
        parts = token.split('.')
        if len(parts) < 2: return None
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except: return None

def get_clerk_user_email(user_id):
    try:
        secret_key = os.environ.get('CLERK_SECRET_KEY')
        if not secret_key: return None
        
        headers = {'Authorization': f'Bearer {secret_key}'}
        response = requests.get(f"https://api.clerk.com/v1/users/{user_id}", headers=headers)
        
        if response.status_code == 200:
            emails = response.json().get('email_addresses', [])
            if emails: return emails[0].get('email_address')
    except Exception as e:
        print(f"API Error: {e}")
    return None

@auth_bp.route('/auth/check-clerk')
def check_clerk_session():
    token = request.cookies.get('__session')
    if not token:
        return redirect(url_for('auth.login'))

    payload = decode_clerk_token(token)
    if not payload or 'sub' not in payload:
        return redirect(url_for('auth.login'))
        
    email = get_clerk_user_email(payload['sub'])
    if not email:
        flash("Email alınamadı.", "error")
        return redirect(url_for('auth.login'))

    print(f"--- GİRİŞ YAPAN: {email} ---")

    # Rol Belirleme
    target_role = 'patient'
    if email == 'esranildogan@gmail.com':
        target_role = 'admin'

    # Kullanıcı İşlemleri
    user = User.query.filter_by(username=email).first()
    if not user:
        user = User(username=email, email=email, full_name=email.split('@')[0], role=target_role, password_hash="clerk")
        db.session.add(user)
        db.session.commit()
    elif user.role != target_role:
        user.role = target_role
        db.session.commit()

    login_user(user)
    
    return redirect(url_for('admin.dashboard' if user.role == 'admin' else 'user.dashboard'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    # Login sayfasına 'force_signout=true' parametresi ile gönder
    # Bu sayede login.html açıldığında Clerk.signOut() çalışacak
    return redirect(url_for('auth.login', force_signout='true'))