from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import os
import uuid
import psycopg2
from datetime import datetime

# Import the ENHANCED travel assistant
try:
    from travel_assistant import EnhancedTravelAssistant, detect_available_providers
    TRAVEL_ASSISTANT_AVAILABLE = True
    print("Successfully imported EnhancedTravelAssistant")
except ImportError as e:
    print(f"Could not import EnhancedTravelAssistant: {e}")
    TRAVEL_ASSISTANT_AVAILABLE = False

# Import MCP tools - ONLY ADDITION
try:
    from travel_mcp_server import search_flights, search_hotels, search_attractions, manage_session
    MCP_TOOLS_AVAILABLE = True
    print("MCP Travel Tools integrated successfully")
except ImportError as e:
    MCP_TOOLS_AVAILABLE = False
    print(f"MCP import failed: {e}")

app = FastAPI(title="Atlas AI Travel Assistant - Complete", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Global travel assistant
travel_assistant: Optional[EnhancedTravelAssistant] = None

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    current_step: str
    awaiting_user_choice: bool
    trip_progress: Optional[Dict[str, Any]] = None

class InitializeRequest(BaseModel):
    provider: str
    api_key: str

class ResumeSessionRequest(BaseModel):
    session_id: str

# Manual initialization only - no auto-initialization
@app.on_event("startup")
async def startup_event():
    global travel_assistant
    
    print("Starting Atlas AI - Manual LLM selection enabled")
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        print("EnhancedTravelAssistant not available")
        return
    
    # Don't auto-initialize - force manual selection
    travel_assistant = None
    print("Manual initialization required - choose your AI provider")

# Complete web interface with clickable chat history - YOUR ORIGINAL WITH TINY MCP ADDITION
@app.get("/", response_class=HTMLResponse)
async def get_web_interface():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Atlas AI - Enhanced with Chat History</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 15px; margin-bottom: 25px; text-align: center; box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .sidebar { width: 350px; float: left; background: white; padding: 25px; border-radius: 15px; margin-right: 25px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .main-content { margin-left: 400px; background: white; padding: 25px; border-radius: 15px; min-height: 600px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .chat-container { height: 500px; overflow-y: auto; border: 2px solid #e9ecef; padding: 20px; margin-bottom: 20px; background: #fafbfc; border-radius: 10px; }
        .message { margin-bottom: 15px; padding: 12px; border-radius: 10px; }
        .user-message { background: linear-gradient(135deg, #e3f2fd, #bbdefb); margin-left: 15%; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .assistant-message { background: linear-gradient(135deg, #f5f5f5, #eeeeee); margin-right: 15%; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .input-container { display: flex; gap: 10px; }
        input, select, button { padding: 12px; border: 2px solid #e9ecef; border-radius: 8px; font-size: 14px; }
        button { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border: none; cursor: pointer; font-weight: 600; transition: all 0.3s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
        button:disabled { background: #ccc; transform: none; box-shadow: none; }
        .provider-card { margin: 15px 0; padding: 18px; border: 2px solid #e9ecef; border-radius: 12px; cursor: pointer; transition: all 0.3s; }
        .provider-card:hover { border-color: #667eea; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .provider-card.selected { border-color: #667eea; background: linear-gradient(135deg, #e3f2fd, #f0f8ff); }
        .api-status { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin: 4px 0; border-radius: 6px; font-size: 13px; }
        .api-connected { background: #d4edda; color: #155724; }
        .api-missing { background: #f8d7da; color: #721c24; }
        .session-panel { background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 15px 0; }
        .progress-indicator { background: #e8f5e8; padding: 12px; border-left: 4px solid #4caf50; margin: 15px 0; border-radius: 5px; }
        .step-indicator { background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0; border-radius: 5px; }
        .chat-history-item { border: 1px solid #ddd; padding: 12px; margin: 8px 0; border-radius: 8px; cursor: pointer; background: #f8f9fa; transition: all 0.3s; }
        .chat-history-item:hover { background: #e3f2fd; border-color: #667eea; transform: translateY(-1px); box-shadow: 0 3px 10px rgba(0,0,0,0.1); }
        .status { padding: 12px; margin: 8px 0; border-radius: 8px; font-size: 14px; }
        .success { background: linear-gradient(135deg, #d4edda, #c3e6cb); color: #155724; border: 1px solid #c3e6cb; }
        .error { background: linear-gradient(135deg, #f8d7da, #f1b0b7); color: #721c24; border: 1px solid #f1b0b7; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Atlas AI Travel Assistant</h1>
            <p>Enhanced with PostgreSQL Session Persistence & Clickable Chat History</p>
            <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 10px; margin-top: 15px;">
                LangGraph Multi-Agent • PostgreSQL Sessions • Real API Integration • Resume Conversations • MCP Tools
            </div>
        </div>
        
        <div class="sidebar">
            <h3>AI Model Selection</h3>
            <div id="provider-section">
                <select id="provider-select" style="width: 100%; margin-bottom: 15px; padding: 12px; border: 2px solid #e9ecef; border-radius: 8px;">
                    <option value="">Choose AI Provider</option>
                    <option value="openai">OpenAI GPT-3.5 Turbo</option>
                    <option value="gemini">Google Gemini</option>
                </select>
                
                <input type="password" id="api-key-input" placeholder="API key (or leave blank if in .env)..." style="width: 100%; margin-bottom: 15px; display: none;">
                <button onclick="initializeSystem()" id="init-btn" style="width: 100%; display: none;">
                    Initialize System
                </button>
            </div>
            
            <div id="system-status">
                <h3>System Status</h3>
                <div id="status-display">Checking...</div>
                
                <h4 style="margin-top: 20px;">API Configuration</h4>
                <div id="api-list"></div>
            </div>
            
            <div class="session-panel" id="session-info">
                <h3>Chat History</h3>
                <div id="session-details">Loading conversation history...</div>
                <button onclick="listSessions()" style="width: 100%; margin-top: 10px; background: #17a2b8;">
                    Show Chat History
                </button>
                <button onclick="checkDatabaseStatus()" style="width: 100%; margin-top: 5px; background: #28a745;">
                    Database Status
                </button>
                <button onclick="clearAllSessions()" style="width: 100%; margin-top: 5px; background: #dc3545;">
                    Clear All History
                </button>
                <button onclick="testMCPTools()" style="width: 100%; margin-top: 5px; background: #fd7e14;">
                    Test MCP Tools
                </button>
            </div>
            
            <div id="trip-progress" style="margin-top: 20px; display: none;">
                <h3>Current Trip</h3>
                <div id="trip-details">No active trip</div>
            </div>
        </div>
        
        <div class="main-content">
            <div id="step-indicator" class="step-indicator" style="display: none;">
                <strong>Current Step:</strong> <span id="step-text">Initial</span>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message assistant-message">
                    <strong>Atlas AI Enhanced:</strong> 
                    Welcome to the enhanced travel assistant with clickable chat history!
                    <br><br>
                    <strong>New Features:</strong><br>
                    Resume any conversation by clicking it in the chat history<br>
                    PostgreSQL automatically saves all conversation states<br>
                    Real API integration with no hardcoded data<br>
                    LangGraph multi-agent workflow<br>
                    MCP modular tools integration<br>
                    <br>
                    <strong>Choose your AI model in the sidebar to begin!</strong>
                </div>
            </div>
            
            <div class="input-container">
                <input type="text" id="message-input" placeholder="Choose your AI model first, then tell me about your travel plans..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()" id="send-btn" disabled>Send</button>
            </div>
            
            <div style="margin-top: 20px;">
                <h4>Test Enhanced Features:</h4>
                <button onclick="sendQuickMessage('Plan a 7-day cultural trip from Boston to Rome, budget $3500')" style="margin: 5px; background: #28a745;">
                    Rome Cultural Trip
                </button>
                <button onclick="sendQuickMessage('Business trip from Dallas to Chicago for 5 days')" style="margin: 5px; background: #28a745;">
                    Chicago Business
                </button>
                <button onclick="sendQuickMessage('I want to visit Tokyo for 10 days, love technology and culture')" style="margin: 5px; background: #28a745;">
                    Tokyo Adventure
                </button>
                <button onclick="startNewConversation()" style="margin: 5px; background: #6f42c1;">
                    Start New Conversation
                </button>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        let isInitialized = false;
        let selectedProvider = null;

        window.onload = function() {
            checkSystemStatus();
            loadSessionInfo();
            
            // Handle dropdown selection
            const select = document.getElementById('provider-select');
            select.addEventListener('change', function() {
                if (this.value) {
                    selectProvider(this.value);
                } else {
                    document.getElementById('api-key-input').style.display = 'none';
                    document.getElementById('init-btn').style.display = 'none';
                }
            });
        };

        function selectProvider(provider) {
            selectedProvider = provider;
            
            document.getElementById('api-key-input').style.display = 'block';
            document.getElementById('init-btn').style.display = 'block';
            
            const input = document.getElementById('api-key-input');
            if (provider === 'openai') {
                input.placeholder = 'OpenAI API key (or leave blank if in .env)...';
            } else {
                input.placeholder = 'Gemini API key (or leave blank if in .env)...';
            }
        }

        async function checkSystemStatus() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                document.getElementById('status-display').innerHTML = `
                    Status: <strong>${data.status}</strong><br>
                    Provider: <strong>${data.current_provider || 'None'}</strong><br>
                    PostgreSQL: <strong>${data.postgresql_status || 'Unknown'}</strong>
                `;
                
                // Update API status
                const apiList = document.getElementById('api-list');
                apiList.innerHTML = '';
                
                Object.entries(data.apis_configured || {}).forEach(([api, status]) => {
                    const div = document.createElement('div');
                    div.className = `api-status ${status === 'configured' ? 'api-connected' : 'api-missing'}`;
                    const icon = status === 'configured' ? 'Yes' : 'No';
                    div.innerHTML = `<span>${api}</span> <span>${icon}</span>`;
                    apiList.appendChild(div);
                });
                
                // Check if system is already initialized - YOUR ORIGINAL LOGIC
                if (data.travel_assistant_loaded) {
                    isInitialized = true;
                    document.getElementById('send-btn').disabled = false;
                    
                    // Hide provider selection, show current provider
                    document.getElementById('provider-section').innerHTML = `
                        <div class="status success">
                            System initialized with <strong>${data.current_provider?.toUpperCase()}</strong><br>
                            PostgreSQL session persistence active
                        </div>
                        <button onclick="showProviderSelection()" style="width: 100%; margin-top: 10px; background: #6c757d;">
                            Change AI Provider
                        </button>
                    `;
                    
                    addMessage(`System ready with ${data.current_provider}! PostgreSQL session persistence is active.`, 'assistant');
                    updatePlaceholder('ready');
                }
                
            } catch (error) {
                console.error('Health check failed:', error);
                document.getElementById('status-display').textContent = 'Connection Error';
            }
        }

        // MCP Test Function - FIXED SYNTAX
        async function testMCPTools() {
            try {
                addMessage('Testing MCP Tools integration...', 'user');
                const response = await fetch('/mcp-status');
                const data = await response.json();
                
                if (data.mcp_available) {
                    let message = 'MCP Tools Test Results:<br><br>';
                    Object.entries(data.all_tools_test).forEach(([tool, result]) => {
                        message += `${tool}: ${result.status}`;
                        if (result.count !== undefined) {
                            message += ` (${result.count} items)`;
                        }
                        message += '<br>';
                    });
                    addMessage(message, 'assistant');
                } else {
                    addMessage('MCP tools are not available.', 'assistant');
                }
            } catch (error) {
                addMessage(`Error testing MCP tools: ${error.message}`, 'assistant');
            }
        }

        async function loadSessionInfo() {
            try {
                const response = await fetch('/database-status');
                const data = await response.json();
                
                if (data.status === 'connected') {
                    document.getElementById('session-details').innerHTML = `
                        <strong>Database:</strong> Connected<br>
                        <strong>Total Conversations:</strong> ${data.total_sessions}<br>
                        <strong>Host:</strong> ${data.host}
                    `;
                } else {
                    document.getElementById('session-details').innerHTML = `
                        <strong>Database:</strong> Error<br>
                        <small>${data.message}</small>
                    `;
                }
            } catch (error) {
                document.getElementById('session-details').innerHTML = 'Database status unknown';
            }
        }

        function showProviderSelection() {
            location.reload();
        }

        async function initializeSystem() {
            if (!selectedProvider) {
                alert('Please select an AI provider first');
                return;
            }
            
            const apiKey = document.getElementById('api-key-input').value;
            
            if (!apiKey) {
                const confirmed = confirm(`Initialize with ${selectedProvider.toUpperCase()} using API key from .env file?`);
                if (!confirmed) return;
            }

            try {
                const response = await fetch('/initialize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        provider: selectedProvider, 
                        api_key: apiKey || 'from_env'
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    isInitialized = true;
                    document.getElementById('send-btn').disabled = false;
                    
                    addMessage(`System initialized with ${data.provider.toUpperCase()}! PostgreSQL session persistence is now active.`, 'assistant');
                    
                    checkSystemStatus();
                    updatePlaceholder('initialized');
                } else {
                    const error = await response.json();
                    alert(`Initialization failed: ${error.detail}`);
                }
            } catch (error) {
                alert(`Connection error: ${error.message}`);
            }
        }

        async function sendMessage() {
            if (!isInitialized) {
                alert('Please initialize the system first by choosing your AI model!');
                return;
            }

            const input = document.getElementById('message-input');
            const message = input.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            input.value = '';
            document.getElementById('send-btn').disabled = true;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message, 
                        session_id: sessionId 
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    if (data.response) {
                        addMessage(data.response, 'assistant');
                        
                        // Update session info
                        sessionId = data.session_id;
                        updateSessionDisplay(data);
                        updateTripProgress(data.trip_progress);
                        updateStepIndicator(data.current_step, data.awaiting_user_choice);
                        
                    } else {
                        addMessage('Received empty response from the system. Check server logs.', 'assistant');
                        console.log('Full response data:', data);
                    }
                } else {
                    addMessage(`System error: ${data.detail}`, 'assistant');
                }
            } catch (error) {
                addMessage(`Connection error: ${error.message}`, 'assistant');
            } finally {
                document.getElementById('send-btn').disabled = false;
            }
        }

        function updateSessionDisplay(data) {
            document.getElementById('session-details').innerHTML = `
                <strong>Current Session:</strong> ${data.session_id.substring(0, 12)}...<br>
                <strong>Step:</strong> ${data.current_step}<br>
                <strong>Awaiting Input:</strong> ${data.awaiting_user_choice ? 'Yes' : 'No'}<br>
                <strong>PostgreSQL:</strong> Auto-saved
            `;
        }

        function updateTripProgress(progress) {
            if (!progress || (!progress.origin && !progress.destination)) {
                document.getElementById('trip-progress').style.display = 'none';
                return;
            }

            document.getElementById('trip-progress').style.display = 'block';
            let tripText = '';
            
            if (progress.origin) tripText += `<strong>From:</strong> ${progress.origin}<br>`;
            if (progress.destination) tripText += `<strong>To:</strong> ${progress.destination}<br>`;
            if (progress.duration_days) tripText += `<strong>Duration:</strong> ${progress.duration_days} days<br>`;
            if (progress.budget) tripText += `<strong>Budget:</strong> ${progress.budget}<br>`;
            if (progress.has_flight) tripText += `<strong>Flight:</strong> Selected<br>`;
            if (progress.has_hotel) tripText += `<strong>Hotel:</strong> Selected<br>`;
            if (progress.trip_style) tripText += `<strong>Style:</strong> ${progress.trip_style}<br>`;
            
            document.getElementById('trip-details').innerHTML = tripText;
        }

        function updateStepIndicator(step, awaiting) {
            const indicator = document.getElementById('step-indicator');
            const stepText = document.getElementById('step-text');
            
            if (step && step !== 'initial' && step !== 'error') {
                indicator.style.display = 'block';
                stepText.textContent = step + (awaiting ? ' - Waiting for your choice...' : '');
            } else {
                indicator.style.display = 'none';
            }
        }

        async function listSessions() {
            try {
                const response = await fetch('/sessions');
                const data = await response.json();
                
                if (data.sessions && data.sessions.length > 0) {
                    // Clear chat and show clickable conversation history
                    const chatContainer = document.getElementById('chat-container');
                    chatContainer.innerHTML = `
                        <div class="message assistant-message">
                            <strong>Atlas AI Enhanced:</strong> Here's your conversation history. Click any conversation to resume exactly where you left off:
                        </div>
                    `;
                    
                    data.sessions.slice(0, 10).forEach((session, index) => {
                        const trip = session.trip_details || {};
                        const route = trip.origin && trip.destination ? `${trip.origin} to ${trip.destination}` : 'Planning in progress';
                        const lastActivity = session.last_activity ? new Date(session.last_activity).toLocaleString() : 'Unknown';
                        const isComplete = session.current_step === 'complete';
                        const statusIcon = isComplete ? 'Complete' : 'In Progress';
                        const duration = trip.duration_days ? `${trip.duration_days} days` : '';
                        
                        const historyItem = document.createElement('div');
                        historyItem.className = 'chat-history-item';
                        historyItem.onclick = () => resumeSession(session.session_id);
                        historyItem.innerHTML = `
                            <strong>${statusIcon} ${route}</strong> ${duration}<br>
                            <small>Step: ${session.current_step} | ${lastActivity}</small><br>
                            <small style="color: #666;">Click to resume • ${session.session_id.substring(0, 12)}...</small>
                        `;
                        
                        chatContainer.appendChild(historyItem);
                    });
                    
                    // Add option to start new conversation
                    const newConversationDiv = document.createElement('div');
                    newConversationDiv.innerHTML = `
                        <div class="message assistant-message" style="margin-top: 20px;">
                            <button onclick="startNewConversation()" style="background: #28a745; padding: 15px 20px;">
                                Start New Conversation
                            </button>
                        </div>
                    `;
                    chatContainer.appendChild(newConversationDiv);
                    
                    // Update session count in sidebar
                    loadSessionInfo();
                } else {
                    addMessage('No saved conversations found. Start a new trip planning conversation!', 'assistant');
                }
            } catch (error) {
                addMessage('Error fetching conversation history.', 'assistant');
                console.error('Session fetch error:', error);
            }
        }

        async function resumeSession(sessionIdToResume) {
            try {
                console.log(`Resuming session: ${sessionIdToResume}`);
                
                // Set the session ID to resume
                sessionId = sessionIdToResume;
                
                // Get session details
                const response = await fetch(`/sessions/${sessionIdToResume}`);
                const sessionData = await response.json();
                
                if (sessionData) {
                    // Clear current chat
                    document.getElementById('chat-container').innerHTML = '';
                    
                    // Show session resume header
                    addMessage(`Resuming conversation from ${new Date().toLocaleString()}`, 'assistant');
                    
                    // Load and display conversation history
                    await loadConversationHistory(sessionIdToResume);
                    
                    // Update all displays
                    updateTripProgress(sessionData.trip_details);
                    updateStepIndicator(sessionData.current_step, sessionData.awaiting_user_choice);
                    updateSessionDisplay({
                        session_id: sessionIdToResume,
                        current_step: sessionData.current_step,
                        awaiting_user_choice: sessionData.awaiting_user_choice
                    });
                    
                    // Show contextual resume message based on current step
                    const trip = sessionData.trip_details || {};
                    let resumeMessage = '';
                    
                    if (sessionData.current_step === 'awaiting_flight_choice') {
                        resumeMessage = `You were choosing a flight for your ${trip.origin} to ${trip.destination} trip. Please select your preferred flight option.`;
                    } else if (sessionData.current_step === 'awaiting_hotel_choice') {
                        resumeMessage = `You were choosing accommodation for ${trip.destination}. Please select your preferred hotel.`;
                    } else if (sessionData.current_step === 'awaiting_style_decision') {
                        resumeMessage = `You were choosing your travel style for ${trip.destination}. Please select your preference.`;
                    } else if (sessionData.current_step === 'awaiting_missing_info') {
                        resumeMessage = `I was waiting for additional trip details. Please provide the missing information to continue.`;
                    } else if (sessionData.current_step === 'complete') {
                        resumeMessage = `Your ${trip.origin} to ${trip.destination} trip planning is complete! You can ask me to modify the itinerary or start a new trip.`;
                    } else if (sessionData.awaiting_user_choice) {
                        resumeMessage = `Please continue from where you left off with your ${trip.origin} to ${trip.destination} trip.`;
                    } else {
                        resumeMessage = `Conversation resumed! You can continue planning or ask me questions about your trip.`;
                    }
                    
                    addMessage(resumeMessage, 'assistant');
                    
                } else {
                    addMessage('Could not load conversation details.', 'assistant');
                }
                
            } catch (error) {
                addMessage(`Error resuming conversation: ${error.message}`, 'assistant');
                console.error('Resume session error:', error);
            }
        }

        async function loadConversationHistory(sessionId) {
            try {
                // Get the full conversation state from PostgreSQL
                const response = await fetch(`/conversation-history/${sessionId}`);
                const data = await response.json();
                
                if (data.conversation_history && data.conversation_history.length > 0) {
                    // Display each message in the conversation
                    data.conversation_history.forEach(msg => {
                        if (msg.role === 'user') {
                            addMessage(msg.content, 'user');
                        } else if (msg.role === 'assistant') {
                            addMessage(msg.content, 'assistant');
                        }
                    });
                    
                    // Add separator
                    addMessage('--- Conversation resumed ---', 'assistant');
                } else {
                    console.log('No conversation history found in session data');
                }
                
            } catch (error) {
                console.log('Could not load conversation history:', error);
                // Continue without history if loading fails
            }
        }

        function startNewConversation() {
            // Reset session ID to start fresh
            sessionId = null;
            
            // Clear chat
            document.getElementById('chat-container').innerHTML = `
                <div class="message assistant-message">
                    <strong>Atlas AI Enhanced:</strong> Starting a new conversation! Tell me about your travel plans.
                </div>
            `;
            
            // Reset displays
            document.getElementById('trip-progress').style.display = 'none';
            document.getElementById('step-indicator').style.display = 'none';
            document.getElementById('session-details').innerHTML = `
                <strong>Status:</strong> New conversation<br>
                <strong>PostgreSQL:</strong> Ready to save
            `;
        }

        async function checkDatabaseStatus() {
            try {
                const response = await fetch('/database-status');
                const data = await response.json();
                
                if (data.status === 'connected') {
                    let statusMessage = `PostgreSQL Database Status:<br><br>`;
                    statusMessage += `<strong>Status:</strong> Connected<br>`;
                    statusMessage += `<strong>Host:</strong> ${data.host}<br>`;
                    statusMessage += `<strong>Database:</strong> ${data.database_name}<br>`;
                    statusMessage += `<strong>Total Sessions:</strong> ${data.total_sessions}<br>`;
                    statusMessage += `<strong>Table Structure:</strong> ${data.table_structure?.length || 0} columns<br><br>`;
                    
                    if (data.recent_sessions && data.recent_sessions.length > 0) {
                        statusMessage += `<strong>Recent Activity:</strong><br>`;
                        data.recent_sessions.forEach(session => {
                            statusMessage += `${session.session_id} - ${session.route} (${session.step})<br>`;
                        });
                    }
                    
                    addMessage(statusMessage, 'assistant');
                } else {
                    addMessage(`Database connection failed: ${data.message}`, 'assistant');
                }
            } catch (error) {
                addMessage('Error checking database status.', 'assistant');
            }
        }

        async function clearAllSessions() {
            if (confirm('Clear all conversation history from PostgreSQL? This cannot be undone.')) {
                try {
                    const response = await fetch('/clear-sessions', { method: 'POST' });
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        addMessage(`${data.message}`, 'assistant');
                        loadSessionInfo(); // Refresh session display
                        startNewConversation(); // Start fresh
                    } else {
                        addMessage(`Error: ${data.message}`, 'assistant');
                    }
                } catch (error) {
                    addMessage('Error clearing conversation history.', 'assistant');
                }
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
            const senderName = sender === 'user' ? 'You' : 'Atlas AI Enhanced';
            messageDiv.innerHTML = `<strong>${senderName}:</strong> ${text}`;
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }

        function updatePlaceholder(status) {
            const input = document.getElementById('message-input');
            if (status === 'ready' || status === 'initialized') {
                input.placeholder = 'Tell me about your travel plans... (PostgreSQL sessions active)';
            }
        }
    </script>
</body>
</html>
    """

@app.post("/initialize")
async def initialize_system(request: InitializeRequest):
    global travel_assistant
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        raise HTTPException(status_code=500, detail="EnhancedTravelAssistant not available")
    
    try:
        available_providers = detect_available_providers()
        provider_values = [p.lower() for p in available_providers.values()]
        
        if request.provider.lower() not in provider_values:
            raise HTTPException(status_code=400, detail="Provider not available")
        
        # Handle 'from_env' API key
        api_key = request.api_key
        if api_key == 'from_env':
            if request.provider.lower() == 'openai':
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=400, detail="OPENAI_API_KEY not found in environment")
            else:  # gemini
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=400, detail="GEMINI_API_KEY not found in environment")
        
        # Initialize Enhanced Travel Assistant
        travel_assistant = EnhancedTravelAssistant(request.provider, api_key)
        
        return {
            "status": "success", 
            "provider": request.provider,
            "postgresql": "active",
            "session_management": "enhanced"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not travel_assistant:
        raise HTTPException(status_code=503, detail="System not initialized. Choose your AI model first.")
    
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        print(f"Processing with PostgreSQL persistence: {session_id[:8]}...")
        
        # Use enhanced chat_with_persistence
        result = travel_assistant.chat_with_persistence(
            user_input=request.message,
            session_id=session_id
        )
        
        print(f"Result keys: {list(result.keys())}")
        print(f"Response length: {len(result.get('response', ''))}")
        
        # Get session info for trip progress
        session_info = travel_assistant.get_session_info(session_id)
        trip_progress = session_info.get('trip_details') if session_info else None
        
        response_text = result.get("response", "")
        if not response_text:
            print("Empty response from system")
            response_text = "I'm processing your request. Please try rephrasing if needed."
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            current_step=result.get("current_step", "processing"),
            awaiting_user_choice=result.get("awaiting_user_choice", False),
            trip_progress=trip_progress
        )
        
    except Exception as e:
        print(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"System error: {str(e)}")

@app.get("/health")
async def health_check():
    # Simplified health check - no provider detection calls
    postgresql_status = "unknown"
    if travel_assistant and hasattr(travel_assistant, 'session_manager'):
        postgresql_status = "connected" if travel_assistant.session_manager else "failed"
    
    return {
        "status": "healthy",
        "travel_assistant_loaded": travel_assistant is not None,
        "current_provider": getattr(travel_assistant, 'provider', None) if travel_assistant else None,
        "postgresql_status": postgresql_status,
        "apis_configured": {
            "openai": "configured" if os.getenv("OPENAI_API_KEY") else "not_configured",
            "gemini": "configured" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "not_configured"
        }
    }

@app.get("/conversation-history/{session_id}")
async def get_conversation_history(session_id: str):
    """Get the full conversation history using existing conversation_state column"""
    if not travel_assistant or not travel_assistant.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        # Load the session state that's already stored in conversation_state column
        session_state = travel_assistant.session_manager.load_session(session_id)
        
        if not session_state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Extract conversation history from the existing data
        conversation_history = session_state.get("conversation_history", [])
        
        # If no formal conversation history, reconstruct from available state
        if not conversation_history:
            messages = []
            
            # Add user input if available
            if session_state.get("user_input"):
                messages.append({
                    "role": "user", 
                    "content": session_state["user_input"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Add bot responses based on current state
            if session_state.get("flight_options"):
                flight_response = "Here are your flight options:\n"
                for i, flight in enumerate(session_state["flight_options"][:3], 1):
                    flight_response += f"Option {i}: {flight.get('airline', 'Unknown')}\n"
                messages.append({
                    "role": "assistant", 
                    "content": flight_response,
                    "timestamp": datetime.now().isoformat()
                })
            
            if session_state.get("hotel_options"):
                hotel_response = "Here are your hotel options:\n"
                for i, hotel in enumerate(session_state["hotel_options"][:3], 1):
                    hotel_response += f"Option {i}: {hotel.get('name', 'Unknown')}\n"
                messages.append({
                    "role": "assistant", 
                    "content": hotel_response,
                    "timestamp": datetime.now().isoformat()
                })
            
            conversation_history = messages
        
        return {
            "session_id": session_id,
            "conversation_history": conversation_history,
            "current_step": session_state.get("current_step", "unknown"),
            "trip_details": {
                "origin": session_state.get("origin", ""),
                "destination": session_state.get("destination", ""),
                "duration_days": session_state.get("duration_days", 0),
                "budget": session_state.get("budget", ""),
                "selected_flight": session_state.get("selected_flight", {}),
                "selected_hotel": session_state.get("selected_hotel", {})
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load conversation history: {str(e)}")

@app.get("/sessions")
async def list_sessions():
    if not travel_assistant:
        return {"sessions": []}
    
    try:
        sessions = travel_assistant.list_sessions(limit=20)
        return {"sessions": sessions}
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return {"sessions": [], "error": str(e)}

@app.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    if not travel_assistant:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        session_info = travel_assistant.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database-status")
async def database_status():
    """Check PostgreSQL database status and show recent sessions"""
    if not travel_assistant or not travel_assistant.session_manager:
        return {"status": "error", "message": "Session manager not available"}
    
    try:
        # Test database connection
        conn = psycopg2.connect(**travel_assistant.session_manager.connection_config)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'enhanced_travel_sessions'
            ORDER BY ordinal_position
        """)
        table_structure = cursor.fetchall()
        
        # Get session count
        cursor.execute("SELECT COUNT(*) FROM enhanced_travel_sessions")
        total_sessions = cursor.fetchone()[0]
        
        # Get recent sessions
        cursor.execute("""
            SELECT session_id, current_step, origin, destination, updated_at
            FROM enhanced_travel_sessions 
            ORDER BY updated_at DESC 
            LIMIT 5
        """)
        recent_sessions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "status": "connected",
            "database": "PostgreSQL Cloud SQL",
            "host": "35.224.149.145",
            "database_name": "travel_sessions",
            "total_sessions": total_sessions,
            "table_structure": [{"column": col[1], "type": col[2]} for col in table_structure],
            "recent_sessions": [
                {
                    "session_id": row[0][:12] + "...",
                    "step": row[1],
                    "route": f"{row[2] or 'Unknown'} → {row[3] or 'Unknown'}" if row[2] or row[3] else "No route",
                    "last_activity": row[4].isoformat() if row[4] else None
                }
                for row in recent_sessions
            ]
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/clear-sessions")
async def clear_all_sessions():
    """Clear all sessions from PostgreSQL"""
    if not travel_assistant or not travel_assistant.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        conn = psycopg2.connect(**travel_assistant.session_manager.connection_config)
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM enhanced_travel_sessions")
        count_before = cursor.fetchone()[0]
        
        # Clear all sessions
        cursor.execute("DELETE FROM enhanced_travel_sessions")
        
        # Get count after deletion
        cursor.execute("SELECT COUNT(*) FROM enhanced_travel_sessions")
        count_after = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Cleared {count_before} conversations from PostgreSQL",
            "sessions_before": count_before,
            "sessions_after": count_after
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config():
    available_providers = detect_available_providers() if TRAVEL_ASSISTANT_AVAILABLE else {}
    return {
        "available_ai_providers": available_providers,
        "current_provider": getattr(travel_assistant, 'provider', None) if travel_assistant else None,
        "session_features": [
            "PostgreSQL persistence",
            "Enhanced session management", 
            "Conversation state tracking",
            "Resume across browser sessions",
            "Clickable chat history"
        ]
    }

# NEW MCP ENDPOINT - ONLY ADDITION TO YOUR ORIGINAL
@app.get("/mcp-status")
async def mcp_status():
    """Test all MCP tools and show their status"""
    if not MCP_TOOLS_AVAILABLE:
        return {"mcp_available": False, "error": "MCP tools not imported"}
    
    results = {}
    
    # Test attractions (should work - free API)
    try:
        attractions_result = search_attractions("Rome", ["cultural"])
        results["attractions"] = {
            "status": "success" if attractions_result.get("status") == "success" else "error",
            "count": attractions_result.get("count", 0)
        }
    except Exception as e:
        results["attractions"] = {"status": "error", "message": str(e)}
    
    # Test sessions (should work - your PostgreSQL)
    try:
        sessions_result = manage_session("list")
        results["sessions"] = {
            "status": "success" if sessions_result.get("status") == "listed" else "error",
            "count": len(sessions_result.get("sessions", []))
        }
    except Exception as e:
        results["sessions"] = {"status": "error", "message": str(e)}
    
    # Test flights (may fail if no API key)
    try:
        flights_result = search_flights("Boston", "Rome")
        results["flights"] = {
            "status": "success" if flights_result.get("status") == "success" else "error",
            "count": flights_result.get("count", 0)
        }
    except Exception as e:
        results["flights"] = {"status": "error", "message": str(e)}
    
    # Test hotels (may fail if no API key)
    try:
        hotels_result = search_hotels("Rome", "2024-06-01", "2024-06-08")
        results["hotels"] = {
            "status": "success" if hotels_result.get("status") == "success" else "error",
            "count": hotels_result.get("count", 0)
        }
    except Exception as e:
        results["hotels"] = {"status": "error", "message": str(e)}
    
    return {
        "mcp_available": True,
        "all_tools_test": results
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting Complete Atlas AI with Clickable Chat History")
    print("Features: LangGraph workflow, real APIs, PostgreSQL persistence, resume conversations")
    uvicorn.run("fastapi_postgresql:app", host="0.0.0.0", port=8000, reload=True)