from flask import Blueprint, request, jsonify, current_app, url_for
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.request_validator import RequestValidator
import json
import os
from datetime import datetime

from app import db
from app.models import (
    Campaign, Voter, CallLog, CallEvent, 
    ConversationFlow, AudioClip, Language, APIConfig
)
from app.services.ai_service import (
    transcribe_speech, analyze_response, 
    detect_language, generate_response_text
)
from app.services.voice_service import generate_audio_clip
from app.utils.helpers import validate_phone_number, get_twilio_config

api_bp = Blueprint('api', __name__, url_prefix='/api')

def validate_twilio_request(f):
    """Decorator to validate that requests are coming from Twilio"""
    def decorated_function(*args, **kwargs):
        # Get Twilio auth token from config
        twilio_config = get_twilio_config()
        if not twilio_config or 'auth_token' not in twilio_config:
            current_app.logger.error("Twilio auth token not found in configuration")
            return jsonify({'error': 'Twilio configuration not found'}), 500
        
        # Validate the request
        validator = RequestValidator(twilio_config['auth_token'])
        request_valid = validator.validate(
            request.url,
            request.form,
            request.headers.get('X-Twilio-Signature', '')
        )
        
        if request_valid or current_app.debug:
            return f(*args, **kwargs)
        else:
            current_app.logger.warning("Invalid Twilio request signature")
            return jsonify({'error': 'Invalid request signature'}), 403
    
    return decorated_function


@api_bp.route('/call/incoming', methods=['POST'])
@validate_twilio_request
def incoming_call():
    """Handle incoming calls (when someone calls our Twilio number)"""
    response = VoiceResponse()
    response.say("Thank you for calling. This number is for outbound campaign calls only.")
    response.hangup()
    return str(response)


