import re
import os
import json
from flask import current_app
import pandas as pd
from werkzeug.utils import secure_filename

from app.models import APIConfig

def validate_phone_number(phone_number):
    """
    Validate and format a phone number to E.164 format for Uganda (+256)
    Returns formatted number or None if invalid
    """
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', phone_number)
    
    # Check if it's a valid Uganda number
    if len(digits_only) == 10 and digits_only.startswith('0'):
        # Convert local format (0772123456) to international format (+256772123456)
        return f"+256{digits_only[1:]}"
    elif len(digits_only) == 9 and not digits_only.startswith('0'):
        # Handle format without leading 0 (772123456)
        return f"+256{digits_only}"
    elif len(digits_only) == 12 and digits_only.startswith('256'):
        # Already in international format without +
        return f"+{digits_only}"
    elif len(digits_only) == 13 and digits_only.startswith('2560'):
        # Fix common mistake where people keep the 0 after country code
        return f"+256{digits_only[4:]}"
    elif len(digits_only) >= 11 and digits_only.startswith('256'):
        # Already has country code, just add +
        return f"+{digits_only}"
    
    # If it already has + and country code
    if phone_number.startswith('+256') and len(re.sub(r'\D', '', phone_number)) >= 11:
        return phone_number
    
    # Invalid format
    return None


def get_twilio_config():
    """Get Twilio configuration from database"""
    config = APIConfig.query.filter_by(name='twilio', is_active=True).first()
    if config and config.config_data:
        return config.config_data
    return None


def get_openai_config():
    """Get OpenAI configuration from database"""
    config = APIConfig.query.filter_by(name='openai', is_active=True).first()
    if config and config.config_data:
        return config.config_data
    return None


def get_openvoice_config():
    """Get OpenVoice configuration from database"""
    config = APIConfig.query.filter_by(name='openvoice', is_active=True).first()
    if config and config.config_data:
        return config.config_data
    return None


def allowed_file(filename, allowed_extensions):
    """Check if a file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, folder, allowed_extensions=None):
    """
    Save an uploaded file to the specified folder
    Returns the filename if successful, None otherwise
    """
    if file and file.filename:
        if allowed_extensions and not allowed_file(file.filename, allowed_extensions):
            return None
        
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid collisions
        name, ext = os.path.splitext(filename)
        timestamp = pd.Timestamp.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"{name}_{timestamp}{ext}"
        
        file_path = os.path.join(folder, new_filename)
        file.save(file_path)
        return new_filename
    
    return None


def process_voter_list(file_path):
    """
    Process an uploaded voter list file (CSV, TXT, XLS, XLSX)
    Returns a list of validated phone numbers
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext == '.csv':
            df = pd.read_csv(file_path)
        elif file_ext == '.txt':
            df = pd.read_csv(file_path, header=None, names=['phone_number'])
        elif file_ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file_path)
        else:
            return []
        
        # Find the column containing phone numbers
        phone_col = None
        for col in df.columns:
            if 'phone' in col.lower() or 'mobile' in col.lower() or 'contact' in col.lower() or 'tel' in col.lower():
                phone_col = col
                break
        
        if not phone_col and len(df.columns) == 1:
            # If there's only one column, assume it's the phone number
            phone_col = df.columns[0]
        
        if not phone_col:
            return []
        
        # Extract and validate phone numbers
        phone_numbers = []
        for number in df[phone_col]:
            if pd.notna(number):
                formatted_number = validate_phone_number(str(number))
                if formatted_number:
                    phone_numbers.append(formatted_number)
        
        # Remove duplicates
        return list(set(phone_numbers))
    
    except Exception as e:
        current_app.logger.error(f"Error processing voter list: {str(e)}")
        return []


def format_duration(seconds):
    """Format seconds into a human-readable duration string"""
    if seconds is None:
        return "N/A"
    
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"
