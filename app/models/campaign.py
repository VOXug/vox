from datetime import datetime
from app import db

class Language(db.Model):
    """Model for supported languages in the system"""
    __tablename__ = 'languages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(10), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    audio_clips = db.relationship('AudioClip', backref='language', lazy='dynamic')
    
    def __repr__(self):
        return f'<Language {self.name}>'


class VoiceModel(db.Model):
    """Model for voice cloning models"""
    __tablename__ = 'voice_models'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    model_path = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    audio_clips = db.relationship('AudioClip', backref='voice_model', lazy='dynamic')
    
    def __repr__(self):
        return f'<VoiceModel {self.name}>'


class Campaign(db.Model):
    """Model for call campaigns"""
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    max_calls_per_day = db.Column(db.Integer, default=1000)
    max_calls_per_hour = db.Column(db.Integer, default=100)
    retry_attempts = db.Column(db.Integer, default=2)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    
    # Foreign keys
    voice_model_id = db.Column(db.Integer, db.ForeignKey('voice_models.id'), nullable=False)
    
    # Relationships
    voice_model = db.relationship('VoiceModel')
    conversation_flows = db.relationship('ConversationFlow', backref='campaign', lazy='dynamic')
    call_logs = db.relationship('CallLog', backref='campaign', lazy='dynamic')
    
    def __repr__(self):
        return f'<Campaign {self.name}>'


class ConversationFlow(db.Model):
    """Model for conversation flow structure"""
    __tablename__ = 'conversation_flows'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    flow_data = db.Column(db.JSON, nullable=False)  # Stores the entire flow structure
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    
    # Relationships
    audio_clips = db.relationship('AudioClip', backref='conversation_flow', lazy='dynamic')
    
    def __repr__(self):
        return f'<ConversationFlow {self.name}>'


class AudioClip(db.Model):
    """Model for audio clips used in conversations"""
    __tablename__ = 'audio_clips'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Float, nullable=True)  # Duration in seconds
    step_id = db.Column(db.String(64), nullable=False)  # ID of the step in the conversation flow
    sentiment = db.Column(db.String(20), nullable=True)  # positive, negative, neutral
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    language_id = db.Column(db.Integer, db.ForeignKey('languages.id'), nullable=False)
    conversation_flow_id = db.Column(db.Integer, db.ForeignKey('conversation_flows.id'), nullable=False)
    voice_model_id = db.Column(db.Integer, db.ForeignKey('voice_models.id'), nullable=False)
    
    def __repr__(self):
        return f'<AudioClip {self.name}>'
