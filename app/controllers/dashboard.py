from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
import json
from datetime import datetime, timedelta

from app import db
from app.models import (
    Campaign, ConversationFlow, VoiceModel, Language, 
    Voter, VoterList, CallLog, CallEvent
)
from app.services.call_service import get_call_stats, get_campaign_stats
from app.utils.decorators import admin_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page"""
    # Get active campaigns
    active_campaigns = Campaign.query.filter_by(is_active=True).all()
    
    # Get recent call logs (last 24 hours)
    recent_time = datetime.utcnow() - timedelta(hours=24)
    recent_calls = CallLog.query.filter(CallLog.created_at >= recent_time).order_by(CallLog.created_at.desc()).limit(10).all()
    
    # Get call statistics
    call_stats = get_call_stats()
    
    return render_template(
        'dashboard/index.html', 
        title='Dashboard',
        active_campaigns=active_campaigns,
        recent_calls=recent_calls,
        call_stats=call_stats
    )


@dashboard_bp.route('/campaigns')
@login_required
def campaigns():
    """View all campaigns"""
    campaigns = Campaign.query.all()
    return render_template('dashboard/campaigns.html', title='Campaigns', campaigns=campaigns)


@dashboard_bp.route('/campaigns/<int:id>')
@login_required
def campaign_detail(id):
    """View campaign details"""
    campaign = Campaign.query.get_or_404(id)
    stats = get_campaign_stats(campaign.id)
    
    # Get conversation flows for this campaign
    flows = ConversationFlow.query.filter_by(campaign_id=campaign.id).all()
    
    # Get recent call logs for this campaign
    recent_calls = CallLog.query.filter_by(campaign_id=campaign.id).order_by(CallLog.created_at.desc()).limit(20).all()
    
    return render_template(
        'dashboard/campaign_detail.html',
        title=f'Campaign: {campaign.name}',
        campaign=campaign,
        stats=stats,
        flows=flows,
        recent_calls=recent_calls
    )


@dashboard_bp.route('/campaigns/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_campaign(id):
    """Toggle campaign active status"""
    campaign = Campaign.query.get_or_404(id)
    campaign.is_active = not campaign.is_active
    
    if campaign.is_active:
        campaign.started_at = datetime.utcnow()
        campaign.ended_at = None
        flash(f'Campaign "{campaign.name}" has been activated.', 'success')
    else:
        campaign.ended_at = datetime.utcnow()
        flash(f'Campaign "{campaign.name}" has been deactivated.', 'success')
    
    db.session.commit()
    return redirect(url_for('dashboard.campaign_detail', id=id))


@dashboard_bp.route('/calls')
@login_required
def calls():
    """View all call logs"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', None)
    sentiment = request.args.get('sentiment', None)
    language = request.args.get('language', None)
    
    # Build query with filters
    query = CallLog.query
    
    if status:
        query = query.filter_by(status=status)
    if sentiment:
        query = query.filter_by(sentiment=sentiment)
    if language:
        query = query.filter_by(language_used=language)
    
    # Paginate results
    calls = query.order_by(CallLog.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template(
        'dashboard/calls.html',
        title='Call Logs',
        calls=calls,
        status=status,
        sentiment=sentiment,
        language=language
    )


@dashboard_bp.route('/calls/<int:id>')
@login_required
def call_detail(id):
    """View call log details"""
    call = CallLog.query.get_or_404(id)
    
    # Get call events
    events = CallEvent.query.filter_by(call_log_id=call.id).order_by(CallEvent.timestamp).all()
    
    return render_template(
        'dashboard/call_detail.html',
        title=f'Call Log: {call.id}',
        call=call,
        events=events
    )


@dashboard_bp.route('/voters')
@login_required
def voters():
    """View voter lists"""
    voter_lists = VoterList.query.all()
    return render_template('dashboard/voters.html', title='Voter Lists', voter_lists=voter_lists)


@dashboard_bp.route('/voters/list/<int:id>')
@login_required
def voter_list_detail(id):
    """View voter list details"""
    voter_list = VoterList.query.get_or_404(id)
    
    # Get voters in this list with pagination
    page = request.args.get('page', 1, type=int)
    voters = Voter.query.join(
        'voter_list_entries'
    ).filter_by(
        voter_list_id=id
    ).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template(
        'dashboard/voter_list_detail.html',
        title=f'Voter List: {voter_list.name}',
        voter_list=voter_list,
        voters=voters
    )


@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """View analytics dashboard"""
    # Get date range from query parameters or default to last 7 days
    days = request.args.get('days', 7, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get call statistics for the date range
    call_stats = get_call_stats(start_date, end_date)
    
    # Get language distribution
    language_stats = db.session.query(
        CallLog.language_used, 
        db.func.count(CallLog.id)
    ).filter(
        CallLog.created_at.between(start_date, end_date)
    ).group_by(
        CallLog.language_used
    ).all()
    
    # Get sentiment distribution
    sentiment_stats = db.session.query(
        CallLog.sentiment, 
        db.func.count(CallLog.id)
    ).filter(
        CallLog.created_at.between(start_date, end_date)
    ).group_by(
        CallLog.sentiment
    ).all()
    
    return render_template(
        'dashboard/analytics.html',
        title='Analytics',
        days=days,
        call_stats=call_stats,
        language_stats=language_stats,
        sentiment_stats=sentiment_stats
    )


@dashboard_bp.route('/voters/<int:voter_id>')
@login_required
def voter_detail(voter_id):
    """View voter details"""
    voter = Voter.query.get_or_404(voter_id)
    voter_list = VoterList.query.get(voter.list_id)
    
    # Get call logs for this voter with pagination
    page = request.args.get('page', 1, type=int)
    call_logs = CallLog.query.filter_by(voter_id=voter_id).order_by(CallLog.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Generate insights if there are enough calls
    insights = None
    if CallLog.query.filter_by(voter_id=voter_id).count() >= 3:
        insights = generate_voter_insights(voter_id)
    
    return render_template(
        'dashboard/voter_detail.html',
        title=f'Voter: {voter.name or voter.phone_number}',
        voter=voter,
        voter_list=voter_list,
        call_logs=call_logs.items,
        pagination=call_logs,
        insights=insights
    )

@dashboard_bp.route('/voters/<int:voter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_voter(voter_id):
    """Edit a voter"""
    voter = Voter.query.get_or_404(voter_id)
    
    if request.method == 'POST':
        voter.name = request.form.get('name', '')
        voter.phone_number = request.form.get('phone_number')
        voter.location = request.form.get('location', '')
        voter.language_preference = request.form.get('language_preference', '')
        voter.notes = request.form.get('notes', '')
        voter.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Voter updated successfully', 'success')
        return redirect(url_for('dashboard.voter_detail', voter_id=voter_id))
    
    return render_template(
        'dashboard/edit_voter.html',
        title=f'Edit Voter: {voter.name or voter.phone_number}',
        voter=voter
    )

@dashboard_bp.route('/voters/<int:voter_id>/toggle-dnc', methods=['POST'])
@login_required
def toggle_do_not_call(voter_id):
    """Toggle do not call flag for a voter"""
    voter = Voter.query.get_or_404(voter_id)
    voter.do_not_call = not voter.do_not_call
    db.session.commit()
    
    flash(f'Do Not Call flag {"enabled" if voter.do_not_call else "disabled"} for this voter', 'success')
    return redirect(url_for('dashboard.voter_detail', voter_id=voter_id))

@dashboard_bp.route('/voters/<int:voter_id>/add-tag', methods=['POST'])
@login_required
def add_voter_tag(voter_id):
    """Add a tag to a voter"""
    voter = Voter.query.get_or_404(voter_id)
    tag = request.form.get('tag', '').strip()
    
    if not tag:
        flash('Tag cannot be empty', 'error')
        return redirect(url_for('dashboard.voter_detail', voter_id=voter_id))
    
    # Add tag to existing tags
    current_tags = voter.tags.split(',') if voter.tags else []
    current_tags = [t.strip() for t in current_tags if t.strip()]
    
    if tag not in current_tags:
        current_tags.append(tag)
        voter.tags = ','.join(current_tags)
        db.session.commit()
        flash(f'Tag "{tag}" added successfully', 'success')
    else:
        flash(f'Tag "{tag}" already exists', 'warning')
    
    return redirect(url_for('dashboard.voter_detail', voter_id=voter_id))

@dashboard_bp.route('/voters/<int:voter_id>/remove-tag/<string:tag>', methods=['POST'])
@login_required
def remove_voter_tag(voter_id, tag):
    """Remove a tag from a voter"""
    voter = Voter.query.get_or_404(voter_id)
    
    # Remove tag from existing tags
    current_tags = voter.tags.split(',') if voter.tags else []
    current_tags = [t.strip() for t in current_tags if t.strip()]
    
    if tag in current_tags:
        current_tags.remove(tag)
        voter.tags = ','.join(current_tags)
        db.session.commit()
        flash(f'Tag "{tag}" removed successfully', 'success')
    
    return redirect(url_for('dashboard.voter_detail', voter_id=voter_id))

@dashboard_bp.route('/voters/<int:voter_id>/test-call', methods=['GET'])
@login_required
def make_test_call(voter_id):
    """Make a test call to a voter"""
    voter = Voter.query.get_or_404(voter_id)
    
    # Create a test call log
    call_log = CallLog(
        voter_id=voter_id,
        campaign_id=None,  # Test call has no campaign
        status='initiated',
        created_by=current_user.id
    )
    
    db.session.add(call_log)
    db.session.commit()
    
    # Redirect to test call page
    return redirect(url_for('dashboard.test_call', call_id=call_log.id))

@dashboard_bp.route('/test-call/<int:call_id>')
@login_required
def test_call(call_id):
    """Test call interface"""
    call = CallLog.query.get_or_404(call_id)
    voter = Voter.query.get(call.voter_id)
    
    # Get available voice models
    voice_models = VoiceModel.query.filter_by(status='ready').all()
    
    return render_template(
        'dashboard/test_call.html',
        title='Test Call',
        call=call,
        voter=voter,
        voice_models=voice_models
    )

@dashboard_bp.route('/flows')
@login_required
def conversation_flows():
    """View conversation flows"""
    flows = ConversationFlow.query.all()
    return render_template(
        'dashboard/conversation_flows.html',
        title='Conversation Flows',
        flows=flows
    )

@dashboard_bp.route('/flows/<int:flow_id>/editor')
@login_required
def flow_editor(flow_id):
    """Conversation flow editor"""
    flow = ConversationFlow.query.get_or_404(flow_id)
    
    # Get flow data or initialize empty flow
    if flow.flow_data:
        flow_data = json.loads(flow.flow_data)
    else:
        # Initialize with a greeting node
        flow_data = {
            'nodes': [{
                'id': 'node_1',
                'type': 'greeting',
                'label': 'Greeting',
                'message': 'Hello, thank you for taking our call.',
                'position': {'x': 100, 'y': 100},
                'language': 'en'
            }],
            'connections': []
        }
    
    return render_template(
        'dashboard/flow_editor.html',
        title=f'Flow Editor: {flow.name}',
        flow=flow,
        flow_data=flow_data
    )

@dashboard_bp.route('/flows/<int:flow_id>/save', methods=['POST'])
@login_required
def save_flow(flow_id):
    """Save conversation flow"""
    flow = ConversationFlow.query.get_or_404(flow_id)
    
    # Get flow data from request
    flow_data = request.json
    
    # Validate flow data
    if not flow_data or 'nodes' not in flow_data or 'connections' not in flow_data:
        return jsonify({'success': False, 'error': 'Invalid flow data'})
    
    # Save flow data
    flow.flow_data = json.dumps(flow_data)
    flow.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

def generate_voter_insights(voter_id):
    """Generate insights for a voter based on call history"""
    # Get all completed calls for this voter
    calls = CallLog.query.filter_by(voter_id=voter_id, status='completed').order_by(CallLog.created_at).all()
    
    if not calls:
        return None
    
    # Prepare sentiment trend data
    sentiment_scores = []
    dates = []
    
    for call in calls:
        # Convert sentiment to score (0-100)
        if call.sentiment == 'positive':
            score = 80  # Range 70-100
        elif call.sentiment == 'neutral':
            score = 50  # Range 30-70
        elif call.sentiment == 'negative':
            score = 20  # Range 0-30
        else:
            score = 50  # Default
        
        sentiment_scores.append(score)
        dates.append(call.created_at.strftime('%Y-%m-%d'))
    
    # Prepare language usage data
    language_counts = {}
    for call in calls:
        if call.language_used:
            language_counts[call.language_used] = language_counts.get(call.language_used, 0) + 1
    
    language_labels = []
    language_data = []
    
    for lang, count in language_counts.items():
        if lang == 'en':
            language_labels.append('English')
        elif lang == 'sw':
            language_labels.append('Swahili')
        elif lang == 'lg':
            language_labels.append('Luganda')
        elif lang == 'ny':
            language_labels.append('Runyankole')
        else:
            language_labels.append(lang)
        
        language_data.append(count)
    
    # Mock topics for now (would be extracted from call transcripts in a real system)
    topics = [
        {'name': 'Healthcare', 'count': 3},
        {'name': 'Education', 'count': 2},
        {'name': 'Economy', 'count': 4},
        {'name': 'Infrastructure', 'count': 1},
        {'name': 'Security', 'count': 2}
    ]
    
    # Calculate engagement score (0-100)
    # Based on call duration, sentiment, and number of interactions
    avg_duration = sum(call.duration or 0 for call in calls) / len(calls) if calls else 0
    engagement_score = min(100, int((avg_duration / 120) * 50 + (sum(sentiment_scores) / len(sentiment_scores)) / 2))
    
    return {
        'sentiment_trend': {
            'labels': dates,
            'data': sentiment_scores
        },
        'language_usage': {
            'labels': language_labels,
            'data': language_data
        },
        'topics': topics,
        'engagement_score': engagement_score
    }

@dashboard_bp.route('/api/stats/calls')
@login_required
def api_call_stats():
    """API endpoint for call statistics (for AJAX charts)"""
    days = request.args.get('days', 7, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get daily call counts
    daily_calls = db.session.query(
        db.func.date(CallLog.created_at),
        db.func.count(CallLog.id)
    ).filter(
        CallLog.created_at.between(start_date, end_date)
    ).group_by(
        db.func.date(CallLog.created_at)
    ).all()
    
    # Format for chart.js
    labels = [date.strftime('%Y-%m-%d') for date, _ in daily_calls]
    data = [count for _, count in daily_calls]
    
    return jsonify({
        'labels': labels,
        'data': data
    })
