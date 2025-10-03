# blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import os, secrets, threading, requests
from datetime import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

# -------------------------
# Supabase Configuration
# -------------------------
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# -------------------------
# Google OAuth Configuration
# -------------------------
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = os.getenv('GOOGLE_DISCOVERY_URL', 'https://accounts.google.com/.well-known/openid-configuration')

auth_bp = Blueprint('auth', __name__)

def get_google_provider_cfg():
    try:
        return requests.get(GOOGLE_DISCOVERY_URL).json()
    except Exception as e:
        print("Google provider config error:", e)
        return None

# -------------------------
# Email Configuration
# -------------------------
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'

def send_email(to_email, subject, body):
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("Email config missing, skipping")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        if EMAIL_USE_TLS:
            server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False

def send_welcome_email(user_email, user_name):
    subject = "Welcome to 4 shoe!"
    body = f"<h2>Welcome {user_name}!</h2><p>Thank you for registering at 4 shoe. <a href='http://localhost:5000'>Start Shopping</a></p>"
    return send_email(user_email, subject, body)

def send_login_confirmation_email(user_email, user_name):
    subject = "Login confirmation - 4 shoe"
    body = f"<p>Hello {user_name}, you logged in at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
    return send_email(user_email, subject, body)

# -------------------------
# Routes: Register & Login
# -------------------------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords match
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template('register.html')
        
        if not supabase:
            flash("Database not configured", "error")
            return render_template('register.html')
        try:
            signup_resp = supabase.auth.sign_up({'email': email, 'password': password})
            if signup_resp.user:
                # Insert into users table with default role='user'
                supabase.table('users').insert({
                    'supabase_user_id': signup_resp.user.id,
                    'name': email.split('@')[0],  # Use part of email as name if not provided
                    'email': email,
                    'role': 'user',
                    'provider': 'email'
                }).execute()
                threading.Thread(target=send_welcome_email, args=(email, email.split('@')[0]), daemon=True).start()
                flash("Registration successful. Please login.", "success")
                return redirect(url_for('auth.login'))
            else:
                flash("Signup failed", "error")
        except Exception as e:
            print("Register error:", e)
            flash("Registration error. Check console.", "error")
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not supabase:
            flash("Database not configured", "error")
            return render_template('login.html')
        try:
            resp = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if resp.user:
                # Ambil data lengkap dari tabel users (integer id!)
                user_resp = supabase.table('users').select('*').eq('supabase_user_id', resp.user.id).execute()
                if user_resp.data:
                    user_data = user_resp.data[0]
                    session['user'] = {
                        'id': user_data['id'],                # <- integer ID
                        'supabase_user_id': user_data['supabase_user_id'],  # UUID Supabase
                        'email': user_data['email'],
                        'name': user_data['name'],
                        'role': user_data.get('role', 'user'),
                        'address': user_data.get('address', ''),
                        'login_time': datetime.now().isoformat()
                    }
                else:
                    flash("User not found in database", "error")
                    return redirect(url_for('auth.login'))

                threading.Thread(target=send_login_confirmation_email, args=(email, user_data['name']), daemon=True).start()
                flash("Login successful", "success")
                return redirect(url_for('home'))
            else:
                flash("Invalid email or password", "error")
        except Exception as e:
            print("Login error:", e)
            flash("Login failed. Check console.", "error")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    if supabase:
        supabase.auth.sign_out()
    flash("Logged out", "info")
    return redirect(url_for('home'))

# -------------------------
# Google OAuth
# -------------------------
@auth_bp.route('/google-login')
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash('Google OAuth not configured', 'error')
        return redirect(url_for('auth.login'))
    google_cfg = get_google_provider_cfg()
    auth_endpoint = google_cfg.get("authorization_endpoint")
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': url_for('auth.google_callback', _external=True),
        'scope': 'openid email profile',
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return redirect(f"{auth_endpoint}?{urlencode(params)}")

@auth_bp.route('/google/callback')
def google_callback():
    try:
        code = request.args.get('code')
        if not code:
            flash("Authorization code not received", "error")
            return redirect(url_for('auth.login'))

        google_cfg = get_google_provider_cfg()
        token_endpoint = google_cfg.get("token_endpoint")
        token_resp = requests.post(token_endpoint, data={
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': url_for('auth.google_callback', _external=True)
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')

        userinfo_endpoint = google_cfg.get("userinfo_endpoint")
        userinfo_resp = requests.get(userinfo_endpoint, headers={'Authorization': f'Bearer {access_token}'})
        userinfo_resp.raise_for_status()
        user_info = userinfo_resp.json()
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])

        # Cek user di Supabase
        user_resp = supabase.table('users').select('*').eq('email', email).execute()
        if user_resp.data:
            user_data = user_resp.data[0]
            session['user'] = {
                'id': user_data['id'],                # <- integer ID
                'supabase_user_id': user_data['supabase_user_id'],
                'email': user_data['email'],
                'name': user_data['name'],
                'role': user_data.get('role', 'user'),
                'provider': user_data.get('provider', 'google'),
                'login_time': datetime.now().isoformat()
            }
        else:
            # Buat user baru di tabel users
            signup_resp = supabase.auth.sign_up({'email': email, 'password': secrets.token_urlsafe(16)})
            insert_resp = supabase.table('users').insert({
                'supabase_user_id': signup_resp.user.id,
                'name': name,
                'email': email,
                'role': 'user',
                'provider': 'google'
            }).execute()

            user_data = insert_resp.data[0]
            session['user'] = {
                'id': user_data['id'],                # <- integer ID
                'supabase_user_id': user_data['supabase_user_id'],
                'email': user_data['email'],
                'name': user_data['name'],
                'role': user_data.get('role', 'user'),
                'provider': 'google',
                'login_time': datetime.now().isoformat()
            }

        threading.Thread(target=send_welcome_email, args=(email, name), daemon=True).start()
        threading.Thread(target=send_login_confirmation_email, args=(email, name), daemon=True).start()
        flash(f"Welcome {name}!", "success")
        return redirect(url_for('home'))

    except Exception as e:
        print("Google callback error:", e)
        flash("Google login error", "error")
        return redirect(url_for('auth.login'))
