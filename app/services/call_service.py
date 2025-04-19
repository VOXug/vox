from datetime import datetime, timedelta
from sqlalchemy import func
from flask import current_app

from app import db
from app.models import Campaign, CallLog, Voter, VoterList, VoterListEntry
from app.utils.helpers import get_twilio_config

def get_call_stats(start_date=None, end_date=None):
    """
    Get call statistics for the specified date range
    If no dates are provided, gets stats for all time
    """
    query = db.session.query(CallLog)
    
    if start_date:
        query = query.filter(CallLog.created_at >= start_date)
    if end_date:
        query = query.filter(CallLog.created_at <= end_date)
    
    total_calls = query.count()
    completed_calls = query.filter(CallLog.status == 'completed').count()
    failed_calls = query.filter(CallLog.status.in_(['failed', 'busy', 'no-answer'])).count()
    
    # Get sentiment distribution
    sentiment_counts = {}
    sentiment_query = db.session.query(
        CallLog.sentiment, 
        func.count(CallLog.id)
    ).filter(CallLog.sentiment.isnot(None))
    
    if start_date:
        sentiment_query = sentiment_query.filter(CallLog.created_at >= start_date)
    if end_date:
        sentiment_query = sentiment_query.filter(CallLog.created_at <= end_date)
    
    sentiment_results = sentiment_query.group_by(CallLog.sentiment).all()
    
    for sentiment, count in sentiment_results:
        sentiment_counts[sentiment] = count
    
    # Get language distribution
    language_counts = {}
    language_query = db.session.query(
        CallLog.language_used, 
        func.count(CallLog.id)
    ).filter(CallLog.language_used.isnot(None))
    
    if start_date:
        language_query = language_query.filter(CallLog.created_at >= start_date)
    if end_date:
        language_query = language_query.filter(CallLog.created_at <= end_date)
    
    language_results = language_query.group_by(CallLog.language_used).all()
    
    for language, count in language_results:
        language_counts[language] = count
    
    # Calculate average call duration
    duration_query = db.session.query(func.avg(CallLog.duration)).filter(CallLog.duration.isnot(None))
    
    if start_date:
        duration_query = duration_query.filter(CallLog.created_at >= start_date)
    if end_date:
        duration_query = duration_query.filter(CallLog.created_at <= end_date)
    
    avg_duration = duration_query.scalar() or 0
    
    return {
        'total_calls': total_calls,
        'completed_calls': completed_calls,
        'failed_calls': failed_calls,
        'completion_rate': (completed_calls / total_calls * 100) if total_calls > 0 else 0,
        'sentiment_counts': sentiment_counts,
        'language_counts': language_counts,
        'avg_duration': avg_duration
    }


def get_campaign_stats(campaign_id):
    """Get statistics for a specific campaign"""
    # Get the campaign
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None
    
    # Get call logs for this campaign
    call_logs = CallLog.query.filter_by(campaign_id=campaign_id).all()
    
    total_calls = len(call_logs)
    completed_calls = sum(1 for log in call_logs if log.status == 'completed')
    failed_calls = sum(1 for log in call_logs if log.status in ['failed', 'busy', 'no-answer'])
    
    # Get sentiment distribution
    sentiment_counts = {}
    for log in call_logs:
        if log.sentiment:
            sentiment_counts[log.sentiment] = sentiment_counts.get(log.sentiment, 0) + 1
    
    # Get language distribution
    language_counts = {}
    for log in call_logs:
        if log.language_used:
            language_counts[log.language_used] = language_counts.get(log.language_used, 0) + 1
    
    # Calculate average call duration
    durations = [log.duration for log in call_logs if log.duration]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Get daily call counts
    daily_counts = {}
    for log in call_logs:
        date_str = log.created_at.strftime('%Y-%m-%d')
        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
    
    return {
        'total_calls': total_calls,
        'completed_calls': completed_calls,
        'failed_calls': failed_calls,
        'completion_rate': (completed_calls / total_calls * 100) if total_calls > 0 else 0,
        'sentiment_counts': sentiment_counts,
        'language_counts': language_counts,
        'avg_duration': avg_duration,
        'daily_counts': daily_counts
    }


