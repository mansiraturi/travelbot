import streamlit as st
import os
from datetime import datetime
import sys

# Add current directory to path so imports work
sys.path.append(os.path.dirname(__file__))

try:
    from travel_assistant import RealAPITravelAssistant, detect_available_providers
except ImportError:
    st.error("❌ Cannot import from travel_assistant.py. Make sure 'travel_assistant.py' is in the same directory.")
    st.stop()

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Atlas AI Travel Assistant - Multi Agent Architecture",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
.chat-message {
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
}
.user-message {
    background-color: #e3f2fd;
    margin-left: 20%;
}
.assistant-message {
    background-color: #f5f5f5;
    margin-right: 20%;
}
.atlas-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    margin-bottom: 1rem;
}
.step-indicator {
    background-color: #e8f5e8;
    padding: 0.5rem;
    border-radius: 5px;
    border-left: 4px solid #4caf50;
    margin: 1rem 0;
}
.api-status {
    padding: 0.5rem;
    border-radius: 5px;
    margin: 0.2rem 0;
}
.api-connected {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
}
.api-missing {
    background-color: #f8d7da;
    border-left: 4px solid #dc3545;
}
.provider-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "atlas_ai" not in st.session_state:
    st.session_state.atlas_ai = None
if "chat_state" not in st.session_state:
    st.session_state.chat_state = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = None

def initialize_atlas_ai(provider: str, api_key: str):
    """Initialize Atlas AI with real APIs"""
    if not provider or not api_key:
        return False
    
    try:
        st.session_state.atlas_ai = RealAPITravelAssistant(provider, api_key)
        st.session_state.chat_state = None
        st.session_state.selected_provider = provider
        return True
    except Exception as e:
        st.error(f"Error initializing Atlas AI: {str(e)}")
        return False

def check_api_status():
    """Check status of all required APIs"""
    apis = {
        "AI Provider (OpenAI)": os.getenv("OPENAI_API_KEY"),
        "AI Provider (Gemini)": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "Flight API (AviationStack)": os.getenv("FLIGHT_API_KEY"),
        "Hotel API (RapidAPI)": os.getenv("RAPIDAPI_KEY"),
        "Attractions (Google Places)": os.getenv("GOOGLE_PLACES_API_KEY"),
        "Weather API (Optional)": os.getenv("OPENWEATHERMAP_API_KEY")
    }
    
    return apis

def display_step_indicator():
    """Display current planning step"""
    if st.session_state.chat_state:
        current_step = st.session_state.chat_state.get("current_step", "initial")
        awaiting_choice = st.session_state.chat_state.get("awaiting_user_choice", False)
        
        step_mapping = {
            "initial": "🔍 Initial Planning",
            "awaiting_missing_info": "📝 Collecting Trip Details", 
            "info_complete": "✅ Information Complete",
            "flights": "✈️ Searching Real Flights",
            "awaiting_flight_choice": "✈️ Choose Flight",
            "hotels": "🏨 Searching Real Hotels",
            "awaiting_hotel_choice": "🏨 Choose Hotel",
            "attractions": "🎯 Finding Real Attractions",
            "trip_style": "🎯 Choose Trip Style",
            "awaiting_style_choice": "🎯 Choose Trip Style",
            "itinerary": "📅 Creating Dynamic Itinerary",
            "complete": "✅ Plan Complete"
        }
        
        step_description = step_mapping.get(current_step, current_step)
        
        if awaiting_choice:
            st.markdown(f"""
            <div class="step-indicator">
                <strong>Current Step:</strong> {step_description} - <em>Waiting for your selection...</em>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="step-indicator">
                <strong>Current Step:</strong> {step_description}
            </div>
            """, unsafe_allow_html=True)

