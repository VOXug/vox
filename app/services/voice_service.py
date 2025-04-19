import os
import tempfile
from flask import current_app
import numpy as np
from pydub import AudioSegment
import subprocess
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

from app.utils.helpers import get_openvoice_config

def process_voice_upload(file_obj):
    """
    Process an uploaded voice file
    Returns the filename if successful, None otherwise
    """
    if not file_obj:
        return None
    
    try:
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'voice_samples')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save the uploaded file
        filename = secure_filename(file_obj.filename)
        # Add unique identifier to filename to avoid collisions
        name, ext = os.path.splitext(filename)
        unique_id = uuid.uuid4().hex[:8]
        new_filename = f"{name}_{unique_id}{ext}"
        
        file_path = os.path.join(upload_dir, new_filename)
        file_obj.save(file_path)
        
        # Validate the audio file
        try:
            audio = AudioSegment.from_file(file_path)
            # Convert to WAV format if needed
            if ext.lower() != '.wav':
                wav_path = os.path.join(upload_dir, f"{name}_{unique_id}.wav")
                audio.export(wav_path, format="wav")
                os.remove(file_path)  # Remove the original file
                file_path = wav_path
                new_filename = os.path.basename(wav_path)
            
            # Ensure audio is in the correct format for training (16kHz, mono)
            if audio.channels > 1:
                audio = audio.set_channels(1)
            if audio.frame_rate != 16000:
                audio = audio.set_frame_rate(16000)
                audio.export(file_path, format="wav")
            
            return new_filename
        except Exception as e:
            current_app.logger.error(f"Error processing audio file: {str(e)}")
            # Remove the file if it's invalid
            if os.path.exists(file_path):
                os.remove(file_path)
            return None
    
    except Exception as e:
        current_app.logger.error(f"Error saving voice file: {str(e)}")
        return None


