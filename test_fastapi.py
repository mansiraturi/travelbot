from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import os
import uuid
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import your existing travel assistant
try:
    from travel_assistant import RealAPITravelAssistant, detect_available_providers
    TRAVEL_ASSISTANT_AVAILABLE = True
    logger.info("✅ Successfully imported travel_assistant")
except ImportError as e:
    logger.error(f"❌ Could not import travel_assistant: {e}")
    TRAVEL_ASSISTANT_AVAILABLE = False

# FastAPI app
app = FastAPI(
    title="Atlas AI Travel Assistant API",
    description="Production travel planning with real API integrations",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global travel assistant instance
travel_assistant: Optional[RealAPITravelAssistant] = None

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    current_step: str
    awaiting_user_choice: bool
    api_calls_made: Optional[List[str]] = []

class InitializeRequest(BaseModel):
    provider: str  # "openai" or "gemini"
    api_key: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    travel_assistant_loaded: bool
    apis_configured: Dict[str, str]

# Startup event
@app.on_event("startup")
async def startup_event():
    """Try to auto-initialize if API keys are available"""
    global travel_assistant
    
    logger.info("🚀 Starting Atlas AI Travel Assistant API")
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        logger.warning("⚠️ Travel assistant not available - manual initialization required")
        return
    
    try:
        # Check for available providers and API keys
        available_providers = detect_available_providers()
        if not available_providers:
            logger.warning("⚠️ No AI providers available")
            return
        
        # Try to auto-initialize with environment variables
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if openai_key and "OpenAI" in available_providers:
            travel_assistant = RealAPITravelAssistant("openai", openai_key)
            logger.info("✅ Auto-initialized with OpenAI")
        elif gemini_key and "Gemini" in available_providers:
            travel_assistant = RealAPITravelAssistant("gemini", gemini_key)
            logger.info("✅ Auto-initialized with Gemini")
        else:
            logger.info("ℹ️ No API keys found - manual initialization required")
            
    except Exception as e:
        logger.error(f"❌ Auto-initialization failed: {e}")

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Atlas AI Travel Assistant API",
        "version": "1.0.0",
        "status": "running",
        "travel_assistant_loaded": travel_assistant is not None,
        "features": [
            "Real flight data (AviationStack)",
            "Real hotel data (Booking.com)", 
            "FREE attractions (OpenStreetMap)",
            "PostgreSQL session persistence",
            "LangGraph conversation flow"
        ],
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "POST /initialize": "Initialize AI provider",
            "POST /chat": "Main conversation",
            "GET /sessions": "List sessions",
            "GET /config": "Configuration info",
            "GET /docs": "API documentation"
        }
    }

# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    # Check API configurations
    apis_configured = {
        "openai": "configured" if os.getenv("OPENAI_API_KEY") else "not_configured",
        "gemini": "configured" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "not_configured",
        "flight_api": "configured" if os.getenv("FLIGHT_API_KEY") else "not_configured",
        "hotel_api": "configured" if os.getenv("RAPIDAPI_KEY") else "not_configured",
        "places_api": "free_openstreetmap_available",
        "postgresql": "configured" if travel_assistant else "depends_on_travel_assistant"
    }
    
    return HealthResponse(
        status="healthy" if TRAVEL_ASSISTANT_AVAILABLE else "limited_functionality",
        timestamp=datetime.now().isoformat(),
        travel_assistant_loaded=travel_assistant is not None,
        apis_configured=apis_configured
    )

