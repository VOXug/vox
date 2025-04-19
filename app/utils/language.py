"""
Language utilities for the VOX application
"""
import re
from flask import current_app
from app.services.ai_service import detect_language

# Language codes and their corresponding names
LANGUAGE_MAP = {
    'en': {
        'name': 'English',
        'native_name': 'English',
        'voice_preference': 'alloy',
        'common_phrases': [
            'hello', 'yes', 'no', 'thank you', 'goodbye',
            'good morning', 'good afternoon', 'good evening'
        ]
    },
    'sw': {
        'name': 'Swahili',
        'native_name': 'Kiswahili',
        'voice_preference': 'echo',
        'common_phrases': [
            'jambo', 'ndio', 'hapana', 'asante', 'kwaheri',
            'habari za asubuhi', 'habari za mchana', 'habari za jioni'
        ]
    },
    'lg': {
        'name': 'Luganda',
        'native_name': 'Oluganda',
        'voice_preference': 'fable',
        'common_phrases': [
            'ki kati', 'yee', 'nedda', 'weebale', 'weraba',
            'wasuze otya', 'osiibye otya', 'obudde bulidde'
        ]
    },
    'ny': {
        'name': 'Runyankole',
        'native_name': 'Runyankole',
        'voice_preference': 'nova',
        'common_phrases': [
            'agandi', 'eego', 'ngaaha', 'webale', 'kare',
            'oraire gye', 'osiibye ota', 'obugyenyi'
        ]
    }
}

def get_language_name(language_code):
    """Get the name of a language from its code"""
    if language_code in LANGUAGE_MAP:
        return LANGUAGE_MAP[language_code]['name']
    return 'Unknown'

def get_native_language_name(language_code):
    """Get the native name of a language from its code"""
    if language_code in LANGUAGE_MAP:
        return LANGUAGE_MAP[language_code]['native_name']
    return 'Unknown'

def get_supported_languages():
    """Get a list of all supported languages"""
    return [
        {
            'code': code,
            'name': info['name'],
            'native_name': info['native_name']
        }
        for code, info in LANGUAGE_MAP.items()
    ]

def get_preferred_voice(language_code):
    """Get the preferred voice for a language"""
    if language_code in LANGUAGE_MAP:
        return LANGUAGE_MAP[language_code]['voice_preference']
    return 'alloy'  # Default to alloy for unknown languages

def detect_language_from_text(text):
    """
    Detect the language of a text
    Uses AI service for complex detection, but first tries simple pattern matching
    for common phrases to save API calls
    """
    if not text or len(text.strip()) < 3:
        return 'en'  # Default to English for very short text
    
    text = text.lower().strip()
    
    # Check for common phrases in each language
    for lang_code, lang_info in LANGUAGE_MAP.items():
        for phrase in lang_info['common_phrases']:
            if phrase in text or text in phrase:
                current_app.logger.info(f"Language detected by phrase matching: {lang_code} ('{phrase}' in '{text}')")
                return lang_code
    
    # If no match found with common phrases, use the AI service
    return detect_language(text)

def translate_text(text, source_lang, target_lang):
    """
    Translate text from source language to target language
    This is a placeholder that would call an external translation API
    """
    if source_lang == target_lang:
        return text
    
    # In a real implementation, this would call a translation API
    # For now, we'll return a placeholder message
    return f"[Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}]: {text}"

def get_language_specific_greeting(language_code):
    """Get a language-specific greeting"""
    greetings = {
        'en': "Hello! Thank you for taking our call.",
        'sw': "Jambo! Asante kwa kupokea simu yetu.",
        'lg': "Ki kati! Webale okukkiriza okusimwa kwaffe.",
        'ny': "Agandi! Webale kukwata esimu yaitu."
    }
    
    return greetings.get(language_code, greetings['en'])

def get_language_specific_closing(language_code):
    """Get a language-specific closing message"""
    closings = {
        'en': "Thank you for your time. Have a great day!",
        'sw': "Asante kwa muda wako. Uwe na siku njema!",
        'lg': "Weebale obudde bwo. Olunaku olulungi!",
        'ny': "Webale obwire bwawe. Obone eizooba rirungi!"
    }
    
    return closings.get(language_code, closings['en'])

def format_number_for_language(number, language_code):
    """Format a number according to language conventions"""
    # This is a simple implementation that could be expanded
    if language_code == 'en':
        return f"{number:,}"
    elif language_code in ['sw', 'lg', 'ny']:
        # Use space as thousands separator and comma as decimal separator
        return f"{number:,}".replace(',', ' ').replace('.', ',')
    else:
        return str(number)

def get_language_direction(language_code):
    """Get the text direction for a language (ltr or rtl)"""
    # All currently supported languages are left-to-right
    return 'ltr'