def train_voice_model(voice_samples, model_name, language_code='en', provider='elevenlabs', description=None, user_id=None):
    """
    Train a voice model using the provided voice samples
    Returns a dictionary with model information if successful, None otherwise
    
    Parameters:
    - voice_samples: List of paths to voice sample files
    - model_name: Name for the voice model
    - language_code: Language code (en, sw, lg, ny)
    - provider: Voice provider (elevenlabs, openai, google)
    - description: Optional description for the model
    - user_id: ID of the user creating the model
    """
    if not voice_samples or len(voice_samples) == 0:
        current_app.logger.error("No voice samples provided for training")
        return None
    
    if not model_name or len(model_name.strip()) == 0:
        current_app.logger.error("No model name provided")
        return None
    
    try:
        # Create models directory if it doesn't exist
        models_dir = os.path.join(current_app.config['MODELS_FOLDER'])
        os.makedirs(models_dir, exist_ok=True)
        
        # Generate a unique model ID
        model_id = uuid.uuid4().hex
        model_dir = os.path.join(models_dir, f"voice_model_{model_id}")
        os.makedirs(model_dir, exist_ok=True)
        
        # Log the training request
        current_app.logger.info(f"Training voice model '{model_name}' with {len(voice_samples)} samples using {provider}")
        
        # Determine which provider to use and call the appropriate training function
        provider = provider.lower()
        if provider == 'elevenlabs':
            result = _train_with_elevenlabs(voice_samples, model_name, model_dir, language_code)
        elif provider == 'openai':
            # OpenAI doesn't currently support custom voice training, so we'll use a default voice
            result = _setup_openai_voice(model_name, model_dir, language_code)
        elif provider == 'google':
            result = _train_with_google(voice_samples, model_name, model_dir, language_code)
        else:
            current_app.logger.error(f"Unsupported voice provider: {provider}")
            return None
        
        if not result:
            return None
        
        # Save model metadata
        metadata = {
            'name': model_name,
            'description': description or f"Voice model for {language_code}",
            'language_code': language_code,
            'provider': provider,
            'model_id': result.get('provider_model_id', model_id),
            'created_at': datetime.utcnow().isoformat(),
            'created_by': user_id,
            'sample_count': len(voice_samples),
            'status': result.get('status', 'completed'),
            'path': model_dir
        }
        
        # Save metadata to a file
        with open(os.path.join(model_dir, 'metadata.json'), 'w') as f:
            import json
            json.dump(metadata, f, indent=2)
        
        # Create a database entry for the voice model
        from app.models import VoiceModel
        from app import db
        
        voice_model = VoiceModel(
            name=model_name,
            description=metadata['description'],
            language_code=language_code,
            provider=provider.capitalize(),
            model_id=metadata['model_id'],
            path=model_dir,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(voice_model)
        db.session.commit()
        
        # Return the model information
        return {
            'id': voice_model.id,
            'name': voice_model.name,
            'provider': voice_model.provider,
            'model_id': voice_model.model_id,
            'language_code': voice_model.language_code,
            'status': metadata['status']
        }
    
    except Exception as e:
        current_app.logger.error(f"Error training voice model: {str(e)}")
        return None


def _train_with_elevenlabs(voice_samples, model_name, model_dir, language_code):
    """
    Train a voice model using ElevenLabs API
    """
    import requests
    from app.utils.helpers import get_elevenlabs_config
    
    try:
        # Get ElevenLabs API key
        elevenlabs_config = get_elevenlabs_config()
        if not elevenlabs_config or 'api_key' not in elevenlabs_config:
            current_app.logger.error("ElevenLabs API key not found in configuration")
            return None
        
        # Prepare the voice samples
        files = []
        for i, sample_path in enumerate(voice_samples):
            if os.path.exists(sample_path):
                files.append(
                    ('files', (f'sample_{i}.mp3', open(sample_path, 'rb'), 'audio/mpeg'))
                )
        
        if not files:
            current_app.logger.error("No valid voice samples found")
            return None
        
        # API endpoint for voice creation
        url = "https://api.elevenlabs.io/v1/voices/add"
        
        # Request headers
        headers = {
            "Accept": "application/json",
            "xi-api-key": elevenlabs_config['api_key']
        }
        
        # Request data
        data = {
            "name": model_name,
            "labels": '{"accent":"' + language_code + '"}'
        }
        
        # Make the request
        current_app.logger.info(f"Sending request to ElevenLabs API with {len(files)} samples")
        response = requests.post(url, headers=headers, data=data, files=files)
        
        if response.status_code == 200:
            result = response.json()
            voice_id = result.get('voice_id')
            
            if not voice_id:
                current_app.logger.error("Voice ID not found in ElevenLabs response")
                return None
            
            # Save the response for reference
            with open(os.path.join(model_dir, 'elevenlabs_response.json'), 'w') as f:
                import json
                json.dump(result, f, indent=2)
            
            current_app.logger.info(f"Voice model created successfully with ID: {voice_id}")
            return {
                'provider_model_id': voice_id,
                'status': 'completed'
            }
        else:
            current_app.logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        current_app.logger.error(f"Error training with ElevenLabs: {str(e)}")
        return None


def _setup_openai_voice(model_name, model_dir, language_code):
    """
    Set up an OpenAI voice (no custom training, just configuration)
    """
    try:
        # OpenAI doesn't support custom voice training, so we'll use a default voice
        # based on the language code
        
        # Map language codes to OpenAI voices
        voice_map = {
            'en': 'alloy',  # English
            'sw': 'echo',   # Swahili
            'lg': 'fable',  # Luganda
            'ny': 'nova'    # Runyankole
        }
        
        # Get the voice for the language
        voice = voice_map.get(language_code, 'alloy')
        
        # Save the configuration
        config = {
            'voice': voice,
            'model': 'tts-1',
            'language_code': language_code
        }
        
        with open(os.path.join(model_dir, 'openai_config.json'), 'w') as f:
            import json
            json.dump(config, f, indent=2)
        
        current_app.logger.info(f"OpenAI voice configured: {voice}")
        return {
            'provider_model_id': voice,
            'status': 'completed'
        }
    
    except Exception as e:
        current_app.logger.error(f"Error setting up OpenAI voice: {str(e)}")
        return None


def _train_with_google(voice_samples, model_name, model_dir, language_code):
    """
    Train a voice model using Google Cloud Text-to-Speech API
    """
    try:
        # This is a placeholder for Google Cloud TTS custom voice implementation
        # In a real implementation, you would use the Google Cloud TTS client library
        current_app.logger.warning("Google Cloud TTS custom voice training not yet implemented")
        
        # For now, we'll simulate a successful training
        model_id = f"google-{uuid.uuid4().hex[:8]}"
        
        # Save a dummy configuration
        config = {
            'model_id': model_id,
            'language_code': language_code,
            'status': 'pending'  # In reality, Google's training would be asynchronous
        }
        
        with open(os.path.join(model_dir, 'google_config.json'), 'w') as f:
            import json
            json.dump(config, f, indent=2)
        
        current_app.logger.info(f"Simulated Google voice model creation: {model_id}")
        return {
            'provider_model_id': model_id,
            'status': 'pending'
        }
    
    except Exception as e:
        current_app.logger.error(f"Error training with Google: {str(e)}")
        return None


def generate_audio_clip(text, voice_model_id, language_code='en'):
    """
    Generate an audio clip from text using the specified voice model
    Returns the path to the generated audio file if successful, None otherwise
    """
    if not text or not voice_model_id:
        current_app.logger.error("Missing text or voice model ID")
        return None
    
    try:
        # Create audio directory if it doesn't exist
        audio_dir = os.path.join(current_app.config['AUDIO_FOLDER'])
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate a unique filename for the audio clip
        audio_filename = f"clip_{uuid.uuid4().hex}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        
        # Get voice model details from database
        from app.models import VoiceModel
        voice_model = VoiceModel.query.get(voice_model_id)
        
        if not voice_model:
            current_app.logger.error(f"Voice model with ID {voice_model_id} not found")
            return None
        
        # Log the request
        current_app.logger.info(f"Generating audio for: '{text[:50]}...' using model: {voice_model.name}")
        
        # Determine which provider to use based on the voice model
        provider = voice_model.provider.lower() if voice_model.provider else 'openai'
        
        if provider == 'openai':
            return _generate_with_openai(text, voice_model, audio_path, language_code)
        elif provider == 'elevenlabs':
            return _generate_with_elevenlabs(text, voice_model, audio_path, language_code)
        elif provider == 'google':
            return _generate_with_google_tts(text, voice_model, audio_path, language_code)
        else:
            current_app.logger.error(f"Unsupported voice provider: {provider}")
            return _generate_fallback_audio(text, audio_path)
    
    except Exception as e:
        current_app.logger.error(f"Error generating audio clip: {str(e)}")
        return _generate_fallback_audio(text, audio_path.replace('.mp3', '.wav'))


def _generate_with_openai(text, voice_model, audio_path, language_code):
    """
    Generate audio using OpenAI's Text-to-Speech API
    """
    from app.utils.helpers import get_openai_config
    from openai import OpenAI
    
    try:
        # Get OpenAI API key
        openai_config = get_openai_config()
        if not openai_config or 'api_key' not in openai_config:
            current_app.logger.error("OpenAI API key not found in configuration")
            return None
        
        # Initialize the OpenAI client
        client = OpenAI(
            api_key=openai_config['api_key'],
            timeout=30.0,  # Longer timeout for audio generation
            max_retries=3
        )
        
        # Get the voice name from the model_id field (e.g., "alloy", "echo", "fable", etc.)
        voice = voice_model.model_id
        if not voice or voice.lower() not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
            voice = "alloy"  # Default voice
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",  # or "tts-1-hd" for higher quality
            voice=voice,
            input=text
        )
        
        # Save the audio file
        response.stream_to_file(audio_path)
        
        return audio_path
    
    except Exception as e:
        current_app.logger.error(f"Error generating audio with OpenAI: {str(e)}")
        return None