# Initialize system
@app.post("/initialize")
async def initialize_system(request: InitializeRequest):
    global travel_assistant
    
    if not TRAVEL_ASSISTANT_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Travel assistant module not available. Check travel_assistant.py import."
        )
    
    try:
        # Validate provider
        available_providers = detect_available_providers()
        provider_values = [p.lower() for p in available_providers.values()]
        
        if request.provider.lower() not in provider_values:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{request.provider}' not available. Available: {list(available_providers.keys())}"
            )
        
        # Initialize travel assistant
        travel_assistant = RealAPITravelAssistant(request.provider, request.api_key)
        
        logger.info(f"✅ System initialized with {request.provider}")
        
        return {
            "status": "success",
            "message": f"Atlas AI initialized with {request.provider.title()}",
            "provider": request.provider,
            "real_apis_available": [
                "AviationStack (flights)" if os.getenv("FLIGHT_API_KEY") else "AviationStack (not configured)",
                "Booking.com (hotels)" if os.getenv("RAPIDAPI_KEY") else "Booking.com (not configured)",
                "OpenStreetMap (attractions - FREE)"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not travel_assistant:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Call /initialize first with your AI provider API key."
        )
    
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"💬 Processing message for session {session_id[:8]}...")
        
        # Process with travel assistant using PostgreSQL persistence
        result = travel_assistant.chat_with_persistence(
            user_input=request.message,
            session_id=session_id
        )
        
        # Determine which APIs were called
        api_calls_made = []
        current_step = result.get("current_step", "")
        
        if "flight" in current_step and result.get("flight_options"):
            api_calls_made.append("AviationStack (flights)")
        if "hotel" in current_step and result.get("hotel_options"):
            api_calls_made.append("Booking.com (hotels)")
        if "attraction" in current_step and result.get("attractions_data"):
            api_calls_made.append("OpenStreetMap (attractions - FREE)")
        
        return ChatResponse(
            response=result.get("response", "Processing your request with real APIs..."),
            session_id=session_id,
            current_step=result.get("current_step", "initial"),
            awaiting_user_choice=result.get("awaiting_user_choice", False),
            api_calls_made=api_calls_made
        )
        
    except Exception as e:
        logger.error(f"❌ Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

# List sessions endpoint
@app.get("/sessions")
async def list_sessions(limit: int = 20):
    if not travel_assistant:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        sessions = travel_assistant.list_sessions(limit=limit)
        return {
            "sessions": sessions,
            "total": len(sessions),
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

# Configuration endpoint
@app.get("/config")
async def get_configuration():
    if TRAVEL_ASSISTANT_AVAILABLE:
        available_providers = detect_available_providers()
    else:
        available_providers = {}
    
    return {
        "travel_assistant_available": TRAVEL_ASSISTANT_AVAILABLE,
        "available_ai_providers": available_providers,
        "current_provider": getattr(travel_assistant, 'provider', None) if travel_assistant else None,
        "api_requirements": {
            "required": {
                "ai_provider": "OPENAI_API_KEY or GEMINI_API_KEY"
            },
            "optional_but_recommended": {
                "flights": "FLIGHT_API_KEY (AviationStack)",
                "hotels": "RAPIDAPI_KEY (Booking.com)"
            },
            "always_available": {
                "attractions": "OpenStreetMap (FREE)"
            }
        },
        "database": {
            "type": "PostgreSQL",
            "location": "Cloud SQL",
            "features": ["Session persistence", "Conversation checkpointing"]
        }
    }

# Test endpoint for debugging
@app.get("/test-integration")
async def test_integration():
    """Test integration with travel_assistant.py"""
    
    results = {
        "travel_assistant_import": TRAVEL_ASSISTANT_AVAILABLE,
        "travel_assistant_initialized": travel_assistant is not None,
        "timestamp": datetime.now().isoformat()
    }
    
    if TRAVEL_ASSISTANT_AVAILABLE:
        try:
            available_providers = detect_available_providers()
            results["available_providers"] = available_providers
            results["provider_detection"] = "working"
        except Exception as e:
            results["provider_detection"] = f"failed: {str(e)}"
    
    if travel_assistant:
        try:
            # Test a simple method
            results["travel_assistant_methods"] = {
                "get_airport_code": hasattr(travel_assistant, 'get_airport_code'),
                "chat_with_persistence": hasattr(travel_assistant, 'chat_with_persistence'),
                "list_sessions": hasattr(travel_assistant, 'list_sessions')
            }
            results["travel_assistant_status"] = "functional"
        except Exception as e:
            results["travel_assistant_status"] = f"error: {str(e)}"
    
    return results

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("🚀 ATLAS AI TRAVEL ASSISTANT - INTEGRATED VERSION")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Travel Assistant Available: {TRAVEL_ASSISTANT_AVAILABLE}")
    print("")
    print("Features:")
    print("  ✈️  Real flight data (AviationStack API)")
    print("  🏨  Real hotel data (Booking.com API)")
    print("  🎯  Real attractions (OpenStreetMap - FREE)")
    print("  💾  PostgreSQL session persistence")
    print("  🤖  LangGraph conversation flow")
    print("")
    print("Test URLs:")
    print(f"  http://localhost:{port}/health")
    print(f"  http://localhost:{port}/test-integration")
    print(f"  http://localhost:{port}/config")
    print(f"  http://localhost:{port}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "test_fastapi:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )