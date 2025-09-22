from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import os
import uuid
from datetime import datetime
import logging

# Import your ORIGINAL travel assistant (keep using your existing file)
try:
    from travel_assistant import RealAPITravelAssistant, detect_available_providers
    TRAVEL_ASSISTANT_AVAILABLE = True
except ImportError:
    try:
        # Fallback to original if enhanced version has issues
        from travel_assistant import RealAPITravelAssistant, detect_available_providers
        RealAPITravelAssistant = RealAPITravelAssistant
        TRAVEL_ASSISTANT_AVAILABLE = True
    except ImportError as e:
        print(f"Could not import travel_assistant: {e}")
        TRAVEL_ASSISTANT_AVAILABLE = False

# FastAPI app
app = FastAPI(
    title="Atlas AI Travel Assistant API",
    description="Full-featured travel planning with all original Streamlit features",
    version="1.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Global state (like your original Streamlit session state)
travel_assistant: Optional[RealAPITravelAssistant] = None
sessions_state = {}

# Request/Response models that match your original functionality
class InitializeRequest(BaseModel):
    provider: str
    api_key: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    current_step: str
    awaiting_user_choice: bool
    trip_progress: Optional[Dict[str, Any]] = None
    api_calls_made: Optional[List[str]] = None
    chat_state: Optional[Dict[str, Any]] = None

# Auto-initialization (like your original startup)
@app.on_event("startup")
async def startup_event():
    global travel_assistant
    
    print("🚀 Starting Atlas AI Travel Assistant with full original features...")
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        print("⚠️ Travel assistant not available")
        return
    
    # Try auto-initialization like your original Streamlit app
    available_providers = detect_available_providers()
    
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if openai_key and "OpenAI" in available_providers:
        try:
            travel_assistant = RealAPITravelAssistant("openai", openai_key)
            print("✅ Auto-initialized with OpenAI")
        except Exception as e:
            print(f"⚠️ OpenAI initialization failed: {e}")
    elif gemini_key and "Gemini" in available_providers:
        try:
            travel_assistant = RealAPITravelAssistant("gemini", gemini_key)
            print("✅ Auto-initialized with Gemini")
        except Exception as e:
            print(f"⚠️ Gemini initialization failed: {e}")

# Full web interface (recreating your Streamlit functionality)
@app.get("/", response_class=HTMLResponse)
async def get_web_interface():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Atlas AI Travel Assistant - Full Features</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f0f2f6; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .sidebar { width: 300px; float: left; background: white; padding: 20px; border-radius: 10px; margin-right: 20px; }
        .main-content { margin-left: 340px; background: white; padding: 20px; border-radius: 10px; min-height: 600px; }
        .chat-container { height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; background: #fafafa; }
        .message { margin-bottom: 15px; padding: 10px; border-radius: 8px; }
        .user-message { background: #e3f2fd; margin-left: 20%; }
        .assistant-message { background: #f5f5f5; margin-right: 20%; }
        .input-container { display: flex; gap: 10px; }
        input[type="text"], select { padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { padding: 10px 15px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #5a6fd8; }
        button:disabled { background: #ccc; }
        .api-status { padding: 10px; margin: 5px 0; border-radius: 5px; font-size: 14px; }
        .api-connected { background: #d4edda; color: #155724; }
        .api-missing { background: #f8d7da; color: #721c24; }
        .status-indicator { padding: 5px 10px; border-radius: 3px; font-size: 12px; margin-left: 10px; }
        .step-indicator { background: #e8f5e8; padding: 10px; border-left: 4px solid #4caf50; margin: 10px 0; }
        .progress-bar { width: 100%; background: #f0f0f0; border-radius: 10px; margin: 10px 0; }
        .progress-fill { height: 20px; background: #4caf50; border-radius: 10px; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Atlas AI Travel Assistant</h1>
            <p>Full-Featured Travel Planning with Real API Integration</p>
        </div>
        
        <div class="sidebar">
            <h3>🔧 AI Provider Setup</h3>
            <div id="provider-selection">
                <select id="provider-select">
                    <option value="">Select AI Provider...</option>
                    <option value="openai">OpenAI GPT-3.5 (Premium)</option>
                    <option value="gemini">Google Gemini (FREE)</option>
                </select>
                <br><br>
                <input type="password" id="api-key-input" placeholder="Enter API Key...">
                <br><br>
                <button onclick="initializeSystem()">🚀 Initialize Atlas AI</button>
            </div>
            
            <div id="system-status" style="margin-top: 20px;">
                <h3>📊 System Status</h3>
                <div id="api-status-list"></div>
            </div>
            
            <div id="trip-progress" style="margin-top: 20px;">
                <h3>🧳 Trip Progress</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                </div>
                <div id="progress-details"></div>
            </div>
            
            <button onclick="resetPlanning()" style="background: #dc3545; margin-top: 10px;">🗑️ Reset Planning</button>
        </div>
        
        <div class="main-content">
            <div id="step-indicator" class="step-indicator" style="display: none;">
                <strong>Current Step:</strong> <span id="current-step-text">Initial Planning</span>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message assistant-message">
                    <strong>🤖 Atlas AI:</strong> Welcome! I'm your AI travel assistant with real API integrations. Configure your AI provider in the sidebar to begin planning your trip with live flight, hotel, and attraction data.
                </div>
            </div>
            
            <div class="input-container">
                <input type="text" id="message-input" placeholder="Tell me about your travel plans..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" id="send-btn" disabled>Send</button>
            </div>
            
            <div style="margin-top: 15px;">
                <h4>Quick Start Examples:</h4>
                <button onclick="sendQuickMessage('Plan a cultural trip from Boston to Rome for 7 days, budget $3500')" class="quick-btn" style="margin: 5px; background: #28a745;">🇮🇹 Rome Cultural</button>
                <button onclick="sendQuickMessage('I want to go to Paris for 5 days from New York, budget $2500')" class="quick-btn" style="margin: 5px; background: #28a745;">🇫🇷 Paris Romantic</button>
                <button onclick="sendQuickMessage('Business trip to London for 4 days, efficient schedule')" class="quick-btn" style="margin: 5px; background: #28a745;">🇬🇧 London Business</button>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        let isInitialized = false;
        let currentChatState = null;

        // Initialize on page load
        window.onload = function() {
            checkSystemStatus();
            loadAvailableProviders();
        };

        async function checkSystemStatus() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                updateAPIStatus(data.apis_configured);
                
                if (data.travel_assistant_loaded) {
                    isInitialized = true;
                    document.getElementById('send-btn').disabled = false;
                    updateStepIndicator('Auto-initialized from .env file', false);
                    
                    // Hide the manual initialization form
                    document.getElementById('provider-selection').innerHTML = `
                        <div style="background: #d4edda; padding: 10px; border-radius: 5px; color: #155724;">
                            ✅ System auto-initialized from .env file<br>
                            Current provider: ${data.current_provider || 'Unknown'}
                        </div>
                    `;
                    
                    addMessage('System is ready! Your .env file API keys were loaded automatically. Start planning your trip!', 'assistant');
                } else {
                    // Show manual form only if auto-init failed
                    addMessage('Auto-initialization from .env failed. Please manually select your AI provider and enter API key.', 'assistant');
                }
            } catch (error) {
                console.error('Health check failed:', error);
                addMessage('Cannot connect to server. Make sure FastAPI is running.', 'assistant');
            }
        }

        async function loadAvailableProviders() {
            try {
                const response = await fetch('/config');
                const data = await response.json();
                
                const select = document.getElementById('provider-select');
                select.innerHTML = '<option value="">Select AI Provider...</option>';
                
                Object.entries(data.available_ai_providers || {}).forEach(([name, value]) => {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = name + (name === 'Gemini' ? ' (FREE)' : '');
                    select.appendChild(option);
                });
                
            } catch (error) {
                console.error('Failed to load providers:', error);
            }
        }

        async function initializeSystem() {
            const provider = document.getElementById('provider-select').value;
            const apiKey = document.getElementById('api-key-input').value;
            
            if (!provider || !apiKey) {
                alert('Please select a provider and enter an API key');
                return;
            }

            try {
                const response = await fetch('/initialize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, api_key: apiKey })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    isInitialized = true;
                    document.getElementById('send-btn').disabled = false;
                    addMessage(`✅ System initialized with ${data.provider}! Ready for travel planning.`, 'assistant');
                    updateStepIndicator('System Ready', false);
                } else {
                    alert(`Initialization failed: ${data.detail}`);
                }
            } catch (error) {
                alert(`Initialization error: ${error.message}`);
            }
        }

        async function sendMessage() {
            if (!isInitialized) {
                alert('Please initialize the system first');
                return;
            }

            const input = document.getElementById('message-input');
            const message = input.value.trim();
            if (!message) return;

            if (!sessionId) sessionId = 'session-' + Math.random().toString(36).substr(2, 9);

            addMessage(message, 'user');
            input.value = '';
            document.getElementById('send-btn').disabled = true;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message, session_id: sessionId })
                });
                
                const data = await response.json();
                
                if (response.ok && data.response) {
                    addMessage(data.response, 'assistant');
                    updateStepIndicator(data.current_step, data.awaiting_user_choice);
                    updateTripProgress(data.trip_progress);
                    currentChatState = data.chat_state;
                } else {
                    addMessage('Sorry, there was an error processing your request. Please check the server logs.', 'assistant');
                }
            } catch (error) {
                addMessage('Connection error. Please ensure the server is running.', 'assistant');
            } finally {
                document.getElementById('send-btn').disabled = false;
            }
        }

        function sendQuickMessage(message) {
            document.getElementById('message-input').value = message;
            sendMessage();
        }

        function addMessage(text, sender) {
            const container = document.getElementById('chat-container');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;
            
            const senderName = sender === 'user' ? 'You' : '🤖 Atlas AI';
            messageDiv.innerHTML = `<strong>${senderName}:</strong> ${text}`;
            
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }

        function updateAPIStatus(apis) {
            const statusContainer = document.getElementById('api-status-list');
            statusContainer.innerHTML = '';
            
            Object.entries(apis || {}).forEach(([api, status]) => {
                const statusDiv = document.createElement('div');
                statusDiv.className = `api-status ${status === 'configured' ? 'api-connected' : 'api-missing'}`;
                
                const icon = status === 'configured' ? '✅' : '❌';
                const statusText = status === 'configured' ? 'Ready' : 'Not configured';
                
                statusDiv.textContent = `${icon} ${api}: ${statusText}`;
                statusContainer.appendChild(statusDiv);
            });
        }

        function updateStepIndicator(step, awaiting) {
            const indicator = document.getElementById('step-indicator');
            const stepText = document.getElementById('current-step-text');
            
            if (step && step !== 'initial') {
                indicator.style.display = 'block';
                stepText.textContent = step + (awaiting ? ' - Waiting for your choice...' : '');
            } else {
                indicator.style.display = 'none';
            }
        }

        function updateTripProgress(progress) {
            if (!progress) return;
            
            const progressFill = document.getElementById('progress-fill');
            const progressDetails = document.getElementById('progress-details');
            
            let completed = 0;
            let total = 7; // Total steps in travel planning
            let details = [];
            
            if (progress.origin) { completed++; details.push(`From: ${progress.origin}`); }
            if (progress.destination) { completed++; details.push(`To: ${progress.destination}`); }
            if (progress.duration_days) { completed++; details.push(`${progress.duration_days} days`); }
            if (progress.has_flight) { completed++; details.push('✈️ Flight selected'); }
            if (progress.has_hotel) { completed++; details.push('🏨 Hotel selected'); }
            if (progress.trip_style) { completed++; details.push(`Style: ${progress.trip_style}`); }
            
            const percentage = (completed / total) * 100;
            progressFill.style.width = percentage + '%';
            progressDetails.innerHTML = details.join('<br>');
        }

        function resetPlanning() {
            if (confirm('Reset current travel planning session?')) {
                sessionId = null;
                currentChatState = null;
                document.getElementById('chat-container').innerHTML = `
                    <div class="message assistant-message">
                        <strong>🤖 Atlas AI:</strong> Session reset! Ready to plan a new trip.
                    </div>
                `;
                updateStepIndicator('', false);
                updateTripProgress(null);
                document.getElementById('progress-fill').style.width = '0%';
                document.getElementById('progress-details').innerHTML = '';
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') sendMessage();
        }
    </script>
</body>
</html>
    """

# All your original API endpoints with full functionality
@app.post("/initialize")
async def initialize_system(request: InitializeRequest):
    global travel_assistant
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        raise HTTPException(status_code=500, detail="Travel assistant module not available")
    
    try:
        available_providers = detect_available_providers()
        provider_values = [p.lower() for p in available_providers.values()]
        
        if request.provider.lower() not in provider_values:
            raise HTTPException(status_code=400, detail=f"Provider not available")
        
        travel_assistant = RealAPITravelAssistant(request.provider, request.api_key)
        
        return {
            "status": "success",
            "provider": request.provider,
            "message": f"Atlas AI initialized with {request.provider.title()}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not travel_assistant:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Use your original chat_with_persistence method
        result = travel_assistant.chat_with_persistence(
            user_input=request.message,
            session_id=session_id
        )
        
        # Get trip progress like your original Streamlit app
        session_info = travel_assistant.get_session_info(session_id)
        trip_progress = session_info.get('trip_details') if session_info else None
        
        # Determine API calls made
        api_calls_made = []
        if result.get("flight_options"): api_calls_made.append("AviationStack (flights)")
        if result.get("hotel_options"): api_calls_made.append("Booking.com (hotels)")
        if result.get("attractions_data"): api_calls_made.append("OpenStreetMap (attractions)")
        
        return ChatResponse(
            response=result.get("response", ""),
            session_id=session_id,
            current_step=result.get("current_step", "initial"),
            awaiting_user_choice=result.get("awaiting_user_choice", False),
            trip_progress=trip_progress,
            api_calls_made=api_calls_made,
            chat_state=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    apis_configured = {
        "openai": "configured" if os.getenv("OPENAI_API_KEY") else "not_configured",
        "gemini": "configured" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "not_configured",
        "flight_api": "configured" if os.getenv("FLIGHT_API_KEY") else "not_configured",
        "hotel_api": "configured" if os.getenv("RAPIDAPI_KEY") else "not_configured",
        "places_api": "free_openstreetmap_available"
    }
    
    return {
        "status": "healthy",
        "travel_assistant_loaded": travel_assistant is not None,
        "current_provider": getattr(travel_assistant, 'provider', None) if travel_assistant else None,
        "apis_configured": apis_configured,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/config")
async def get_config():
    available_providers = detect_available_providers() if TRAVEL_ASSISTANT_AVAILABLE else {}
    return {
        "available_ai_providers": available_providers,
        "current_provider": getattr(travel_assistant, 'provider', None) if travel_assistant else None
    }

@app.get("/sessions")
async def list_sessions():
    if not travel_assistant:
        return {"sessions": []}
    return {"sessions": travel_assistant.list_sessions()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_travel_app:app", host="0.0.0.0", port=8000, reload=True)