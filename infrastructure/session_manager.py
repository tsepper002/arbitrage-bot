"""
Session Manager - User session management
Manages user sessions and authentication
"""
import logging
from typing import Dict, Optional
import time
import secrets

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions"""
    
    def __init__(self, session_timeout: int = 3600):
        self.sessions = {}
        self.session_timeout = session_timeout  # seconds
        logger.info("✅ SessionManager initialized")
    
    def create_session(self, user_id: str, metadata: Dict = None) -> str:
        """Create new session"""
        try:
            session_id = secrets.token_urlsafe(32)
            
            self.sessions[session_id] = {
                'user_id': user_id,
                'created': time.time(),
                'last_activity': time.time(),
                'metadata': metadata or {}
            }
            
            logger.info(f"Created session for user: {user_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return ""
    
    def validate_session(self, session_id: str) -> bool:
        """Validate session"""
        try:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            
            # Check if session expired
            if time.time() - session['last_activity'] > self.session_timeout:
                self.destroy_session(session_id)
                return False
            
            # Update last activity
            session['last_activity'] = time.time()
            return True
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data"""
        try:
            if not self.validate_session(session_id):
                return None
            
            return self.sessions[session_id].copy()
            
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def destroy_session(self, session_id: str) -> bool:
        """Destroy session"""
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Destroyed session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error destroying session: {e}")
            return False
    
    def cleanup_expired(self):
        """Clean up expired sessions"""
        try:
            current_time = time.time()
            expired = [
                sid for sid, session in self.sessions.items()
                if current_time - session['last_activity'] > self.session_timeout
            ]
            
            for session_id in expired:
                self.destroy_session(session_id)
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")

def get_session_manager():
    """Factory function"""
    return SessionManager()
