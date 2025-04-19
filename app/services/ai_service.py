import os
import tempfile
from flask import current_app
from openai import OpenAI
import json
import whisper
import numpy as np
from pydub import AudioSegment

from app.utils.helpers import get_openai_config

def transcribe_speech(audio_file_path):
    """
    Transcribe speech from an audio file using Whisper
    Returns the transcribed text
    """
    try:
        # Load the Whisper model (small model for efficiency)
        model = whisper.load_model("small")
        
        # Transcribe the audio
        result = model.transcribe(audio_file_path)
        
        return result["text"]
    except Exception as e:
        current_app.logger.error(f"Error transcribing speech: {str(e)}")
        return ""


def detect_language(text):
    """
    Detect the language of the provided text
    Returns the language code (en, sw, lg, ny for English, Swahili, Luganda, Runyankole)
    """
    if not text or len(text.strip()) < 3:
        current_app.logger.warning("Text too short for language detection")
        return "en"  # Default to English for very short text
    
    try:
        # Get OpenAI API key and configuration
        openai_config = get_openai_config()
        if not openai_config or 'api_key' not in openai_config:
            current_app.logger.error("OpenAI API key not found in configuration")
            return "en"  # Default to English
        
        # Initialize the OpenAI client with timeout and retry settings
        client = OpenAI(
            api_key=openai_config['api_key'],
            timeout=10.0,  # 10 second timeout
            max_retries=2  # Retry failed requests twice
        )
        
        # Get model from config or use default
        model = openai_config.get('model', 'gpt-4')
        
        # Use a structured prompt for more reliable language detection
        system_prompt = """
        You are a language detection system specialized in Ugandan languages.
        Your task is to identify if text is in English, Swahili, Luganda, or Runyankole.
        Respond with ONLY the language code:
        - 'en' for English
        - 'sw' for Swahili
        - 'lg' for Luganda
        - 'ny' for Runyankole
        """
        
        # Use the OpenAI API to detect the language
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Detect the language: {text}"}
            ],
            max_tokens=10,
            temperature=0.3  # Lower temperature for more deterministic results
        )
        
        # Extract and validate the language code
        language_code = response.choices[0].message.content.strip().lower()
        
        # Log the detection result
        current_app.logger.info(f"Language detection: '{text[:30]}...' -> {language_code}")
        
        # Validate the language code
        if language_code in ['en', 'sw', 'lg', 'ny']:
            return language_code
        else:
            current_app.logger.warning(f"Invalid language code detected: {language_code}, defaulting to English")
            return "en"  # Default to English
    except Exception as e:
        current_app.logger.error(f"Error detecting language: {str(e)}")
        return "en"  # Default to English


def analyze_response(text):
    """
    Analyze the voter's response to determine sentiment and content
    Returns a dictionary with sentiment and key points
    """
    try:
        # Get OpenAI API key
        openai_config = get_openai_config()
        if not openai_config or 'api_key' not in openai_config:
            current_app.logger.error("OpenAI API key not found in configuration")
            return {"sentiment": "neutral", "key_points": []}
        
        # Initialize the OpenAI client
        client = OpenAI(api_key=openai_config['api_key'])
        
        # Use GPT-4 to analyze the response
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a sentiment and content analysis system for a political campaign. Analyze the voter's response and provide a sentiment classification (positive, negative, or neutral) and extract key points from their response."},
                {"role": "user", "content": f"Analyze this voter response: '{text}'"}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        # Extract the analysis from the response
        analysis_text = response.choices[0].message.content
        
        # Try to parse structured data if it's in JSON format
        try:
            # Check if the response contains JSON
            if '{' in analysis_text and '}' in analysis_text:
                json_str = analysis_text[analysis_text.find('{'):analysis_text.rfind('}')+1]
                analysis = json.loads(json_str)
                if 'sentiment' not in analysis:
                    analysis['sentiment'] = 'neutral'
                return analysis
        except:
            pass
        
        # Fallback to simple text parsing
        sentiment = 'neutral'
        if 'positive' in analysis_text.lower():
            sentiment = 'positive'
        elif 'negative' in analysis_text.lower():
            sentiment = 'negative'
        
        return {
            "sentiment": sentiment,
            "key_points": [],
            "analysis": analysis_text
        }
    except Exception as e:
        current_app.logger.error(f"Error analyzing response: {str(e)}")
        return {"sentiment": "neutral", "key_points": []}


def generate_response_text(voter_input, analysis, prompt_template=""):
    """
    Generate a response text based on the voter's input and analysis
    Returns the generated text
    """
    try:
        # Get OpenAI API key
        openai_config = get_openai_config()
        if not openai_config or 'api_key' not in openai_config:
            current_app.logger.error("OpenAI API key not found in configuration")
            return "Thank you for your feedback. We appreciate your time."
        
        # Initialize the OpenAI client
        client = OpenAI(api_key=openai_config['api_key'])
        
        # Prepare the system prompt
        system_prompt = """
        You are an AI assistant for a political campaign. Generate a natural, conversational response to the voter's input.
        Keep your response concise (1-3 sentences), friendly, and politically appropriate.
        Acknowledge their sentiment and address their key concerns if any.
        Do not make specific policy promises unless they are in the provided prompt template.
        """
        
        # Use GPT-4 to generate a response
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Voter said: '{voter_input}'\nSentiment: {analysis['sentiment']}\nPrompt template: {prompt_template}\n\nGenerate a response:"}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        # Extract the generated text from the response
        return response.choices[0].message.content.strip()
    except Exception as e:
        current_app.logger.error(f"Error generating response text: {str(e)}")
        return "Thank you for your feedback. We appreciate your time."
