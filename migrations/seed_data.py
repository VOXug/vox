"""
Seed data script to populate the database with initial data
"""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User
from app.models.campaign import Campaign, ConversationFlow, VoiceModel
from app.models.voter import Voter
from app.models.call_log import CallLog

def seed_data():
    """Seed the database with initial data"""
    print("Seeding database with initial data...")
    app = create_app()
    with app.app_context():
        # Create admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            print("Admin user created")
        
        # Create demo user
        if not User.query.filter_by(username='demo').first():
            demo = User(
                username='demo',
                email='demo@example.com',
                password_hash=generate_password_hash('demo123'),
                is_admin=False,
                created_at=datetime.utcnow()
            )
            db.session.add(demo)
            print("Demo user created")
        
        # Create voice models
        voice_models = [
            {
                'name': 'Default English Voice',
                'description': 'Default voice model for English language',
                'language_code': 'en',
                'provider': 'OpenAI',
                'model_id': 'alloy',
                'is_default': True
            },
            {
                'name': 'Default Swahili Voice',
                'description': 'Default voice model for Swahili language',
                'language_code': 'sw',
                'provider': 'OpenAI',
                'model_id': 'echo',
                'is_default': True
            },
            {
                'name': 'Default Luganda Voice',
                'description': 'Default voice model for Luganda language',
                'language_code': 'lg',
                'provider': 'OpenAI',
                'model_id': 'fable',
                'is_default': True
            },
            {
                'name': 'Default Runyankole Voice',
                'description': 'Default voice model for Runyankole language',
                'language_code': 'ny',
                'provider': 'OpenAI',
                'model_id': 'nova',
                'is_default': True
            }
        ]
        
        for model_data in voice_models:
            if not VoiceModel.query.filter_by(name=model_data['name']).first():
                model = VoiceModel(
                    name=model_data['name'],
                    description=model_data['description'],
                    language_code=model_data['language_code'],
                    provider=model_data['provider'],
                    model_id=model_data['model_id'],
                    is_default=model_data['is_default'],
                    created_at=datetime.utcnow()
                )
                db.session.add(model)
                print(f"Voice model created: {model_data['name']}")
        
        # Create demo campaign
        if not Campaign.query.filter_by(name='Demo Campaign').first():
            # Get the voice models we just created
            english_voice = VoiceModel.query.filter_by(language_code='en', is_default=True).first()
            
            campaign = Campaign(
                name='Demo Campaign',
                description='A demo campaign for testing purposes',
                status='active',
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                voice_model_id=english_voice.id if english_voice else None,
                created_by=1,  # Admin user
                created_at=datetime.utcnow()
            )
            db.session.add(campaign)
            db.session.flush()  # Flush to get the campaign ID
            
            # Create a conversation flow for the campaign
            flow = ConversationFlow(
                campaign_id=campaign.id,
                name='Demo Flow',
                description='A simple conversation flow for the demo campaign',
                initial_greeting='Hello! This is a demo call from the VOX campaign system. How are you today?',
                is_active=True,
                flow_data="""
                {
                    "nodes": [
                        {
                            "id": "start",
                            "type": "start",
                            "text": "Hello! This is a demo call from the VOX campaign system. How are you today?",
                            "next": "response"
                        },
                        {
                            "id": "response",
                            "type": "input",
                            "text": "Are you interested in learning more about our campaign?",
                            "options": [
                                {"value": "yes", "next": "interested"},
                                {"value": "no", "next": "not_interested"}
                            ]
                        },
                        {
                            "id": "interested",
                            "type": "message",
                            "text": "Great! We'll send you more information about our campaign soon.",
                            "next": "end"
                        },
                        {
                            "id": "not_interested",
                            "type": "message",
                            "text": "No problem. Thank you for your time.",
                            "next": "end"
                        },
                        {
                            "id": "end",
                            "type": "end",
                            "text": "Thank you for taking our call. Have a great day!"
                        }
                    ]
                }
                """,
                start_node_id="start",
                created_at=datetime.utcnow()
            )
            db.session.add(flow)
            print("Demo campaign and flow created")
        
        # Create sample voters
        sample_voters = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'phone_number': '+12025550001',
                'email': 'john.doe@example.com',
                'language_preference': 'en',
                'location': 'Kampala'
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'phone_number': '+12025550002',
                'email': 'jane.smith@example.com',
                'language_preference': 'en',
                'location': 'Entebbe'
            },
            {
                'first_name': 'Michael',
                'last_name': 'Johnson',
                'phone_number': '+12025550003',
                'email': 'michael.johnson@example.com',
                'language_preference': 'sw',
                'location': 'Jinja'
            },
            {
                'first_name': 'Sarah',
                'last_name': 'Williams',
                'phone_number': '+12025550004',
                'email': 'sarah.williams@example.com',
                'language_preference': 'lg',
                'location': 'Gulu'
            },
            {
                'first_name': 'David',
                'last_name': 'Brown',
                'phone_number': '+12025550005',
                'email': 'david.brown@example.com',
                'language_preference': 'ny',
                'location': 'Mbarara'
            }
        ]
        
        for voter_data in sample_voters:
            if not Voter.query.filter_by(phone_number=voter_data['phone_number']).first():
                voter = Voter(
                    first_name=voter_data['first_name'],
                    last_name=voter_data['last_name'],
                    phone_number=voter_data['phone_number'],
                    email=voter_data['email'],
                    language_preference=voter_data['language_preference'],
                    location=voter_data['location'],
                    created_at=datetime.utcnow()
                )
                db.session.add(voter)
                print(f"Sample voter created: {voter_data['first_name']} {voter_data['last_name']}")
        
        # Commit all changes
        db.session.commit()
        print("Database seeded successfully!")

if __name__ == '__main__':
    seed_data()
