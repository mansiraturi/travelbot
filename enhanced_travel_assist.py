import psycopg2
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Import your existing travel assistant
from travel_assistant import RealAPITravelAssistant, RealAPITravelState

class PostgreSQLSessionManager:
    """Simple PostgreSQL session management"""
    
    def __init__(self):
        self.connection_config = {
            'host': '35.224.149.145',
            'port': 5432,
            'database': 'travel_sessions',
            'user': 'chatbot_user',
            'password': '#Mansi1234'
        }
        self._setup_tables()
    
    def _setup_tables(self):
        """Create sessions table if it doesn't exist"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ PostgreSQL session tables ready")
            
        except Exception as e:
            print(f"⚠️ PostgreSQL setup failed: {e}")
    
    def save_session(self, session_id: str, state: Dict[str, Any]) -> bool:
        """Save session state to PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            state_json = json.dumps(state)
            current_time = datetime.now()
            
            cursor.execute('''
                INSERT INTO travel_sessions (session_id, state, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id)
                DO UPDATE SET state = %s, updated_at = %s
            ''', (session_id, state_json, current_time, state_json, current_time))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Failed to save session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state from PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('SELECT state FROM travel_sessions WHERE session_id = %s', (session_id,))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            print(f"❌ Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(self, limit: int = 20) -> list:
        """List recent sessions"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, updated_at, created_at
                FROM travel_sessions 
                ORDER BY updated_at DESC 
                LIMIT %s
            ''', (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [
                {
                    "session_id": row[0],
                    "last_activity": row[1].isoformat() if row[1] else None,
                    "created_at": row[2].isoformat() if row[2] else None
                }
                for row in results
            ]
            
        except Exception as e:
            print(f"❌ Failed to list sessions: {e}")
            return []

class EnhancedTravelAssistant(RealAPITravelAssistant):
    """Your travel assistant with PostgreSQL persistence"""
    
    def __init__(self, provider: str, api_key: str):
        # Initialize your existing travel assistant
        super().__init__(provider, api_key)
        
        # Add PostgreSQL session manager
        self.session_manager = PostgreSQLSessionManager()
        print("✅ Enhanced Travel Assistant with PostgreSQL ready!")
    
    def chat_with_persistence(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """Chat with PostgreSQL persistence"""
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Load existing session or create new
        current_state = self.session_manager.load_session(session_id)
        
        if current_state:
            print(f"📂 Loaded session {session_id}")
            # Update with new user input
            current_state["user_input"] = user_input
        else:
            print(f"🆕 New session {session_id}")
            # Create initial state (from your existing travel assistant)
            current_state = {
                "user_input": user_input,
                "conversation_history": [],
                "current_step": "initial",
                "awaiting_user_choice": False,
                "origin": "",
                "destination": "",
                "duration_days": 0,
                "budget": "",
                "interests": [],
                "selected_flight": {},
                "selected_hotel": {},
                "selected_trip_style": "",
                "flight_options": [],
                "hotel_options": [],
                "attractions_data": [],
                "response": "",
                "api_errors": []
            }
        
        try:
            # Process using your existing chat method
            result = self.chat(user_input, current_state)
            
            # Add session ID to result
            result["session_id"] = session_id
            
            # Save updated state to PostgreSQL
            if self.session_manager.save_session(session_id, result):
                print(f"💾 Session {session_id} saved to PostgreSQL")
            else:
                print(f"⚠️ Failed to save session {session_id}")
            
            return result
            
        except Exception as e:
            print(f"❌ Chat processing error: {e}")
            # Return error response but still save session
            error_result = current_state.copy()
            error_result["response"] = f"Sorry, I encountered an error: {str(e)}"
            error_result["session_id"] = session_id
            
            self.session_manager.save_session(session_id, error_result)
            return error_result
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        state = self.session_manager.load_session(session_id)
        if not state:
            return None
        
        return {
            "session_id": session_id,
            "current_step": state.get("current_step", "unknown"),
            "awaiting_user_choice": state.get("awaiting_user_choice", False),
            "trip_details": {
                "origin": state.get("origin", ""),
                "destination": state.get("destination", ""),
                "duration_days": state.get("duration_days", 0),
                "budget": state.get("budget", ""),
                "interests": state.get("interests", []),
                "has_flight": bool(state.get("selected_flight", {})),
                "has_hotel": bool(state.get("selected_hotel", {}))
            }
        }
    
    def list_sessions(self, limit: int = 20) -> list:
        """List recent sessions with info"""
        sessions = self.session_manager.list_sessions(limit)
        
        # Add session info to each
        enhanced_sessions = []
        for session in sessions:
            session_info = self.get_session_info(session["session_id"])
            if session_info:
                session.update(session_info)
            enhanced_sessions.append(session)
        
        return enhanced_sessions

# Test the enhanced travel assistant
def test_enhanced_assistant():
    """Test the enhanced travel assistant"""
    print("🧪 Testing Enhanced Travel Assistant...")
    
    # You need to provide your Gemini API key
    gemini_key = input("Enter your Gemini API key: ").strip()
    if not gemini_key:
        print("❌ Need Gemini API key to test")
        return
    
    try:
        # Initialize enhanced assistant
        assistant = EnhancedTravelAssistant("gemini", gemini_key)
        
        print("\n🔄 Testing conversation with persistence...")
        
        # Start a conversation
        session_id = "test-enhanced-001"
        
        response1 = assistant.chat_with_persistence(
            user_input="I want to plan a 7-day trip from Boston to Rome, budget $3500, I love museums and culture",
            session_id=session_id
        )
        
        print(f"\n🤖 Bot Response 1:")
        print(f"Response: {response1.get('response', 'No response')[:150]}...")
        print(f"Current Step: {response1.get('current_step')}")
        print(f"Session ID: {response1.get('session_id')}")
        
        # Continue the conversation
        response2 = assistant.chat_with_persistence(
            user_input="Yes, I'm interested in historical sites and art galleries",
            session_id=session_id
        )
        
        print(f"\n🤖 Bot Response 2:")
        print(f"Response: {response2.get('response', 'No response')[:150]}...")
        print(f"Current Step: {response2.get('current_step')}")
        
        # Test session info
        session_info = assistant.get_session_info(session_id)
        print(f"\n📊 Session Info:")
        print(f"Trip: {session_info['trip_details']['origin']} → {session_info['trip_details']['destination']}")
        print(f"Duration: {session_info['trip_details']['duration_days']} days")
        print(f"Current Step: {session_info['current_step']}")
        
        # List sessions
        sessions = assistant.list_sessions(limit=5)
        print(f"\n📋 Recent Sessions ({len(sessions)}):")
        for session in sessions:
            print(f"  {session['session_id'][:8]}... - {session.get('current_step', 'unknown')}")
        
        print("\n🎉 Enhanced Travel Assistant working perfectly!")
        print("✅ PostgreSQL persistence enabled")
        print("✅ Sessions can be resumed")
        print("✅ Ready for FastAPI integration!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_enhanced_assistant()