def main():
    # Header
    st.markdown("""
    <div class="atlas-header">
        <h1>🤖 Atlas AI Travel Assistant</h1>
        <p>Your Personal Travel Planner</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("🤖 AI Provider Setup")
        
        # Provider detection and selection
        available_providers = detect_available_providers()
        
        if not available_providers:
            st.error("❌ No AI providers available!")
            st.markdown("""
            **Install required packages:**
            ```bash
            pip install langchain-openai google-generativeai
            ```
            """)
            return
        
        # Provider selection
        provider_options = list(available_providers.keys())
        selected_provider_name = st.selectbox(
            "Choose AI Provider:",
            options=provider_options,
            index=0
        )
        
        selected_provider = available_providers[selected_provider_name]
        
        # API key input based on provider
        if selected_provider == "openai":
            st.info("🔷 **OpenAI GPT-3.5**\n- High quality responses\n- Costs ~$0.01-0.05 per plan")
            ai_api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                value=os.getenv("OPENAI_API_KEY", ""),
                help="Get from https://platform.openai.com/api-keys"
            )
        else:  # gemini
            st.success("🟢 **Google Gemini**\n- FREE to use!\n- High quality responses")
            ai_api_key = st.text_input(
                "Gemini API Key",
                type="password",
                value=os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
                help="Get from https://makersuite.google.com/app/apikey"
            )
        
        # Initialize button
        if st.button("🚀 Initialize Atlas AI", type="primary"):
            if initialize_atlas_ai(selected_provider, ai_api_key):
                st.success(f"✅ Atlas AI ready with {selected_provider_name}!")
                st.rerun()
            else:
                st.error("❌ Initialization failed. Check API key.")
        
        st.markdown("---")
        
        # API Status Check
        st.header("API Configuration ")
        
        api_status = check_api_status()
        
        for api_name, api_key in api_status.items():
            if api_key:
                st.markdown(f"""
                <div class="api-status api-connected">
                    ✅ <strong>{api_name}:</strong> Connected
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="api-status api-missing">
                    ❌ <strong>{api_name}:</strong> Missing
                </div>
                """, unsafe_allow_html=True)
        
        # API Key Input Section
        st.header("🔧 Configure Real APIs")
        
        flight_key = st.text_input(
            "AviationStack API Key",
            type="password",
            value=os.getenv("FLIGHT_API_KEY", ""),
            help="Get from https://aviationstack.com/product - Free tier available"
        )
        
        rapidapi_key = st.text_input(
            "RapidAPI Key",
            type="password",
            value=os.getenv("RAPIDAPI_KEY", ""),
            help="Get from https://rapidapi.com - Used for Booking.com hotel API"
        )
        
        google_places_key = st.text_input(
            "Google Places API Key",
            type="password",
            value=os.getenv("GOOGLE_PLACES_API_KEY", ""),
            help="Get from Google Cloud Console - Places API"
        )
        
        weather_key = st.text_input(
            "OpenWeatherMap API Key (Optional)",
            type="password",
            value=os.getenv("OPENWEATHERMAP_API_KEY", ""),
            help="Get from https://openweathermap.org/api - For weather data"
        )
        
        # Set environment variables dynamically
        if flight_key:
            os.environ["FLIGHT_API_KEY"] = flight_key
        if rapidapi_key:
            os.environ["RAPIDAPI_KEY"] = rapidapi_key
        if google_places_key:
            os.environ["GOOGLE_PLACES_API_KEY"] = google_places_key
        if weather_key:
            os.environ["OPENWEATHERMAP_API_KEY"] = weather_key
        
        st.markdown("---")
        
        # Planning progress
        if st.session_state.chat_state:
            st.header("📊 Planning Progress")
            
            steps = ["Initial", "Info Collection", "Flights", "Hotels", "Attractions", "Style", "Itinerary", "Complete"]
            current = st.session_state.chat_state.get("current_step", "initial")
            
            progress_map = {
                "initial": 1, "awaiting_missing_info": 1, "info_complete": 2, 
                "flights": 3, "awaiting_flight_choice": 3,
                "hotels": 4, "awaiting_hotel_choice": 4, "attractions": 5,
                "trip_style": 6, "awaiting_style_choice": 6,
                "itinerary": 7, "complete": 8
            }
            
            current_progress = progress_map.get(current, 1)
            progress = min(current_progress / 8, 1.0)
            
            st.progress(progress)
            st.write(f"Step {current_progress}/8: {steps[min(current_progress-1, 7)]}")
        
        # Trip details
        if st.session_state.chat_state:
            st.header("🧳 Trip Details")
            trip_state = st.session_state.chat_state
            
            if trip_state.get("origin"):
                st.write(f"**From:** {trip_state['origin']}")
            if trip_state.get("destination"):
                st.write(f"**To:** {trip_state['destination']}")
            if trip_state.get("duration_days"):
                st.write(f"**Duration:** {trip_state['duration_days']} days")
            if trip_state.get("selected_flight") and trip_state["selected_flight"].get("airline"):
                flight = trip_state["selected_flight"]
                st.write(f"**Flight:** {flight['airline']} - {flight.get('note', 'Contact airline')}")
            if trip_state.get("selected_hotel") and trip_state["selected_hotel"].get("name"):
                hotel = trip_state["selected_hotel"]
                st.write(f"**Hotel:** {hotel['name']} - ${hotel.get('price_per_night', 'N/A')}/night")
            if trip_state.get("selected_trip_style"):
                st.write(f"**Style:** {trip_state['selected_trip_style'].title()}")
            if trip_state.get("attractions_data"):
                st.write(f"**Attractions Found:** {len(trip_state['attractions_data'])}")
        
        # Reset button
        if st.button("🗑️ Reset Planning"):
            st.session_state.messages = []
            st.session_state.chat_state = None
            st.rerun()
    
    # Main interface
    if not st.session_state.atlas_ai:
        # Setup instructions
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("**🎯 Real API Features:**")
            st.markdown("""
            • **Real Flight Data** - AviationStack API integration
            • **Real Hotel Data** - Booking.com via RapidAPI  
            • **Real Attractions** - Google Places API
            • **Dynamic Itineraries** - AI-generated from real selections
            • **No Mock Data** - Everything is live API calls
            • **Step-by-Step Planning** - Interactive choice flow
            • **Memory Buffer** - Remembers conversation context
            • **Smart Validation** - Asks for missing information
            """)
        
        with col2:
            st.warning("**🔑 Required API Keys:**")
            st.markdown("""
            **Essential:**
            • OpenAI or Gemini API key (AI provider)
            • AviationStack API key (flights)
            • RapidAPI key (hotels via Booking.com)
            • Google Places API key (attractions)
            
            **Optional:**
            • OpenWeatherMap API key (weather data)
            
            **Get Keys:**
            • [AviationStack](https://aviationstack.com/product) - Free tier
            • [RapidAPI](https://rapidapi.com) - Free signup
            • [Google Places](https://console.cloud.google.com) - Free quota
            • [OpenAI](https://platform.openai.com) - Pay per use
            • [Gemini](https://makersuite.google.com) - FREE!
            """)
        
        # Quick provider setup cards
        st.markdown("### 🚀 Quick Setup")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="provider-card">
                <h4>🔷 OpenAI GPT-3.5</h4>
                <p>• Premium quality responses<br>
                • Small cost per conversation<br>
                • Proven travel planning AI</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="provider-card">
                <h4>🟢 Google Gemini</h4>
                <p>• Completely FREE to use<br>
                • High quality responses<br>
                • Generous usage limits</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.error("**Configure your APIs in the sidebar to begin real travel planning!**")
        
        # Show example
        st.markdown("### 💬 Example Request:")
        st.code('''
"Hi! I want to plan a trip from Boston to Rome, Italy 
for 7 days in March 2026. My budget is $3,500 and 
I love adventure and cultural experiences!"
        ''')
        
        return
    
    # Step indicator
    display_step_indicator()
    
    # Chat messages display
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You</strong> • {message.get('timestamp', '')}
                <br>{message['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <strong>🤖 Atlas AI</strong> • {message.get('timestamp', '')}
                <br>{message['content']}
            </div>
            """, unsafe_allow_html=True)
    
    # Quick start examples
    if len(st.session_state.messages) == 0:
        st.markdown("**Quick Start Examples (API Calls):**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🇮🇹 Rome Cultural Adventure"):
                st.session_state.quick_query = "I want to plan a cultural adventure trip from Boston to Rome for 7 days in March 2026. Budget is $3500, love history and food!"
            if st.button("🇯🇵 Tokyo Spring Trip"):
                st.session_state.quick_query = "Plan a trip from New York to Tokyo for 10 days in April 2026. Budget $4000, interested in culture and technology!"
        
        with col2:
            if st.button("🇫🇷 Paris Romantic Getaway"):
                st.session_state.quick_query = "Romantic trip from Chicago to Paris for 5 days in June 2026. Budget $2500, love art and cuisine!"
            if st.button("🇬🇧 London Business Trip"):
                st.session_state.quick_query = "Business trip from Boston to London for 4 days in May 2026. Budget $2000, need efficient schedule!"
        
        with col3:
            if st.button("🇪🇸 Barcelona Art & Culture"):
                st.session_state.quick_query = "Art and culture trip to Barcelona for 6 days, budget $2000, love museums and architecture!"
            if st.button("🇹🇭 Thailand Adventure"):
                st.session_state.quick_query = "Adventure trip to Thailand for 2 weeks, budget travel, love outdoor activities and local food!"
    
    # Handle quick queries
    if hasattr(st.session_state, 'quick_query'):
        query = st.session_state.quick_query
        del st.session_state.quick_query
    else:
        # Chat input
        query = st.chat_input("Tell me about your trip plans...")
    
    # Process user input
    if query:
        # Add user message
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.messages.append({
            "role": "user",
            "content": query,
            "timestamp": timestamp
        })
        
        # Process with Atlas AI
        try:
            with st.spinner("🔍 calling APIs"):
                # Show which APIs are being called
                status_placeholder = st.empty()
                with status_placeholder:
                    st.info("🔄 Initializing real API calls...")
                
                st.session_state.chat_state = st.session_state.atlas_ai.chat(
                    query, st.session_state.chat_state
                )
                
                # Clear status
                status_placeholder.empty()
                
                # Get response
                response = st.session_state.chat_state.get("response", "Processing your request with real APIs...")
                response_time = datetime.now().strftime("%H:%M:%S")
                
                # Add assistant message
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": response_time
                })
                
        except Exception as e:
            error_msg = f"Sorry, I encountered an error with the real APIs: {str(e)}"
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
        
        st.rerun()
    
    # API Call Statistics
    if st.session_state.chat_state and len(st.session_state.messages) > 0:
        with st.expander("📊 Real API Call Statistics", expanded=False):
            state = st.session_state.chat_state
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**🔗 API Calls Made:**")
                if state.get("flight_options"):
                    st.write("✅ AviationStack called")
                    if state["flight_options"] and not state["flight_options"][0].get("error"):
                        st.write(f"   → {len(state['flight_options'])} options found")
                    else:
                        st.write("   → Error occurred")
                        
                if state.get("hotel_options"):
                    st.write("✅ Booking.com called")
                    if state["hotel_options"] and not state["hotel_options"][0].get("error"):
                        st.write(f"   → {len(state['hotel_options'])} options found")
                    else:
                        st.write("   → Error occurred")
                        
                if state.get("attractions_data"):
                    st.write("✅ Google Places called")
                    if state["attractions_data"] and not state["attractions_data"][0].get("error"):
                        st.write(f"   → {len(state['attractions_data'])} attractions found")
                    else:
                        st.write("   → Error occurred")
            
            with col2:
                st.write("**📊 Real Data Retrieved:**")
                flight_count = len([f for f in state.get("flight_options", []) if not f.get("error")])
                hotel_count = len([h for h in state.get("hotel_options", []) if not h.get("error")])
                attraction_count = len([a for a in state.get("attractions_data", []) if not a.get("error")])
                
                st.write(f"Valid Flights: {flight_count}")
                st.write(f"Valid Hotels: {hotel_count}")
                st.write(f"Valid Attractions: {attraction_count}")
                
                # Show selections
                if state.get("selected_flight") and state["selected_flight"].get("airline"):
                    st.write(f"✈️ Selected: {state['selected_flight']['airline']}")
                if state.get("selected_hotel") and state["selected_hotel"].get("name"):
                    st.write(f"🏨 Selected: {state['selected_hotel']['name']}")
            
            with col3:
                st.write("**🤖 System Info:**")
                st.write(f"AI: {st.session_state.selected_provider.title()}")
                conversations = len([m for m in st.session_state.messages if m['role'] == 'user'])
                st.write(f"Conversations: {conversations}")
                
                # Memory buffer info
                if hasattr(st.session_state.atlas_ai, 'memory'):
                    memory_msgs = len(st.session_state.atlas_ai.memory.chat_memory.messages)
                    st.write(f"Memory: {memory_msgs} messages")
                
                # Current step
                current_step = state.get("current_step", "initial")
                st.write(f"Step: {current_step}")
                
                # Completion percentage
                progress_map = {"initial": 10, "awaiting_missing_info": 15, "info_complete": 20, "flights": 35, "hotels": 60, "attractions": 80, "trip_style": 90, "itinerary": 95, "complete": 100}
                completion = progress_map.get(current_step, 10)
                st.write(f"Progress: {completion}%")
        
        # Show raw API data if available (for debugging)
        if st.checkbox("🔍 Show Raw API Data (Debug Mode)"):
            if st.session_state.chat_state.get("flight_options"):
                st.subheader("✈️ Raw Flight API Data")
                st.json(st.session_state.chat_state["flight_options"])
            
            if st.session_state.chat_state.get("hotel_options"):
                st.subheader("🏨 Raw Hotel API Data")
                st.json(st.session_state.chat_state["hotel_options"])
            
            if st.session_state.chat_state.get("attractions_data"):
                st.subheader("🎯 Raw Attractions API Data")
                st.json(st.session_state.chat_state["attractions_data"][:3])  # Show first 3 to avoid clutter
    
    # Footer
    if st.session_state.atlas_ai:
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.9em;">
            🌟 Powered by Real APIs • No Mock Data • Dynamic Itineraries • Memory Buffer • Smart Validation<br>
            Atlas AI Travel Assistant with LangGraph Multi-Agent System
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()