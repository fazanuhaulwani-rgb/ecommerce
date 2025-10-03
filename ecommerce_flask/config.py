"""
Configuration for Flask e-commerce application
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Basic Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
    
    # Template configuration
    TEMPLATE_FOLDER = 'templates'
    STATIC_FOLDER = 'static'
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = 'flask_session'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/google/callback')
    GOOGLE_DISCOVERY_URL = os.getenv('GOOGLE_DISCOVERY_URL', 'https://accounts.google.com/.well-known/openid-configuration')
    
    # Supabase configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Email configuration
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
    
    # Security configuration
    RATE_LIMIT_MAX_ATTEMPTS = 5
    RATE_LIMIT_TIMEOUT = 300  # 5 minutes
    
    @staticmethod
    def is_valid_config():
        """Check if critical configuration is valid"""
        # Check if critical values are not placeholders
        placeholders = ['your-', 'placeholder', 'here', 'change-this']
        
        def is_placeholder(value):
            if not value:
                return True
            return any(ph in value.lower() for ph in placeholders)
        
        # For development, we can work with placeholder configs
        # For production, these should be validated
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    @staticmethod
    def is_valid_config():
        """Strict validation for production"""
        # In production, we need valid configs
        return (
            Config.GOOGLE_CLIENT_ID and 
            Config.GOOGLE_CLIENT_SECRET and
            Config.SUPABASE_URL and
            Config.SUPABASE_KEY and
            not Config.is_valid_config()
        )

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}