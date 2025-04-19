"""
Authentication routes for the VOX application
"""
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps

from app import db, login_manager
from app.models.user import User
from app.auth.forms import LoginForm, RegisterForm, ResetPasswordRequestForm, ResetPasswordForm
from app.utils.email import send_email

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Rate limiting for failed login attempts
login_attempts = {}

def check_rate_limit(ip_address):
    """
    Check if an IP address has exceeded the rate limit for failed login attempts
    Returns True if rate limited, False otherwise
    """
    now = datetime.utcnow()
    if ip_address in login_attempts:
        attempts = login_attempts[ip_address]
        # Remove attempts older than 15 minutes
        attempts = [attempt for attempt in attempts if now - attempt < timedelta(minutes=15)]
        login_attempts[ip_address] = attempts
        
        # If there are 5 or more attempts in the last 15 minutes, rate limit
        if len(attempts) >= 5:
            return True
    
    return False

def record_failed_attempt(ip_address):
    """Record a failed login attempt for an IP address"""
    now = datetime.utcnow()
    if ip_address not in login_attempts:
        login_attempts[ip_address] = []
    
    login_attempts[ip_address].append(now)

def admin_required(f):
    """Decorator to require admin access for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database"""
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Check for rate limiting
        ip_address = request.remote_addr
        if check_rate_limit(ip_address):
            flash('Too many failed login attempts. Please try again later.', 'danger')
            return render_template('auth/login.html', form=form)
        
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            # Successful login
            login_user(user, remember=form.remember_me.data)
            
            # Record login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Clear any failed login attempts
            if ip_address in login_attempts:
                del login_attempts[ip_address]
            
            # Redirect to the page the user was trying to access
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard.index')
            
            return redirect(next_page)
        else:
            # Failed login
            record_failed_attempt(ip_address)
            flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Check if registration is enabled
    if not current_app.config.get('REGISTRATION_ENABLED', False):
        flash('Registration is currently disabled', 'info')
        return redirect(url_for('auth.login'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return render_template('auth/register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            is_admin=False,
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Handle password reset request"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # Generate reset token
            token = generate_reset_token(user.id)
            
            # Send reset email
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_email(
                recipient=user.email,
                subject='Reset Your Password',
                template='auth/email/reset_password',
                user=user,
                reset_url=reset_url
            )
        
        # Always show success message to prevent email enumeration
        flash('If your email address exists in our database, you will receive a password reset link shortly.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Verify token
    user_id = verify_reset_token(token)
    if not user_id:
        flash('Invalid or expired reset token', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.login'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        
        flash('Your password has been reset successfully', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

@auth_bp.route('/profile')
@login_required
def profile():
    """Display user profile"""
    return render_template('auth/profile.html')

def generate_reset_token(user_id):
    """Generate a JWT token for password reset"""
    expiration = datetime.utcnow() + timedelta(hours=1)
    payload = {
        'user_id': user_id,
        'exp': expiration
    }
    
    secret_key = current_app.config['SECRET_KEY']
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    
    return token

def verify_reset_token(token):
    """Verify a password reset token"""
    secret_key = current_app.config['SECRET_KEY']
    
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload['user_id']
    except:
        return None