def schedule_campaign_calls(campaign_id, max_calls=None):
    """
    Schedule calls for a campaign
    Returns the number of calls scheduled
    """
    # Get the campaign
    campaign = Campaign.query.get(campaign_id)
    if not campaign or not campaign.is_active:
        return 0
    
    # Determine how many calls to schedule
    if max_calls is None:
        max_calls = campaign.max_calls_per_hour
    
    # Get Twilio configuration
    twilio_config = get_twilio_config()
    if not twilio_config:
        current_app.logger.error("Twilio configuration not found")
        return 0
    
    # Get voter lists for this campaign
    voter_lists = campaign.voter_lists.all()
    if not voter_lists:
        current_app.logger.warning(f"No voter lists found for campaign {campaign_id}")
        return 0
    
    # Get voters from these lists who haven't been called yet or need a retry
    called_voter_ids = db.session.query(CallLog.voter_id).filter_by(campaign_id=campaign_id).all()
    called_voter_ids = [v[0] for v in called_voter_ids]
    
    # Get voters from the lists who haven't been called
    voter_list_ids = [vl.id for vl in voter_lists]
    
    voters_query = db.session.query(Voter).join(
        VoterListEntry, Voter.id == VoterListEntry.voter_id
    ).filter(
        VoterListEntry.voter_list_id.in_(voter_list_ids),
        Voter.do_not_call == False
    )
    
    if called_voter_ids:
        voters_query = voters_query.filter(Voter.id.notin_(called_voter_ids))
    
    voters = voters_query.limit(max_calls).all()
    
    # If we don't have enough new voters, get voters who need a retry
    if len(voters) < max_calls:
        # Calculate how many more voters we need
        remaining_slots = max_calls - len(voters)
        
        # Get voters who have been called but need a retry
        retry_candidates = db.session.query(
            CallLog.voter_id,
            func.count(CallLog.id).label('call_count')
        ).filter(
            CallLog.campaign_id == campaign_id,
            CallLog.status.in_(['busy', 'no-answer', 'failed'])
        ).group_by(
            CallLog.voter_id
        ).having(
            func.count(CallLog.id) < campaign.retry_attempts
        ).order_by(
            func.count(CallLog.id)
        ).limit(remaining_slots).all()
        
        retry_voter_ids = [v[0] for v in retry_candidates]
        
        if retry_voter_ids:
            retry_voters = Voter.query.filter(
                Voter.id.in_(retry_voter_ids),
                Voter.do_not_call == False
            ).all()
            
            voters.extend(retry_voters)
    
    # Schedule calls for these voters
    scheduled_count = 0
    
    for voter in voters:
        try:
            # Initiate the call using Twilio
            call_sid = initiate_call(voter.id, campaign.id)
            if call_sid:
                scheduled_count += 1
        except Exception as e:
            current_app.logger.error(f"Error scheduling call for voter {voter.id}: {str(e)}")
    
    db.session.commit()
    return scheduled_count


