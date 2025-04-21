from queue import Queue
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime
import threading
import uuid
import json

@dataclass
class ProcessingSession:
    session_id: str
    message_queue: Queue
    created_at: datetime
    is_active: bool = True

class MessageBroker:
    def __init__(self):
        self._sessions: dict[str, ProcessingSession] = {}
        self._cleanup_thread = threading.Thread(target=self._cleanup_old_sessions, daemon=True)
        self._cleanup_thread.start()
    
    def create_session(self) -> ProcessingSession:
        """Create a new processing session"""
        session_id = str(uuid.uuid4())
        session = ProcessingSession(
            session_id=session_id,
            message_queue=Queue(),
            created_at=datetime.now()
        )
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ProcessingSession]:
        """Get an existing session by ID"""
        return self._sessions.get(session_id)
    
    def send_update(self, session_id: str, message: str, message_type: str = "update", data: Any = None):
        """Send an update message to a specific session"""
        if session := self.get_session(session_id):
            # Try to parse data as JSON if it's a string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass
                    
            session.message_queue.put({
                "type": message_type,
                "content": message,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
    
    def close_session(self, session_id: str):
        """Mark a session as complete and send final message"""
        if session := self.get_session(session_id):
            session.is_active = False
            session.message_queue.put(None)  # Sentinel value
    
    def _cleanup_old_sessions(self):
        """Periodically clean up old sessions"""
        import time
        while True:
            current_time = datetime.now()
            for session_id, session in list(self._sessions.items()):
                if not session.is_active and (current_time - session.created_at).seconds > 3600:
                    del self._sessions[session_id]
            time.sleep(300)  # Clean up every 5 minutes

# Global message broker instance
message_broker = MessageBroker()