from datetime import datetime
from app import db

class CallLog(db.Model):
    """Model for tracking call history and results"""
    __tablename__ = 'call_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    call_sid = db.Column(db.String(64), nullable=True, unique=True, index=True)  # Twilio call SID
    status = db.Column(db.String(20), nullable=False)  # initiated, ringing, in-progress, completed, failed, busy, no-answer
    duration = db.Column(db.Integer, nullable=True)  # Call duration in seconds
    language_used = db.Column(db.String(20), nullable=True)  # Language code used in the call
    sentiment = db.Column(db.String(20), nullable=True)  # positive, negative, neutral
    transcript = db.Column(db.Text, nullable=True)  # Full conversation transcript
    recording_url = db.Column(db.String(255), nullable=True)  # URL to the call recording if available
    notes = db.Column(db.Text, nullable=True)  # Additional notes or information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # When the call was initiated
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)  # When the call ended
    
    # Foreign keys
    voter_id = db.Column(db.Integer, db.ForeignKey('voters.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    
    # Relationships
    call_events = db.relationship('CallEvent', backref='call_log', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CallLog {self.id} - {self.status}>'


class CallEvent(db.Model):
    """Model for tracking detailed events within a call"""
    __tablename__ = 'call_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # audio-played, speech-detected, transcription, response-selected, etc.
    event_data = db.Column(db.JSON, nullable=True)  # Additional event data in JSON format
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    call_log_id = db.Column(db.Integer, db.ForeignKey('call_logs.id'), nullable=False)
    
    def __repr__(self):
        return f'<CallEvent {self.id} - {self.event_type}>'


class APIConfig(db.Model):
    """Model for storing API configurations"""
    __tablename__ = 'api_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)  # twilio, openai, etc.
    config_data = db.Column(db.JSON, nullable=False)  # API keys and configuration in JSON format
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<APIConfig {self.name}>'
