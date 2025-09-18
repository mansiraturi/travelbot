# Atlas AI Travel Assistant

A sophisticated multi-agent travel planning system built with LangGraph, featuring real-time API integration and intelligent conversational workflows.

## 🎥 Demo Video

[![Atlas AI Demo]](assets/Demo.mp4)

*Click to watch the complete demonstration of Atlas AI's multi-agent workflow and real API integrations*

## Overview

Atlas AI transforms travel planning from a fragmented multi-website experience into a single, intelligent conversation. Using LangGraph's multi-agent architecture, the system orchestrates real-time API calls to provide live flight schedules, hotel pricing, and attraction data while maintaining sophisticated state management throughout the planning process.

## Key Features

- **Multi-Agent Architecture**: 8 specialized agents handle different aspects of travel planning
- **Real API Integration**: Live data from AviationStack, Booking.com, and Google Places
- **Intelligent Validation**: Progressive information collection with natural language processing
- **Adaptive Workflows**: Users can customize their experience or skip to quick results
- **Memory Persistence**: Full conversation context maintained across all interactions
- **Error Recovery**: Comprehensive fallback systems for API failures

## Multi-Agent Workflow

### Agent Architecture

The system employs 8 specialized agents working in coordination:

1. **Information Extraction Agent** - Parses natural language input and extracts travel requirements
2. **Missing Information Handler** - Collects incomplete data through targeted questioning
3. **Flight Search Agent** - Integrates with AviationStack for real flight schedules
4. **Hotel Search Agent** - Retrieves live hotel pricing from Booking.com via RapidAPI
5. **Attractions Discovery Agent** - Finds real points of interest using Google Places
6. **Style Decision Agent** - Routes users between customization and quick completion
7. **Style Selection Agent** - Handles travel style preferences (Cultural, Adventure, etc.)
8. **Itinerary Creation Agent** - Synthesizes all data into comprehensive travel plans

### LangGraph State Machine

START → extract_info → [validation] → search_flights → [user choice]
↓
search_hotels → [user choice] → search_attractions → style_decision
↓
[customize] → choose_style → create_itinerary → END
[skip] → create_itinerary → END


## Technical Architecture

### Real-Time API Integration

**AviationStack API**
- Live flight schedules and airline information
- Airport code conversion and route validation
- Comprehensive error handling for authentication and quotas

**Booking.com via RapidAPI**
- Two-step process: location search → hotel search
- Dynamic date management to prevent API rejections
- Live pricing and availability data

**Google Places API**
- Interest-based attraction discovery
- Duplicate removal and result ranking
- Real ratings and location data

### LLM Provider Support

- **OpenAI GPT-3.5**: Premium response quality
- **Google Gemini**: Cost-effective operation
- Unified interface with runtime provider switching

### Advanced Features

- **Progressive Information Collection**: Asks for missing data one piece at a time
- **AI-Powered Choice Processing**: Natural language interpretation of user selections
- **Conditional Workflow Routing**: Adapts flow based on user preferences
- **Memory Buffer Integration**: Maintains conversation context using LangChain

## Installation & Setup

### Prerequisites
```bash
pip install langgraph langchain streamlit requests python-dotenv
pip install langchain-openai google-generativeai  # For LLM providers
```

### API Keys Required
# AI Provider (choose one)
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key

# Travel APIs
FLIGHT_API_KEY=your_aviationstack_key
RAPIDAPI_KEY=your_rapidapi_key  
GOOGLE_PLACES_API_KEY=your_google_places_key

### Running the Application
```bash
streamlit run travel_app.py
```
## Project Structure
```bash
atlas-ai/
├── travel_assistant.py    # Core multi-agent system
├── travel_app.py          # Streamlit web interface  
├── test_flight_api.py     # API testing utilities
├── assets/
│   ├── demo_video.mp4     # System demonstration
│   └── demo_thumbnail.png # Video thumbnail
├── .env                   # API keys (create this)
└── README.md
```