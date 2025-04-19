from datetime import datetime
from app import db

class Voter(db.Model):
    """Model for voter contact information"""
    __tablename__ = 'voters'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    name = db.Column(db.String(128), nullable=True)
    location = db.Column(db.String(128), nullable=True)
    language_preference = db.Column(db.String(20), nullable=True)
    do_not_call = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    call_logs = db.relationship('CallLog', backref='voter', lazy='dynamic')
    
    def __repr__(self):
        return f'<Voter {self.phone_number}>'


class VoterList(db.Model):
    """Model for managing lists of voters"""
    __tablename__ = 'voter_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    voter_list_entries = db.relationship('VoterListEntry', backref='voter_list', lazy='dynamic', cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', secondary='campaign_voter_lists', backref=db.backref('voter_lists', lazy='dynamic'))
    
    def __repr__(self):
        return f'<VoterList {self.name}>'


class VoterListEntry(db.Model):
    """Model for mapping voters to voter lists"""
    __tablename__ = 'voter_list_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    voter_list_id = db.Column(db.Integer, db.ForeignKey('voter_lists.id'), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey('voters.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add unique constraint to prevent duplicate entries
    __table_args__ = (db.UniqueConstraint('voter_list_id', 'voter_id', name='unique_voter_in_list'),)
    
    def __repr__(self):
        return f'<VoterListEntry {self.id}>'


# Association table for many-to-many relationship between campaigns and voter lists
campaign_voter_lists = db.Table('campaign_voter_lists',
    db.Column('campaign_id', db.Integer, db.ForeignKey('campaigns.id'), primary_key=True),
    db.Column('voter_list_id', db.Integer, db.ForeignKey('voter_lists.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)