def initiate_call(voter_id, campaign_id):
    """
    Initiate a call to a voter for a specific campaign using Twilio
    Returns the call SID if successful, None otherwise
    """
    try:
        # Get Twilio configuration
        twilio_config = get_twilio_config()
        if not twilio_config or 'account_sid' not in twilio_config or 'auth_token' not in twilio_config:
            current_app.logger.error("Twilio configuration incomplete or not found")
            return None
        
        # Get voter and campaign details
        voter = Voter.query.get(voter_id)
        campaign = Campaign.query.get(campaign_id)
        
        if not voter or not campaign:
            current_app.logger.error(f"Voter ID {voter_id} or Campaign ID {campaign_id} not found")
            return None
        
        # Validate phone number
        if not voter.phone_number or not voter.phone_number.strip():
            current_app.logger.error(f"Voter ID {voter_id} has no phone number")
            return None
            
        # Format phone number for Twilio (ensure it has + prefix)
        phone_number = voter.phone_number.strip()
        if not phone_number.startswith('+'):
            # Assuming Ugandan numbers, add the country code if not present
            if phone_number.startswith('0'):
                phone_number = '+256' + phone_number[1:]
            else:
                phone_number = '+256' + phone_number
        
        # Initialize Twilio client
        client = Client(twilio_config['account_sid'], twilio_config['auth_token'])
        
        # Get the callback URL for when the call is answered
        callback_url = url_for('api.call_answered', _external=True, campaign_id=campaign_id, voter_id=voter_id)
        
        # Get the Twilio phone number to use for outbound calls
        from_number = twilio_config.get('phone_number')
        if not from_number:
            current_app.logger.error("No Twilio phone number configured for outbound calls")
            return None
        
        # Set call timeout and other parameters
        timeout = 30  # 30 seconds ring time
        status_callback = url_for('api.call_status_callback', _external=True)
        
        # Log the call attempt
        current_app.logger.info(f"Initiating call to {phone_number} for campaign '{campaign.name}'")
        
        # Make the call using Twilio API
        call = client.calls.create(
            to=phone_number,
            from_=from_number,
            url=callback_url,
            timeout=timeout,
            status_callback=status_callback,
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        
        call_sid = call.sid
        
        # Create a call log entry
        call_log = CallLog(
            call_sid=call_sid,
            voter_id=voter_id,
            campaign_id=campaign_id,
            status="initiated",
            start_time=datetime.utcnow()
        )
        
        db.session.add(call_log)
        db.session.commit()
        
        current_app.logger.info(f"Call initiated with SID: {call_sid}")
        return call_sid
    
    except TwilioRestException as e:
        current_app.logger.error(f"Twilio API error: {e.code} - {e.msg}")
        return None
    except Exception as e:
        current_app.logger.error(f"Error initiating call: {str(e)}")
        return None


def handle_call_answered(campaign_id, voter_id, call_sid=None):
    """
    Generate TwiML response when a call is answered
    This starts the conversation flow for the campaign
    """
    try:
        # Get campaign and voter details
        campaign = Campaign.query.get(campaign_id)
        voter = Voter.query.get(voter_id)
        
        if not campaign or not voter:
            current_app.logger.error(f"Campaign ID {campaign_id} or Voter ID {voter_id} not found")
            return _generate_error_twiml()
        
        # Get the conversation flow for the campaign
        flow = ConversationFlow.query.filter_by(campaign_id=campaign_id, is_active=True).first()
        if not flow:
            current_app.logger.error(f"No active conversation flow found for campaign {campaign_id}")
            return _generate_error_twiml()
        
        # Update call log if call_sid is provided
        if call_sid:
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log:
                call_log.status = "in-progress"
                db.session.commit()
        
        # Generate TwiML for the initial greeting
        response = VoiceResponse()
        
        # Add initial greeting from the flow
        greeting = flow.initial_greeting or f"Hello from {campaign.name}. This is an automated call."
        response.say(greeting, voice="alice")
        
        # Start the conversation flow
        gather = Gather(input="dtmf speech", timeout=5, action=url_for('api.process_response', flow_id=flow.id, voter_id=voter_id, node_id=flow.start_node_id, _external=True), method="POST")
        gather.say("Please respond to continue the conversation.")
        response.append(gather)
        
        # If no input is received, retry
        response.redirect(url_for('api.call_answered', campaign_id=campaign_id, voter_id=voter_id, _external=True))
        
        return str(response)
    
    except Exception as e:
        current_app.logger.error(f"Error handling answered call: {str(e)}")
        return _generate_error_twiml()


def _generate_error_twiml():
    """
    Generate a TwiML response for error conditions
    """
    response = VoiceResponse()
    response.say("We're sorry, but there was an error processing your call. Please try again later.")
    response.hangup()
    return str(response)


def end_call(call_sid, status="completed", duration=None, recording_url=None):
    """
    End a call and update the call log
    """
    try:
        # Get the call log
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if not call_log:
            current_app.logger.error(f"Call log not found for SID {call_sid}")
            return False
        
        # Update the call log
        call_log.status = status
        call_log.end_time = datetime.utcnow()
        
        if duration is not None:
            call_log.duration = duration
        elif call_log.start_time:
            # Calculate duration if not provided
            call_log.duration = (datetime.utcnow() - call_log.start_time).total_seconds()
        
        if recording_url:
            call_log.recording_url = recording_url
        
        # Save the changes
        db.session.commit()
        
        current_app.logger.info(f"Call {call_sid} ended with status {status}")
        return True
    
    except Exception as e:
        current_app.logger.error(f"Error ending call: {str(e)}")
        return False


def get_call_status(call_sid):
    """
    Get the current status of a call from Twilio
    """
    try:
        # Get Twilio configuration
        twilio_config = get_twilio_config()
        if not twilio_config:
            current_app.logger.error("Twilio configuration not found")
            return None
        
        # Initialize Twilio client
        client = Client(twilio_config['account_sid'], twilio_config['auth_token'])
        
        # Get call details from Twilio
        call = client.calls(call_sid).fetch()
        
        return {
            'status': call.status,
            'duration': call.duration,
            'direction': call.direction,
            'from': call.from_,
            'to': call.to,
            'start_time': call.start_time,
            'end_time': call.end_time
        }
    
    except TwilioRestException as e:
        current_app.logger.error(f"Twilio API error getting call status: {e.code} - {e.msg}")
        return None
    except Exception as e:
        current_app.logger.error(f"Error getting call status: {str(e)}")
        return None
