# Real-Time Multilingual Conversational Voice AI Campaign System

A secure, full-stack AI-powered system for Uganda's Presidential Election campaign that enables real-time voice conversations with voters using a cloned presidential voice, with support for multiple languages (English, Swahili, Luganda, and Runyankole).

## Features

### Admin Dashboard
- Secure login
- API configuration (Twilio, GPT-4)
- Voice upload and training with OpenVoice
- Multi-language management
- Conversation flow builder
- Voter list management
- Campaign scheduling

### Voice AI & Audio Engine
- Voice cloning with OpenVoice
- Automatic audio generation in multiple languages
- Organized audio storage

### Conversational AI Calling Engine
- Twilio integration for calls
- Real-time speech-to-text with Whisper
- Language and sentiment analysis with GPT-4
- Dynamic response selection
- Comprehensive data logging

### Reports & Live Monitoring
- Real-time dashboard
- Detailed call logs
- Exportable reports
- Analytics

## Technology Stack
- **Backend**: Python (Flask)
- **Frontend**: TailwindCSS
- **Voice Cloning**: OpenVoice
- **Speech Recognition**: Whisper
- **AI Understanding**: GPT-4
- **Telephony**: Twilio Programmable Voice
- **Database**: SQLite

## Getting Started

### Prerequisites
- Python 3.8+
- Docker (for deployment)
- Twilio account
- OpenAI API key

### Installation

1. Clone the repository
```
git clone https://github.com/VOXug/vox.git
cd vox
```

2. Create and activate a virtual environment
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Set up environment variables
```
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. Initialize the database
```
flask db init
flask db migrate
flask db upgrade
```

6. Run the development server
```
flask run
```

## Deployment

The application can be deployed using Docker:

```
docker-compose up -d
```

## License

[MIT License](LICENSE)

![VOX Platform](https://via.placeholder.com/800x400?text=VOX+Multilingual+Voice+AI+System)

## Features

- **Admin Dashboard**: Comprehensive management interface for campaigns, voters, and analytics
- **Voice Cloning**: Create natural-sounding voice models in multiple languages
- **Multilingual Support**: English, Swahili, Luganda, and Runyankole
- **Real-time Analysis**: Sentiment analysis and language detection during calls
- **Conversation Flow Management**: Visual editor for creating dynamic conversation paths
- **Voter Database**: Import, segment, and manage voter contact information
- **Reporting & Analytics**: Detailed insights on campaign performance and voter sentiment
- **Test Interface**: Test calls and conversation flows before deployment
- **Secure API Integration**: Twilio for telephony, OpenAI for language processing

## Tech Stack

### Backend
- **Framework**: Flask with Blueprints architecture
- **Database**: SQLAlchemy ORM with SQLite (dev) and PostgreSQL (prod)
- **Authentication**: Flask-Login with role-based access control
- **API Integration**: Twilio, OpenAI, ElevenLabs

### Frontend
- **HTML/CSS**: Responsive design with Tailwind CSS
- **JavaScript**: Interactive components and real-time updates
- **Visualization**: Chart.js for analytics, jsPlumb for flow editor

### AI Components
- **Natural Language Processing**: OpenAI GPT-4
- **Speech Recognition**: Whisper
- **Voice Synthesis**: OpenAI TTS, ElevenLabs, Google Cloud TTS
- **Sentiment Analysis**: Custom models trained on political discourse

### Infrastructure
- **Containerization**: Docker and docker-compose
- **Web Server**: Gunicorn with Nginx
- **Telephony**: Twilio Programmable Voice

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/VOXug/vox.git
cd vox
```

2. **Create and activate a virtual environment**
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. **Initialize the database**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. **Create an admin user**
```bash
flask shell
```

Then in the shell:
```python
from app import db
from app.models import User

admin = User(username='admin', email='admin@example.com', password='secure_password', is_admin=True)
db.session.add(admin)
db.session.commit()
exit()
```

7. **Run the application**
```bash
flask run
```

The application will be available at http://127.0.0.1:5000

## Detailed Setup

For a more comprehensive setup guide, including API integration details and troubleshooting tips, see [setup.txt](setup.txt).

## Deployment

The application can be deployed using Docker:

```bash
docker-compose build
docker-compose up -d
```

## Project Structure

```
vox/
├── app/                  # Application package
│   ├── api/              # API endpoints
│   ├── controllers/      # Route controllers
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   ├── static/           # Static assets
│   ├── templates/        # HTML templates
│   └── utils/            # Utility functions
├── migrations/           # Database migrations
├── tests/                # Test suite
├── .env.example          # Example environment variables
├── docker-compose.yml    # Docker configuration
├── Dockerfile            # Docker build instructions
├── requirements.txt      # Python dependencies
└── run.py                # Application entry point
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)

## Contact
DAX +256702448951 OR +256778415709 WHATSAPP ONLY

Project Link: [https://github.com/VOXug/vox}
