"""
Unit tests for the voice service module
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
import uuid
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.voice_service import (
    process_voice_upload, 
    train_voice_model, 
    generate_audio_clip,
    _generate_with_openai,
    _generate_with_elevenlabs
)
from app import create_app, db

class TestVoiceService(unittest.TestCase):
    """Test cases for the voice service module"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Set up test directories
        self.app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'test_uploads')
        self.app.config['MODELS_FOLDER'] = os.path.join(os.path.dirname(__file__), 'test_models')
        self.app.config['AUDIO_FOLDER'] = os.path.join(os.path.dirname(__file__), 'test_audio')
        
        # Create test directories if they don't exist
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(self.app.config['MODELS_FOLDER'], exist_ok=True)
        os.makedirs(self.app.config['AUDIO_FOLDER'], exist_ok=True)
        
        # Mock the OpenAI client
        self.openai_patcher = patch('app.services.voice_service.OpenAI')
        self.mock_openai = self.openai_patcher.start()
        
        # Mock the requests module for ElevenLabs API
        self.requests_patcher = patch('app.services.voice_service.requests')
        self.mock_requests = self.requests_patcher.start()
        
        # Mock the database models
        self.db_patcher = patch('app.services.voice_service.VoiceModel')
        self.mock_voice_model = self.db_patcher.start()
        
        # Mock the get_openai_config function
        self.openai_config_patcher = patch('app.services.voice_service._generate_with_openai.get_openai_config')
        self.mock_get_openai_config = self.openai_config_patcher.start()
        self.mock_get_openai_config.return_value = {'api_key': 'test_key'}
        
        # Mock the get_elevenlabs_config function
        self.elevenlabs_config_patcher = patch('app.services.voice_service._generate_with_elevenlabs.get_elevenlabs_config')
        self.mock_get_elevenlabs_config = self.elevenlabs_config_patcher.start()
        self.mock_get_elevenlabs_config.return_value = {'api_key': 'test_key'}
        
    def tearDown(self):
        """Clean up after tests"""
        self.openai_patcher.stop()
        self.requests_patcher.stop()
        self.db_patcher.stop()
        
        # Try to stop the config patchers if they were started
        try:
            self.openai_config_patcher.stop()
        except:
            pass
        
        try:
            self.elevenlabs_config_patcher.stop()
        except:
            pass
        
        self.app_context.pop()
        
        # Clean up test directories
        for dir_path in [self.app.config['UPLOAD_FOLDER'], self.app.config['MODELS_FOLDER'], self.app.config['AUDIO_FOLDER']]:
            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
    
    @patch('app.services.voice_service.AudioSegment')
    @patch('app.services.voice_service.uuid.uuid4')
    def test_process_voice_upload(self, mock_uuid4, mock_audio_segment):
        """Test processing of voice uploads"""
        # Mock UUID generation
        mock_uuid4.return_value.hex = 'test_uuid'
        
        # Mock file object
        mock_file = MagicMock()
        mock_file.filename = 'test_voice.mp3'
        mock_file.save.return_value = None
        
        # Mock AudioSegment
        mock_audio = MagicMock()
        mock_audio_segment.from_file.return_value = mock_audio
        mock_audio.export.return_value = None
        
        # Test the function
        result = process_voice_upload(mock_file)
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertTrue('filename' in result)
        self.assertTrue('path' in result)
        self.assertEqual(result['filename'], 'test_voice_test_uuid.wav')
        
        # Verify that the file was saved
        mock_file.save.assert_called_once()
        
        # Verify that the audio was processed
        mock_audio_segment.from_file.assert_called_once()
        mock_audio.export.assert_called_once()
    
    @patch('app.services.voice_service.os.path.exists')
    @patch('app.services.voice_service.uuid.uuid4')
    @patch('app.services.voice_service.open', new_callable=mock_open)
    @patch('app.services.voice_service.json.dump')
    @patch('app.services.voice_service.db')
    def test_train_voice_model(self, mock_db, mock_json_dump, mock_open, mock_uuid4, mock_path_exists):
        """Test voice model training"""
        # Mock UUID generation
        mock_uuid4.return_value.hex = 'test_model_id'
        
        # Mock path exists
        mock_path_exists.return_value = True
        
        # Mock voice model instance
        mock_voice_model_instance = MagicMock()
        mock_voice_model_instance.id = 1
        mock_voice_model_instance.name = 'Test Model'
        mock_voice_model_instance.provider = 'Elevenlabs'
        mock_voice_model_instance.model_id = 'test_provider_id'
        mock_voice_model_instance.language_code = 'en'
        
        # Mock VoiceModel class
        self.mock_voice_model.return_value = mock_voice_model_instance
        
        # Mock ElevenLabs API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'voice_id': 'test_provider_id'}
        self.mock_requests.post.return_value = mock_response
        
        # Test data
        voice_samples = ['sample1.mp3', 'sample2.mp3']
        model_name = 'Test Voice Model'
        language_code = 'en'
        
        # Test the function
        result = train_voice_model(
            voice_samples=voice_samples,
            model_name=model_name,
            language_code=language_code,
            provider='elevenlabs',
            description='Test description',
            user_id=1
        )
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Test Model')
        self.assertEqual(result['provider'], 'Elevenlabs')
        self.assertEqual(result['language_code'], 'en')
        
        # Verify that the model was saved to the database
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()
    
    @patch('app.services.voice_service.os.path.exists')
    @patch('app.services.voice_service.uuid.uuid4')
    def test_generate_audio_clip_openai(self, mock_uuid4, mock_path_exists):
        """Test audio clip generation with OpenAI"""
        # Mock UUID generation
        mock_uuid4.return_value.hex = 'test_audio_id'
        
        # Mock path exists
        mock_path_exists.return_value = True
        
        # Mock voice model
        mock_voice_model = MagicMock()
        mock_voice_model.provider = 'OpenAI'
        mock_voice_model.model_id = 'alloy'
        mock_voice_model.name = 'Test Voice'
        
        # Mock VoiceModel query
        self.mock_voice_model.query.get.return_value = mock_voice_model
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.stream_to_file.return_value = None
        self.mock_openai.return_value.audio.speech.create.return_value = mock_response
        
        # Test the function
        result = generate_audio_clip(
            text="Hello, this is a test.",
            voice_model_id=1,
            language_code='en'
        )
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertTrue('test_audio_id' in result)
        
        # Verify that the OpenAI API was called
        self.mock_openai.return_value.audio.speech.create.assert_called_once()
        mock_response.stream_to_file.assert_called_once()

if __name__ == '__main__':
    unittest.main()
