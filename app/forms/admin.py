from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, SelectField, IntegerField, HiddenField, DateTimeField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
import json

class APIConfigForm(FlaskForm):
    """Form for API configuration"""
    id = HiddenField('ID')
    name = SelectField('API Service', choices=[
        ('twilio', 'Twilio'),
        ('openai', 'OpenAI'),
        ('openvoice', 'OpenVoice')
    ], validators=[DataRequired()])
    config_data = TextAreaField('Configuration (JSON)', validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Configuration')
    
    def validate_config_data(self, field):
        """Validate that the config data is valid JSON"""
        try:
            json.loads(field.data)
        except json.JSONDecodeError:
            raise ValidationError('Invalid JSON format. Please check your configuration.')


class VoiceModelForm(FlaskForm):
    """Form for voice model management"""
    id = HiddenField('ID')
    name = StringField('Model Name', validators=[DataRequired(), Length(max=64)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    voice_file = FileField('Voice File', validators=[
        Optional(),
        FileAllowed(['wav', 'mp3'], 'Audio files only (.wav or .mp3)')
    ])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Voice Model')


class LanguageForm(FlaskForm):
    """Form for language management"""
    id = HiddenField('ID')
    name = StringField('Language Name', validators=[DataRequired(), Length(max=64)])
    code = StringField('Language Code', validators=[DataRequired(), Length(max=10)])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Language')


class ConversationFlowForm(FlaskForm):
    """Form for conversation flow management"""
    id = HiddenField('ID')
    name = StringField('Flow Name', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    flow_data = TextAreaField('Flow Structure (JSON)', validators=[DataRequired()])
    campaign_id = SelectField('Campaign', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Conversation Flow')
    
    def validate_flow_data(self, field):
        """Validate that the flow data is valid JSON"""
        try:
            json.loads(field.data)
        except json.JSONDecodeError:
            raise ValidationError('Invalid JSON format. Please check your flow structure.')


class CampaignForm(FlaskForm):
    """Form for campaign management"""
    id = HiddenField('ID')
    name = StringField('Campaign Name', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    is_active = BooleanField('Active')
    max_calls_per_day = IntegerField('Max Calls Per Day', default=1000)
    max_calls_per_hour = IntegerField('Max Calls Per Hour', default=100)
    retry_attempts = IntegerField('Retry Attempts', default=2)
    voice_model_id = SelectField('Voice Model', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Campaign')


class VoterListUploadForm(FlaskForm):
    """Form for uploading voter lists"""
    name = StringField('List Name', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    file = FileField('Voter List File', validators=[
        FileRequired(),
        FileAllowed(['csv', 'txt', 'xls', 'xlsx'], 'Spreadsheet files only (.csv, .txt, .xls, .xlsx)')
    ])
    submit = SubmitField('Upload Voter List')


class AudioClipForm(FlaskForm):
    """Form for audio clip management"""
    id = HiddenField('ID')
    name = StringField('Clip Name', validators=[DataRequired(), Length(max=128)])
    transcript = TextAreaField('Transcript', validators=[Optional()])
    step_id = StringField('Flow Step ID', validators=[DataRequired(), Length(max=64)])
    sentiment = SelectField('Sentiment', choices=[
        ('neutral', 'Neutral'),
        ('positive', 'Positive'),
        ('negative', 'Negative')
    ], validators=[DataRequired()])
    language_id = SelectField('Language', coerce=int, validators=[DataRequired()])
    conversation_flow_id = SelectField('Conversation Flow', coerce=int, validators=[DataRequired()])
    voice_model_id = SelectField('Voice Model', coerce=int, validators=[DataRequired()])
    audio_file = FileField('Audio File', validators=[
        Optional(),
        FileAllowed(['wav', 'mp3'], 'Audio files only (.wav or .mp3)')
    ])
    submit = SubmitField('Save Audio Clip')
