"""
Unit tests for the AI service module
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_service import detect_language, analyze_sentiment, generate_response
from app import create_app, db

class TestAIService(unittest.TestCase):
    """Test cases for the AI service module"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Mock the OpenAI client
        self.openai_patcher = patch('app.services.ai_service.OpenAI')
        self.mock_openai = self.openai_patcher.start()
        
        # Mock the get_openai_config function
        self.config_patcher = patch('app.services.ai_service.get_openai_config')
        self.mock_get_config = self.config_patcher.start()
        self.mock_get_config.return_value = {'api_key': 'test_key', 'model': 'gpt-4'}
        
    def tearDown(self):
        """Clean up after tests"""
        self.openai_patcher.stop()
        self.config_patcher.stop()
        self.app_context.pop()
    
    def test_detect_language_english(self):
        """Test language detection for English text"""
        # Mock the OpenAI response
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "en"
        self.mock_openai.return_value.chat.completions.create.return_value = mock_completion
        
        # Test with English text
        result = detect_language("Hello, how are you today?")
        
        # Verify the result
        self.assertEqual(result, "en")
        self.mock_openai.return_value.chat.completions.create.assert_called_once()
    
    def test_detect_language_swahili(self):
        """Test language detection for Swahili text"""
        # Mock the OpenAI response
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "sw"
        self.mock_openai.return_value.chat.completions.create.return_value = mock_completion
        
        # Test with Swahili text
        result = detect_language("Habari yako?")
        
        # Verify the result
        self.assertEqual(result, "sw")
        self.mock_openai.return_value.chat.completions.create.assert_called_once()
    
    def test_detect_language_empty_text(self):
        """Test language detection with empty text"""
        # Test with empty text
        result = detect_language("")
        
        # Should default to English without calling the API
        self.assertEqual(result, "en")
        self.mock_openai.return_value.chat.completions.create.assert_not_called()
    
    def test_detect_language_api_error(self):
        """Test language detection when API returns an error"""
        # Mock the OpenAI client to raise an exception
        self.mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        # Test with text
        result = detect_language("Hello, how are you?")
        
        # Should default to English when there's an error
        self.assertEqual(result, "en")
    
    @patch('app.services.ai_service.analyze_sentiment')
    def test_generate_response(self, mock_analyze_sentiment):
        """Test response generation"""
        # Mock the sentiment analysis
        mock_analyze_sentiment.return_value = "positive"
        
        # Mock the OpenAI response
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "I'm glad you're interested in our campaign!"
        self.mock_openai.return_value.chat.completions.create.return_value = mock_completion
        
        # Test response generation
        result = generate_response(
            "I would like to learn more about your campaign",
            "en",
            context={"campaign_name": "Test Campaign", "voter_name": "John"}
        )
        
        # Verify the result
        self.assertEqual(result, "I'm glad you're interested in our campaign!")
        self.mock_openai.return_value.chat.completions.create.assert_called_once()

if __name__ == '__main__':
    unittest.main()
