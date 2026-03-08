import uuid

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(self, user_message):
        session_id = str(uuid.uuid4())

        self.sessions[session_id] = {
            "original_prompt": user_message,
            "missing_fields": [],
            "collected_data": {},
            "state": "new"
        }

        return session_id

    def get(self, session_id):
        return self.sessions.get(session_id)

    def update_data(self, session_id, data):
        if session_id in self.sessions:
            self.sessions[session_id]["collected_data"].update(data)

    def set_missing_fields(self, session_id, fields):
        if session_id in self.sessions:
            self.sessions[session_id]["missing_fields"] = fields
            self.sessions[session_id]["state"] = "waiting_for_input"

    def clear_missing_fields(self, session_id):
        if session_id in self.sessions:
            self.sessions[session_id]["missing_fields"] = []
            self.sessions[session_id]["state"] = "ready"


session_manager = SessionManager()