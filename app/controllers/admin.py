from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

from app import db
from app.models import (
    User, Language, VoiceModel, Campaign, 
    ConversationFlow, AudioClip, APIConfig
)
from app.forms.admin import (
    APIConfigForm, VoiceModelForm, LanguageForm, 
    ConversationFlowForm, CampaignForm
)
from app.utils.decorators import admin_required
from app.services.voice_service import process_voice_upload, train_voice_model

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard home page"""
    stats = {
        'users': User.query.count(),
        'campaigns': Campaign.query.count(),
        'active_campaigns': Campaign.query.filter_by(is_active=True).count(),
        'voice_models': VoiceModel.query.count(),
        'languages': Language.query.filter_by(is_active=True).count()
    }
    return render_template('admin/index.html', title='Admin Dashboard', stats=stats)


# API Configuration Management
@admin_bp.route('/api-config', methods=['GET', 'POST'])
@login_required
@admin_required
def api_config():
    """Manage API configurations (Twilio, OpenAI)"""
    form = APIConfigForm()
    
    if form.validate_on_submit():
        config = APIConfig.query.filter_by(name=form.name.data).first()
        
        if config:
            # Update existing config
            config.config_data = json.loads(form.config_data.data)
            config.is_active = form.is_active.data
            db.session.commit()
            flash(f'API configuration for {form.name.data} has been updated.', 'success')
        else:
            # Create new config
            new_config = APIConfig(
                name=form.name.data,
                config_data=json.loads(form.config_data.data),
                is_active=form.is_active.data
            )
            db.session.add(new_config)
            db.session.commit()
            flash(f'API configuration for {form.name.data} has been added.', 'success')
        
        return redirect(url_for('admin.api_config'))
    
    configs = APIConfig.query.all()
    return render_template('admin/api_config.html', title='API Configuration', form=form, configs=configs)


@admin_bp.route('/api-config/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_api_config(id):
    """Delete an API configuration"""
    config = APIConfig.query.get_or_404(id)
    db.session.delete(config)
    db.session.commit()
    flash(f'API configuration for {config.name} has been deleted.', 'success')
    return redirect(url_for('admin.api_config'))


# Voice Model Management
@admin_bp.route('/voice-models', methods=['GET', 'POST'])
@login_required
@admin_required
def voice_models():
    """Manage voice models"""
    form = VoiceModelForm()
    
    if form.validate_on_submit():
        if form.id.data:
            # Update existing model
            model = VoiceModel.query.get_or_404(form.id.data)
            model.name = form.name.data
            model.description = form.description.data
            model.is_active = form.is_active.data
            
            if form.voice_file.data:
                # Process new voice file upload
                filename = process_voice_upload(form.voice_file.data)
                if filename:
                    # Train or update the voice model
                    model_path = train_voice_model(filename, model.model_path)
                    if model_path:
                        model.model_path = model_path
                        flash('Voice model has been updated with new training data.', 'success')
            
            db.session.commit()
            flash(f'Voice model "{form.name.data}" has been updated.', 'success')
        else:
            # Create new model
            if form.voice_file.data:
                # Process voice file upload
                filename = process_voice_upload(form.voice_file.data)
                if filename:
                    # Train the voice model
                    model_path = train_voice_model(filename)
                    if model_path:
                        new_model = VoiceModel(
                            name=form.name.data,
                            description=form.description.data,
                            model_path=model_path,
                            is_active=form.is_active.data
                        )
                        db.session.add(new_model)
                        db.session.commit()
                        flash(f'Voice model "{form.name.data}" has been created.', 'success')
                    else:
                        flash('Failed to train voice model. Please try again.', 'danger')
                else:
                    flash('Failed to process voice file. Please try again.', 'danger')
            else:
                flash('Please upload a voice file to train the model.', 'warning')
        
        return redirect(url_for('admin.voice_models'))
    
    models = VoiceModel.query.all()
    return render_template('admin/voice_models.html', title='Voice Models', form=form, models=models)


@admin_bp.route('/voice-models/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_voice_model(id):
    """Delete a voice model"""
    model = VoiceModel.query.get_or_404(id)
    
    # Check if model is in use by any campaigns
    if Campaign.query.filter_by(voice_model_id=id).first():
        flash(f'Cannot delete voice model "{model.name}" as it is being used by one or more campaigns.', 'danger')
    else:
        # Delete the model file if it exists
        if os.path.exists(model.model_path):
            try:
                os.remove(model.model_path)
            except OSError:
                flash(f'Could not delete model file at {model.model_path}.', 'warning')
        
        db.session.delete(model)
        db.session.commit()
        flash(f'Voice model "{model.name}" has been deleted.', 'success')
    
    return redirect(url_for('admin.voice_models'))


# Language Management
@admin_bp.route('/languages', methods=['GET', 'POST'])
@login_required
@admin_required
def languages():
    """Manage supported languages"""
    form = LanguageForm()
    
    if form.validate_on_submit():
        if form.id.data:
            # Update existing language
            language = Language.query.get_or_404(form.id.data)
            language.name = form.name.data
            language.code = form.code.data
            language.is_active = form.is_active.data
            db.session.commit()
            flash(f'Language "{form.name.data}" has been updated.', 'success')
        else:
            # Create new language
            new_language = Language(
                name=form.name.data,
                code=form.code.data,
                is_active=form.is_active.data
            )
            db.session.add(new_language)
            db.session.commit()
            flash(f'Language "{form.name.data}" has been added.', 'success')
        
        return redirect(url_for('admin.languages'))
    
    languages = Language.query.all()
    return render_template('admin/languages.html', title='Languages', form=form, languages=languages)


@admin_bp.route('/languages/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_language(id):
    """Delete a language"""
    language = Language.query.get_or_404(id)
    
    # Check if language is in use by any audio clips
    if AudioClip.query.filter_by(language_id=id).first():
        flash(f'Cannot delete language "{language.name}" as it is being used by one or more audio clips.', 'danger')
    else:
        db.session.delete(language)
        db.session.commit()
        flash(f'Language "{language.name}" has been deleted.', 'success')
    
    return redirect(url_for('admin.languages'))


# User Management
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Manage users"""
    users = User.query.all()
    return render_template('admin/users.html', title='User Management', users=users)


@admin_bp.route('/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(id):
    """Toggle admin status for a user"""
    user = User.query.get_or_404(id)
    
    # Prevent removing admin status from the last admin
    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash('Cannot remove admin status from the last admin user.', 'danger')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f'Admin status for {user.username} has been {"granted" if user.is_admin else "revoked"}.', 'success')
    
    return redirect(url_for('admin.users'))