def _generate_with_elevenlabs(text, voice_model, audio_path, language_code):
    """
    Generate audio using ElevenLabs API
    """
    import requests
    from app.utils.helpers import get_elevenlabs_config
    
    try:
        # Get ElevenLabs API key
        elevenlabs_config = get_elevenlabs_config()
        if not elevenlabs_config or 'api_key' not in elevenlabs_config:
            current_app.logger.error("ElevenLabs API key not found in configuration")
            return None
        
        # API endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_model.model_id}"
        
        # Request headers
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": elevenlabs_config['api_key']
        }
        
        # Request body
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        # Make the request
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            # Save the audio file
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            return audio_path
        else:
            current_app.logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        current_app.logger.error(f"Error generating audio with ElevenLabs: {str(e)}")
        return None


def _generate_with_google_tts(text, voice_model, audio_path, language_code):
    """
    Generate audio using Google Cloud Text-to-Speech API
    """
    try:
        # This is a placeholder for Google Cloud TTS implementation
        # In a real implementation, you would use the Google Cloud TTS client library
        current_app.logger.warning("Google Cloud TTS not yet implemented, using fallback")
        return _generate_fallback_audio(text, audio_path.replace('.mp3', '.wav'))
    
    except Exception as e:
        current_app.logger.error(f"Error generating audio with Google TTS: {str(e)}")
        return None


def _generate_fallback_audio(text, audio_path):
    """
    Generate a fallback audio file when other methods fail
    """
    try:
        # Create a simple WAV file with silence as a fallback
        sample_rate = 16000
        duration_sec = len(text) / 15  # Rough estimate: 15 characters per second
        duration_sec = max(1, min(duration_sec, 30))  # Between 1 and 30 seconds
        
        silence = np.zeros(int(sample_rate * duration_sec), dtype=np.int16)
        
        # Ensure the path ends with .wav for wave module
        if not audio_path.endswith('.wav'):
            audio_path = audio_path.replace('.mp3', '.wav')
        
        import wave
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(silence.tobytes())
        
        current_app.logger.warning(f"Generated fallback audio at {audio_path}")
        return audio_path
    
    except Exception as e:
        current_app.logger.error(f"Error generating fallback audio: {str(e)}")
        return None