@api_bp.route('/call/outbound', methods=['POST'])
def outbound_call():
    """Initiate an outbound call to a voter"""
    # Get request data
    data = request.json
    if not data or 'voter_id' not in data or 'campaign_id' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    voter_id = data['voter_id']
    campaign_id = data['campaign_id']
    
    # Get voter and campaign
    voter = Voter.query.get(voter_id)
    campaign = Campaign.query.get(campaign_id)
    
    if not voter or not campaign:
        return jsonify({'error': 'Voter or campaign not found'}), 404
    
    if voter.do_not_call:
        return jsonify({'error': 'Voter is on do-not-call list'}), 400
    
    if not campaign.is_active:
        return jsonify({'error': 'Campaign is not active'}), 400
    
    # Get Twilio configuration
    twilio_config = get_twilio_config()
    if not twilio_config:
        return jsonify({'error': 'Twilio configuration not found'}), 500
    
    # Initialize call log
    call_log = CallLog(
        status='initiated',
        voter_id=voter_id,
        campaign_id=campaign_id,
        created_at=datetime.utcnow()
    )
    db.session.add(call_log)
    db.session.commit()
    
    # Import Twilio client here to avoid loading it when not needed
    from twilio.rest import Client
    
    # Initialize Twilio client
    client = Client(twilio_config['account_sid'], twilio_config['auth_token'])
    
    try:
        # Make the call
        call = client.calls.create(
            to=voter.phone_number,
            from_=twilio_config['phone_number'],
            url=url_for('api.call_started', _external=True, call_log_id=call_log.id),
            status_callback=url_for('api.call_status', _external=True, call_log_id=call_log.id),
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        
        # Update call log with Twilio call SID
        call_log.call_sid = call.sid
        db.session.commit()
        
        return jsonify({
            'success': True,
            'call_sid': call.sid,
            'call_log_id': call_log.id
        })
    
    except Exception as e:
        # Update call log with error
        call_log.status = 'failed'
        call_log.notes = str(e)
        db.session.commit()
        
        current_app.logger.error(f"Error initiating call: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/call/started', methods=['POST'])
@validate_twilio_request
def call_started():
    """Handle when a call is answered and the conversation should begin"""
    call_log_id = request.args.get('call_log_id')
    if not call_log_id:
        current_app.logger.error("No call_log_id provided to call_started endpoint")
        return jsonify({'error': 'Missing call_log_id parameter'}), 400
    
    # Get call log
    call_log = CallLog.query.get(call_log_id)
    if not call_log:
        current_app.logger.error(f"Call log {call_log_id} not found")
        return jsonify({'error': 'Call log not found'}), 404
    
    # Get campaign and conversation flow
    campaign = Campaign.query.get(call_log.campaign_id)
    conversation_flow = ConversationFlow.query.filter_by(campaign_id=campaign.id).first()
    
    if not conversation_flow:
        current_app.logger.error(f"No conversation flow found for campaign {campaign.id}")
        response = VoiceResponse()
        response.say("We're sorry, but there was an error with this call. Goodbye.")
        response.hangup()
        return str(response)
    
    # Get the first step in the conversation flow
    flow_data = conversation_flow.flow_data
    if not flow_data or 'steps' not in flow_data or not flow_data['steps']:
        current_app.logger.error(f"Invalid flow data for conversation flow {conversation_flow.id}")
        response = VoiceResponse()
        response.say("We're sorry, but there was an error with this call. Goodbye.")
        response.hangup()
        return str(response)
    
    # Find the first step (intro)
    intro_step = None
    for step in flow_data['steps']:
        if step.get('type') == 'intro':
            intro_step = step
            break
    
    if not intro_step:
        intro_step = flow_data['steps'][0]
    
    # Get the voter's preferred language or default to English
    voter = Voter.query.get(call_log.voter_id)
    language_code = voter.language_preference if voter.language_preference else 'en'
    
    # Find the language in our database
    language = Language.query.filter_by(code=language_code, is_active=True).first()
    if not language:
        language = Language.query.filter_by(code='en', is_active=True).first()
    
    # Update call log with language
    call_log.language_used = language.code
    db.session.commit()
    
    # Find the audio clip for this step and language
    audio_clip = AudioClip.query.filter_by(
        conversation_flow_id=conversation_flow.id,
        step_id=intro_step['id'],
        language_id=language.id,
        sentiment='neutral'  # Intro is always neutral
    ).first()
    
    # Build TwiML response
    response = VoiceResponse()
    
    if audio_clip:
        # Log the event
        event = CallEvent(
            call_log_id=call_log.id,
            event_type='audio-played',
            event_data={
                'step_id': intro_step['id'],
                'audio_clip_id': audio_clip.id,
                'language': language.code
            }
        )
        db.session.add(event)
        db.session.commit()
        
        # Play the audio clip
        response.play(url_for('static', filename=f'audio/{os.path.basename(audio_clip.file_path)}', _external=True))
    else:
        # Fallback if no audio clip is found
        response.say(f"Hello, this is a call from the campaign. We apologize, but we're experiencing technical difficulties.")
    
    # Set up gathering the voter's response
    gather = Gather(
        input='speech',
        action=url_for('api.process_response', _external=True, call_log_id=call_log.id, step_id=intro_step['id']),
        method='POST',
        timeout=5,
        speechTimeout='auto'
    )
    
    # Add the gather to the response
    response.append(gather)
    
    # If no input is received, try again or end the call
    response.redirect(url_for('api.no_input', _external=True, call_log_id=call_log.id))
    
    return str(response)


@api_bp.route('/call/process-response', methods=['POST'])
@validate_twilio_request
def process_response():
    """Process the voter's spoken response"""
    call_log_id = request.args.get('call_log_id')
    current_step_id = request.args.get('step_id')
    
    if not call_log_id or not current_step_id:
        current_app.logger.error("Missing parameters in process_response")
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Get call log
    call_log = CallLog.query.get(call_log_id)
    if not call_log:
        current_app.logger.error(f"Call log {call_log_id} not found")
        return jsonify({'error': 'Call log not found'}), 404
    
    # Get speech input
    speech_result = request.form.get('SpeechResult')
    
    if not speech_result:
        # No speech detected, redirect to no input handler
        response = VoiceResponse()
        response.redirect(url_for('api.no_input', _external=True, call_log_id=call_log_id))
        return str(response)
    
    # Log the event
    event = CallEvent(
        call_log_id=call_log.id,
        event_type='speech-detected',
        event_data={
            'speech_text': speech_result,
            'step_id': current_step_id
        }
    )
    db.session.add(event)
    db.session.commit()
    
    # Get campaign and conversation flow
    campaign = Campaign.query.get(call_log.campaign_id)
    conversation_flow = ConversationFlow.query.filter_by(campaign_id=campaign.id).first()
    
    if not conversation_flow:
        current_app.logger.error(f"No conversation flow found for campaign {campaign.id}")
        response = VoiceResponse()
        response.say("We're sorry, but there was an error with this call. Goodbye.")
        response.hangup()
        return str(response)
    
    # Get flow data
    flow_data = conversation_flow.flow_data
    
    # Detect language if not already set
    if not call_log.language_used:
        detected_language = detect_language(speech_result)
        language = Language.query.filter_by(code=detected_language, is_active=True).first()
        if not language:
            language = Language.query.filter_by(code='en', is_active=True).first()
        
        call_log.language_used = language.code
        db.session.commit()
    else:
        language = Language.query.filter_by(code=call_log.language_used, is_active=True).first()
    
    # Analyze the response to determine sentiment and content
    analysis = analyze_response(speech_result)
    
    # Update call log with sentiment
    call_log.sentiment = analysis['sentiment']
    db.session.commit()
    
    # Log the analysis event
    event = CallEvent(
        call_log_id=call_log.id,
        event_type='response-analyzed',
        event_data={
            'analysis': analysis,
            'step_id': current_step_id
        }
    )
    db.session.add(event)
    db.session.commit()
    
    # Find the next step based on the current step and analysis
    next_step = None
    for step in flow_data['steps']:
        if step.get('id') == current_step_id:
            # Find the transition that matches the sentiment
            transitions = step.get('transitions', [])
            for transition in transitions:
                if transition.get('sentiment') == analysis['sentiment']:
                    next_step_id = transition.get('next_step_id')
                    # Find the step with this ID
                    for potential_next_step in flow_data['steps']:
                        if potential_next_step.get('id') == next_step_id:
                            next_step = potential_next_step
                            break
                    break
            
            # If no matching sentiment transition, use default
            if not next_step:
                default_transition = next((t for t in transitions if t.get('sentiment') == 'default'), None)
                if default_transition:
                    next_step_id = default_transition.get('next_step_id')
                    # Find the step with this ID
                    for potential_next_step in flow_data['steps']:
                        if potential_next_step.get('id') == next_step_id:
                            next_step = potential_next_step
                            break
            
            break
    
    # If no next step found, end the call
    if not next_step:
        response = VoiceResponse()
        response.say("Thank you for your time. Goodbye.")
        response.hangup()
        
        # Update call log
        call_log.status = 'completed'
        call_log.ended_at = datetime.utcnow()
        db.session.commit()
        
        return str(response)
    
    # Check if this is an outro (end of conversation)
    is_outro = next_step.get('type') == 'outro'
    
    # Find the audio clip for the next step
    audio_clip = AudioClip.query.filter_by(
        conversation_flow_id=conversation_flow.id,
        step_id=next_step['id'],
        language_id=language.id,
        sentiment=analysis['sentiment']
    ).first()
    
    # If no matching sentiment clip, try neutral
    if not audio_clip:
        audio_clip = AudioClip.query.filter_by(
            conversation_flow_id=conversation_flow.id,
            step_id=next_step['id'],
            language_id=language.id,
            sentiment='neutral'
        ).first()
    
    # Build TwiML response
    response = VoiceResponse()
    
    if audio_clip:
        # Log the event
        event = CallEvent(
            call_log_id=call_log.id,
            event_type='audio-played',
            event_data={
                'step_id': next_step['id'],
                'audio_clip_id': audio_clip.id,
                'language': language.code
            }
        )
        db.session.add(event)
        db.session.commit()
        
        # Play the audio clip
        response.play(url_for('static', filename=f'audio/{os.path.basename(audio_clip.file_path)}', _external=True))
    else:
        # Generate a response if no audio clip is found
        generated_text = generate_response_text(speech_result, analysis, next_step.get('content', ''))
        response.say(generated_text)
    
    # If this is the outro, hang up after playing
    if is_outro:
        response.hangup()
        
        # Update call log
        call_log.status = 'completed'
        call_log.ended_at = datetime.utcnow()
        db.session.commit()
    else:
        # Otherwise, gather the next response
        gather = Gather(
            input='speech',
            action=url_for('api.process_response', _external=True, call_log_id=call_log.id, step_id=next_step['id']),
            method='POST',
            timeout=5,
            speechTimeout='auto'
        )
        
        # Add the gather to the response
        response.append(gather)
        
        # If no input is received, try again or end the call
        response.redirect(url_for('api.no_input', _external=True, call_log_id=call_log.id))
    
    return str(response)


@api_bp.route('/call/no-input', methods=['POST'])
@validate_twilio_request
def no_input():
    """Handle when no input is received from the voter"""
    call_log_id = request.args.get('call_log_id')
    
    if not call_log_id:
        current_app.logger.error("No call_log_id provided to no_input endpoint")
        return jsonify({'error': 'Missing call_log_id parameter'}), 400
    
    # Get call log
    call_log = CallLog.query.get(call_log_id)
    if not call_log:
        current_app.logger.error(f"Call log {call_log_id} not found")
        return jsonify({'error': 'Call log not found'}), 404
    
    # Log the event
    event = CallEvent(
        call_log_id=call_log.id,
        event_type='no-input',
        event_data={}
    )
    db.session.add(event)
    db.session.commit()
    
    # Build TwiML response
    response = VoiceResponse()
    response.say("I didn't hear anything. Thank you for your time. Goodbye.")
    response.hangup()
    
    # Update call log
    call_log.status = 'completed'
    call_log.ended_at = datetime.utcnow()
    db.session.commit()
    
    return str(response)


@api_bp.route('/call/status', methods=['POST'])
@validate_twilio_request
def call_status():
    """Handle Twilio call status callbacks"""
    call_log_id = request.args.get('call_log_id')
    call_status = request.form.get('CallStatus')
    call_duration = request.form.get('CallDuration')
    
    if not call_log_id or not call_status:
        current_app.logger.error("Missing parameters in call_status")
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Get call log
    call_log = CallLog.query.get(call_log_id)
    if not call_log:
        current_app.logger.error(f"Call log {call_log_id} not found")
        return jsonify({'error': 'Call log not found'}), 404
    
    # Update call log
    call_log.status = call_status
    
    if call_duration:
        call_log.duration = int(call_duration)
    
    if call_status in ['completed', 'busy', 'failed', 'no-answer']:
        call_log.ended_at = datetime.utcnow()
    
    db.session.commit()
    
    # Log the event
    event = CallEvent(
        call_log_id=call_log.id,
        event_type='status-update',
        event_data={
            'status': call_status,
            'duration': call_duration
        }
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({'success': True})


@api_bp.route('/voice-models', methods=['GET'])
def get_voice_models():
    """API endpoint to get all voice models"""
    models = VoiceModel.query.filter_by(is_active=True).all()
    return jsonify({
        'models': [
            {
                'id': model.id,
                'name': model.name,
                'description': model.description
            } for model in models
        ]
    })


@api_bp.route('/languages', methods=['GET'])
def get_languages():
    """API endpoint to get all supported languages"""
    languages = Language.query.filter_by(is_active=True).all()
    return jsonify({
        'languages': [
            {
                'id': lang.id,
                'name': lang.name,
                'code': lang.code
            } for lang in languages
        ]
    })


@api_bp.route('/campaigns', methods=['GET'])
def get_campaigns():
    """API endpoint to get all campaigns"""
    campaigns = Campaign.query.all()
    return jsonify({
        'campaigns': [
            {
                'id': campaign.id,
                'name': campaign.name,
                'description': campaign.description,
                'is_active': campaign.is_active
            } for campaign in campaigns
        ]
    })
