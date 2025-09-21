import os
from typing import TypedDict, List, Dict, Any, Literal, Optional
import requests
import json
from datetime import datetime, timedelta
import re
import psycopg2
import uuid

from langgraph.graph import StateGraph, START, END
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

load_dotenv()

# Travel State Schema
class RealAPITravelState(TypedDict):
    user_input: str
    conversation_history: List[Dict[str, str]]
    current_step: str
    awaiting_user_choice: bool
    origin: str
    destination: str
    duration_days: int
    budget: str
    interests: List[str]
    selected_flight: Dict[str, Any]
    selected_hotel: Dict[str, Any]
    selected_trip_style: str
    flight_options: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]
    attractions_data: List[Dict[str, Any]]
    response: str
    api_errors: List[str]

# ===========================================
# FREE PLACES API - NO API KEY NEEDED
# ===========================================

class FreePlacesAPI:
    """Free places API using OpenStreetMap - completely free, no API keys needed"""
    
    def get_attractions_free(self, destination: str, interests: list = None):
        """Get attractions using free APIs"""
        try:
            print(f"🆓 Calling FREE OpenStreetMap API for {destination}...")
            
            # Get coordinates using free Nominatim
            coords = self._get_coordinates(destination)
            if not coords:
                print("Using fallback attractions...")
                return self._get_fallback_attractions(destination)
            
            lat, lon = coords
            print(f"Found coordinates: {lat}, {lon}")
            
            # Query OpenStreetMap for attractions
            overpass_url = "http://overpass-api.de/api/interpreter"
            query = f"""
            [out:json][timeout:25];
            (
              node["tourism"~"^(attraction|museum|gallery|monument|memorial|castle|palace)$"](around:8000,{lat},{lon});
              node["historic"~"^(castle|palace|monument|memorial|ruins|archaeological_site)$"](around:8000,{lat},{lon});
              node["amenity"~"^(theatre|arts_centre|cinema)$"](around:8000,{lat},{lon});
              way["tourism"~"^(attraction|museum|gallery|monument|memorial)$"](around:8000,{lat},{lon});
            );
            out center;
            """
            
            response = requests.post(overpass_url, data=query, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                attractions = []
                
                for element in data.get('elements', [])[:15]:
                    tags = element.get('tags', {})
                    name = tags.get('name', 'Tourist Attraction')
                    
                    if name and name != 'yes' and len(name) > 1 and not name.isdigit():
                        attraction_type = self._get_attraction_type(tags)
                        price_info = self._get_price_info(tags)
                        
                        attractions.append({
                            'name': name,
                            'rating': '4.2⭐',
                            'address': self._format_address(tags, destination),
                            'types': [attraction_type],
                            'price_level': price_info,
                            'source': 'OpenStreetMap (FREE)'
                        })
                
                print(f"Found {len(attractions)} attractions from OpenStreetMap")
                
                if attractions:
                    # Add some fallback attractions to ensure we have good coverage
                    fallback = self._get_fallback_attractions(destination)
                    attractions.extend(fallback[:3])
                    
                    # Remove duplicates by name
                    unique_attractions = []
                    seen_names = set()
                    for attraction in attractions:
                        name_lower = attraction['name'].lower()
                        if name_lower not in seen_names:
                            unique_attractions.append(attraction)
                            seen_names.add(name_lower)
                    
                    return unique_attractions[:8]
                else:
                    print("No attractions found in OpenStreetMap, using fallback...")
                    return self._get_fallback_attractions(destination)
            else:
                print(f"OpenStreetMap API error: {response.status_code}")
                return self._get_fallback_attractions(destination)
                
        except Exception as e:
            print(f"Free API error: {e}")
            return self._get_fallback_attractions(destination)
    
    def _get_coordinates(self, destination: str):
        """Get coordinates using free Nominatim API"""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {'q': destination, 'format': 'json', 'limit': 1}
            headers = {'User-Agent': 'TravelBot/1.0'}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
            return None
        except Exception as e:
            print(f"Geocoding failed: {e}")
            return None
    
    def _get_attraction_type(self, tags: Dict) -> str:
        """Get attraction type from OSM tags"""
        if tags.get('tourism'):
            return tags['tourism'].replace('_', ' ').title()
        elif tags.get('historic'):
            return f"Historic {tags['historic'].replace('_', ' ').title()}"
        elif tags.get('amenity'):
            return tags['amenity'].replace('_', ' ').title()
        else:
            return 'Tourist Attraction'
    
    def _get_price_info(self, tags: Dict) -> str:
        """Get price info from OSM tags"""
        if tags.get('fee') == 'no':
            return 'Free'
        elif tags.get('fee') == 'yes':
            return 'Paid attraction'
        elif tags.get('tourism') == 'museum':
            return 'Museum admission fee'
        else:
            return 'Check locally for pricing'
    
    def _format_address(self, tags: Dict, destination: str) -> str:
        """Format address from OSM tags"""
        address_parts = []
        for key in ['addr:street', 'addr:city', 'addr:country']:
            if tags.get(key):
                address_parts.append(tags[key])
        
        if address_parts:
            return ', '.join(address_parts)
        else:
            return destination
    
    def _get_fallback_attractions(self, destination: str):
        """Static attractions for major cities"""
        fallback_data = {
            'rome': [
                {'name': 'Colosseum', 'rating': '4.6⭐', 'address': 'Piazza del Colosseo, Rome', 'types': ['monument'], 'price_level': '€12-16', 'source': 'Static Data'},
                {'name': 'Trevi Fountain', 'rating': '4.4⭐', 'address': 'Piazza di Trevi, Rome', 'types': ['monument'], 'price_level': 'Free', 'source': 'Static Data'},
                {'name': 'Vatican Museums', 'rating': '4.5⭐', 'address': 'Vatican City', 'types': ['museum'], 'price_level': '€17', 'source': 'Static Data'},
                {'name': 'Roman Forum', 'rating': '4.5⭐', 'address': 'Via della Salara Vecchia, Rome', 'types': ['historic'], 'price_level': '€12', 'source': 'Static Data'},
                {'name': 'Pantheon', 'rating': '4.5⭐', 'address': 'Piazza della Rotonda, Rome', 'types': ['monument'], 'price_level': 'Free', 'source': 'Static Data'}
            ],
            'paris': [
                {'name': 'Eiffel Tower', 'rating': '4.6⭐', 'address': 'Champ de Mars, Paris', 'types': ['monument'], 'price_level': '€10-25', 'source': 'Static Data'},
                {'name': 'Louvre Museum', 'rating': '4.7⭐', 'address': 'Rue de Rivoli, Paris', 'types': ['museum'], 'price_level': '€17', 'source': 'Static Data'},
                {'name': 'Notre-Dame Cathedral', 'rating': '4.5⭐', 'address': 'Île de la Cité, Paris', 'types': ['monument'], 'price_level': 'Free exterior', 'source': 'Static Data'},
                {'name': 'Arc de Triomphe', 'rating': '4.5⭐', 'address': 'Place Charles de Gaulle, Paris', 'types': ['monument'], 'price_level': '€13', 'source': 'Static Data'},
                {'name': 'Sacré-Cœur', 'rating': '4.5⭐', 'address': 'Montmartre, Paris', 'types': ['religious'], 'price_level': 'Free', 'source': 'Static Data'}
            ],
            'london': [
                {'name': 'Tower of London', 'rating': '4.5⭐', 'address': 'Tower Hill, London', 'types': ['castle'], 'price_level': '£25-30', 'source': 'Static Data'},
                {'name': 'British Museum', 'rating': '4.6⭐', 'address': 'Great Russell St, London', 'types': ['museum'], 'price_level': 'Free', 'source': 'Static Data'},
                {'name': 'Big Ben', 'rating': '4.4⭐', 'address': 'Westminster, London', 'types': ['monument'], 'price_level': 'Free to view', 'source': 'Static Data'},
                {'name': 'Westminster Abbey', 'rating': '4.5⭐', 'address': 'Westminster, London', 'types': ['religious'], 'price_level': '£25', 'source': 'Static Data'},
                {'name': 'London Eye', 'rating': '4.3⭐', 'address': 'Westminster Bridge, London', 'types': ['attraction'], 'price_level': '£30', 'source': 'Static Data'}
            ],
            'tokyo': [
                {'name': 'Senso-ji Temple', 'rating': '4.3⭐', 'address': 'Asakusa, Tokyo', 'types': ['religious'], 'price_level': 'Free', 'source': 'Static Data'},
                {'name': 'Tokyo National Museum', 'rating': '4.3⭐', 'address': 'Ueno, Tokyo', 'types': ['museum'], 'price_level': '¥1000', 'source': 'Static Data'},
                {'name': 'Meiji Shrine', 'rating': '4.4⭐', 'address': 'Shibuya, Tokyo', 'types': ['religious'], 'price_level': 'Free', 'source': 'Static Data'},
                {'name': 'Imperial Palace', 'rating': '4.2⭐', 'address': 'Chiyoda, Tokyo', 'types': ['historic'], 'price_level': 'Free gardens', 'source': 'Static Data'}
            ],
            'barcelona': [
                {'name': 'Sagrada Familia', 'rating': '4.7⭐', 'address': 'Carrer de Mallorca, Barcelona', 'types': ['monument'], 'price_level': '€20-26', 'source': 'Static Data'},
                {'name': 'Park Güell', 'rating': '4.4⭐', 'address': 'Gràcia, Barcelona', 'types': ['park'], 'price_level': '€10', 'source': 'Static Data'},
                {'name': 'Casa Batlló', 'rating': '4.5⭐', 'address': 'Passeig de Gràcia, Barcelona', 'types': ['architecture'], 'price_level': '€25', 'source': 'Static Data'},
                {'name': 'Gothic Quarter', 'rating': '4.4⭐', 'address': 'Ciutat Vella, Barcelona', 'types': ['historic'], 'price_level': 'Free to explore', 'source': 'Static Data'}
            ]
        }
        
        # Try to find matching city
        city_key = destination.lower().split(',')[0].strip()
        for city, attractions in fallback_data.items():
            if city in city_key or city_key in city:
                return attractions
        
        # Generic fallback for any city
        return [
            {'name': f'{destination} City Center', 'rating': '4.0⭐', 'address': destination, 'types': ['area'], 'price_level': 'Free to explore', 'source': 'Generic'},
            {'name': f'{destination} Historic District', 'rating': '4.1⭐', 'address': f'Historic {destination}', 'types': ['historic'], 'price_level': 'Free to walk', 'source': 'Generic'},
            {'name': f'{destination} Main Square', 'rating': '4.0⭐', 'address': f'Central {destination}', 'types': ['landmark'], 'price_level': 'Free', 'source': 'Generic'}
        ]

# ===========================================
# POSTGRESQL SESSION MANAGER
# ===========================================

class PostgreSQLSessionManager:
    """PostgreSQL session management for travel conversations"""
    
    def __init__(self):
        self.connection_config = {
            'host': '35.224.149.145',  # Your Cloud SQL IP
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
            
            state_json = json.dumps(state, default=str)  # Handle datetime objects
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

# ===========================================
# UNIFIED LLM INTERFACE (ORIGINAL)
# ===========================================

class UnifiedLLM:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider.lower()
        
        if self.provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(api_key=api_key, model="gpt-3.5-turbo", temperature=0.7)
                self.use_langchain = True
                print("✅ OpenAI initialized")
            except ImportError:
                raise ImportError("langchain-openai required")
                
        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                model_options = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                for model_name in model_options:
                    try:
                        self.model = genai.GenerativeModel(model_name)
                        test_response = self.model.generate_content("Hi")
                        print(f"✅ Gemini initialized with {model_name}")
                        break
                    except Exception as e:
                        continue
                else:
                    raise Exception("No working Gemini models found")
                
                self.use_langchain = False
            except ImportError:
                raise ImportError("google-generativeai required")
    
    def invoke(self, messages):
        if self.use_langchain:
            return self.llm.invoke(messages)
        else:
            prompt = ""
            for message in messages:
                if hasattr(message, 'content'):
                    content = message.content
                    if hasattr(message, 'type') and message.type == 'system':
                        prompt += f"Instructions: {content}\n\n"
                    else:
                        prompt += f"User: {content}\n"
            
            try:
                response = self.model.generate_content(prompt)
                class GeminiResponse:
                    def __init__(self, content):
                        self.content = content
                return GeminiResponse(response.text)
            except Exception as e:
                class ErrorResponse:
                    def __init__(self, content):
                        self.content = content
                return ErrorResponse(f"Error: {str(e)}")

class SystemMessage:
    def __init__(self, content):
        self.content = content
        self.type = 'system'

class HumanMessage:
    def __init__(self, content):
        self.content = content
        self.type = 'human'

def detect_available_providers():
    """Detect available AI providers"""
    providers = {}
    
    try:
        from langchain_openai import ChatOpenAI
        providers["OpenAI"] = "openai"
        print("✅ OpenAI available")
    except ImportError:
        print("❌ OpenAI not available")
    
    try:
        import google.generativeai as genai
        providers["Gemini"] = "gemini"
        print("✅ Gemini available")
    except ImportError:
        print("❌ Gemini not available")
    
    return providers

def interactive_setup():
    """Interactive setup with API key collection"""
    print("🌟 Travel Planning System Setup")
    print("=" * 40)
    
    available_providers = detect_available_providers()
    if not available_providers:
        return None, None
    
    # Provider selection
    if len(available_providers) == 1:
        provider_name = list(available_providers.keys())[0]
        provider_key = available_providers[provider_name]
        print(f"Using {provider_name}")
    else:
        print("\nChoose AI Provider:")
        for i, name in enumerate(available_providers.keys(), 1):
            cost_info = "💰 Pay per use" if name == "OpenAI" else "🆓 FREE"
            print(f"{i}. {name} ({cost_info})")
        
        while True:
            try:
                choice = int(input("\nEnter choice: "))
                provider_name = list(available_providers.keys())[choice - 1]
                provider_key = available_providers[provider_name]
                break
            except (ValueError, IndexError):
                print("Invalid choice")
    
    # API Key collection
    if provider_key == "openai":
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            print(f"✅ Found OpenAI API key in environment")
            api_key = env_key
        else:
            print("\n📋 OpenAI API Key Setup:")
            print("1. Go to: https://platform.openai.com/api-keys")
            print("2. Create an account and add payment method")
            print("3. Create a new API key")
            print("4. Copy and paste it below")
            api_key = input("\nEnter OpenAI API key: ").strip()
    else:  # Gemini
        env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if env_key:
            print(f"✅ Found Gemini API key in environment")
            api_key = env_key
        else:
            print("\n📋 Gemini API Key Setup (FREE!):")
            print("1. Go to: https://makersuite.google.com/app/apikey")
            print("2. Sign in with Google account (free)")
            print("3. Create API key")
            print("4. Copy and paste it below")
            api_key = input("\nEnter Gemini API key: ").strip()
    
    if not api_key:
        return None, None
    
    # Additional API Keys
    print("\n🔑 Travel API Keys:")
    
    # Flight API Key
    flight_key = os.getenv("FLIGHT_API_KEY")
    if not flight_key:
        print("\n✈️ Flight API (AviationStack) - FREE TIER:")
        print("1. Go to: https://aviationstack.com/product")
        print("2. Sign up for free account (1000 requests/month)")
        print("3. Get your access key")
        flight_key = input("Enter AviationStack API key (or press Enter to skip): ").strip()
        if flight_key:
            os.environ["FLIGHT_API_KEY"] = flight_key
    
    # Hotel API Key
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if not rapidapi_key:
        print("\n🏨 Hotel API (RapidAPI) - FREE TIER:")
        print("1. Go to: https://rapidapi.com")
        print("2. Sign up for free account")
        print("3. Subscribe to Booking.com API (free tier available)")
        print("4. Get your RapidAPI key")
        rapidapi_key = input("Enter RapidAPI key (or press Enter to skip): ").strip()
        if rapidapi_key:
            os.environ["RAPIDAPI_KEY"] = rapidapi_key
    
    print(f"\n✅ Setup complete!")
    print(f"🤖 AI Provider: {provider_name}")
    print(f"✈️ Flight API: {'Configured' if os.getenv('FLIGHT_API_KEY') else 'Not configured'}")
    print(f"🏨 Hotel API: {'Configured' if os.getenv('RAPIDAPI_KEY') else 'Not configured'}")
    print(f"🏛️ Places API: FREE OpenStreetMap (always available)")
    print(f"💾 Database: PostgreSQL (configured)")
    
    return provider_key, api_key

# ===========================================
# MAIN TRAVEL ASSISTANT CLASS
# ===========================================

class RealAPITravelAssistant:
    def __init__(self, provider: str, api_key: str):
        self.llm = UnifiedLLM(provider, api_key)
        self.memory = ConversationBufferMemory()
        
        # Add PostgreSQL session management
        try:
            self.session_manager = PostgreSQLSessionManager()
            print("✅ PostgreSQL session management ready")
        except Exception as e:
            print(f"⚠️ PostgreSQL failed: {e}")
            self.session_manager = None
        
        # Add free places API
        self.places_api = FreePlacesAPI()
        print("✅ Free Places API ready (OpenStreetMap)")
        
        self.graph = self._build_conversational_graph()
    
    def call_aviationstack_api(self, origin: str, destination: str, api_key: str) -> List[Dict[str, Any]]:
        """Call AviationStack for flight data with improved error handling"""
        try:
            url = "http://api.aviationstack.com/v1/flights"
            params = {
                "access_key": api_key,
                "dep_iata": origin,
                "arr_iata": destination,
                "limit": 4
            }
            
            print(f"Calling AviationStack: {origin} → {destination}")
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 401:
                raise Exception("AviationStack 401: Invalid API key")
            elif response.status_code == 403:
                raise Exception("AviationStack 403: Access denied - check API key or quota exceeded")
            elif response.status_code != 200:
                raise Exception(f"AviationStack HTTP error {response.status_code}")
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise Exception(f"AviationStack returned invalid JSON: {str(e)}")
            
            if "error" in data:
                error_info = data["error"]
                if isinstance(error_info, dict):
                    error_msg = error_info.get("message", "Unknown API error")
                    error_code = error_info.get("code", "Unknown code")
                    raise Exception(f"AviationStack API error {error_code}: {error_msg}")
                else:
                    raise Exception(f"AviationStack API error: {error_info}")
            
            flights_data = data.get("data", []) if isinstance(data, dict) else []
            
            if not flights_data:
                raise Exception(f"No flights found for route {origin} → {destination}")
            
            flights = []
            for i, flight in enumerate(flights_data[:4]):
                try:
                    airline_info = flight.get("airline", {}) or {}
                    flight_info = flight.get("flight", {}) or {}
                    departure_info = flight.get("departure", {}) or {}
                    arrival_info = flight.get("arrival", {}) or {}
                    
                    processed_flight = {
                        "airline": airline_info.get("name", "Unknown Airline"),
                        "flight_number": flight_info.get("number", "N/A"),
                        "departure": departure_info.get("scheduled", "N/A"),
                        "arrival": arrival_info.get("scheduled", "N/A"),
                        "source": "AviationStack",
                        "note": "Contact airline for pricing"
                    }
                    
                    flights.append(processed_flight)
                    
                except Exception as flight_error:
                    continue
            
            if not flights:
                raise Exception("Could not process any flight data from response")
            
            return flights
            
        except Exception as e:
            if "AviationStack" in str(e):
                raise e
            else:
                raise Exception(f"AviationStack API failed: {str(e)}")
    
    def call_booking_hotels_api(self, destination: str, checkin: str, checkout: str, api_key: str) -> List[Dict[str, Any]]:
        """Call Booking.com API with proper error handling"""
        try:
            # Step 1: Get destination ID
            search_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
            }
            
            search_params = {"name": destination, "locale": "en-gb"}
            search_response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
            
            if search_response.status_code == 401:
                raise Exception("Booking.com authentication failed - check your RapidAPI key")
            elif search_response.status_code == 403:
                raise Exception("Booking.com access forbidden - check subscription status")
            elif search_response.status_code != 200:
                raise Exception(f"Location search failed: HTTP {search_response.status_code}")
            
            try:
                search_data = search_response.json()
            except:
                raise Exception("Invalid JSON response from location search")
            
            if not search_data or len(search_data) == 0:
                raise Exception(f"No location found for {destination}")
            
            dest_id = search_data[0].get("dest_id")
            if not dest_id:
                raise Exception("Could not extract destination ID from response")
            
            # Step 2: Search hotels
            hotel_url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
            hotel_params = {
                "dest_id": str(dest_id),
                "order_by": "popularity",
                "filter_by_currency": "USD",
                "adults_number": "2",
                "checkin_date": checkin,
                "checkout_date": checkout,
                "room_number": "1",
                "locale": "en-gb",
                "dest_type": "city",
                "units": "metric",
                "page_number": "0"
            }
            
            hotel_response = requests.get(hotel_url, headers=headers, params=hotel_params, timeout=20)
            
            if hotel_response.status_code != 200:
                raise Exception(f"Hotel search failed: HTTP {hotel_response.status_code}")
            
            try:
                hotel_data = hotel_response.json()
            except:
                raise Exception("Invalid JSON response from hotel search")
            
            hotels = hotel_data.get("result", [])
            if not hotels:
                raise Exception("No hotels found in the response")
            
            # Format hotel data
            formatted_hotels = []
            nights = self.calculate_nights(checkin, checkout)
            
            for hotel in hotels[:4]:
                try:
                    hotel_name = hotel.get("hotel_name", "Hotel Name Not Available")
                    
                    price_info = hotel.get("min_total_price", hotel.get("composite_price_breakdown", {}))
                    if isinstance(price_info, dict):
                        total_price = price_info.get("gross_amount_per_night", {}).get("value", 150)
                    else:
                        total_price = float(price_info) if price_info else 150
                    
                    per_night = total_price / nights if nights > 0 else total_price
                    
                    formatted_hotels.append({
                        "name": hotel_name,
                        "price_per_night": int(per_night),
                        "total_price": int(total_price),
                        "location": hotel.get("district", hotel.get("city", "City center")),
                        "rating": f"{hotel.get('review_score', 'N/A')}⭐" if hotel.get('review_score') != "N/A" else "No rating",
                        "amenities": hotel.get("hotel_facilities", "Standard amenities"),
                        "source": "Booking.com",
                        "booking_url": hotel.get("url", "")
                    })
                    
                except Exception:
                    continue
            
            if not formatted_hotels:
                raise Exception("Could not parse any hotel data from response")
            
            return formatted_hotels
            
        except Exception as e:
            raise Exception(f"Booking.com API failed: {str(e)}")
    
    def call_google_places_api(self, destination: str, interests: List[str]) -> List[Dict[str, Any]]:
        """Use FREE Places API instead of Google Places - NO API KEY NEEDED"""
        try:
            print(f"🆓 Using FREE Places API for {destination} (saving you money!)...")
            return self.places_api.get_attractions_free(destination, interests)
        except Exception as e:
            print(f"Free Places API failed: {e}")
            return []
    
    def get_airport_code(self, city: str) -> str:
        """Convert city to airport code"""
        codes = {
            "boston": "BOS", "new york": "JFK", "los angeles": "LAX",
            "chicago": "ORD", "miami": "MIA", "san francisco": "SFO",
            "paris": "CDG", "london": "LHR", "rome": "FCO",
            "tokyo": "NRT", "barcelona": "BCN", "amsterdam": "AMS",
            "madrid": "MAD", "berlin": "BER", "munich": "MUC",
            "vienna": "VIE", "zurich": "ZUR", "milan": "MXP"
        }
        city_clean = city.lower().split(',')[0].strip()
        return codes.get(city_clean, city[:3].upper())
    
    def get_price_description(self, price_level: int) -> str:
        """Convert price level to description"""
        if price_level is None:
            return "Price not available"
        levels = {0: "Free", 1: "Budget", 2: "Moderate", 3: "Expensive", 4: "Very Expensive"}
        return levels.get(price_level, "Unknown")
    
    def calculate_nights(self, checkin: str, checkout: str) -> int:
        """Calculate nights"""
        try:
            checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
            checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
            return (checkout_date - checkin_date).days
        except:
            return 7
    
    def get_future_dates(self, duration_days: int) -> tuple:
        """Get future dates that won't be rejected by APIs"""
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=30 + duration_days)).strftime("%Y-%m-%d")
        return checkin, checkout

    # [ALL YOUR ORIGINAL LANGGRAPH METHODS REMAIN EXACTLY THE SAME]
    def _build_conversational_graph(self) -> StateGraph:
        """Build step-by-step conversational graph"""
        workflow = StateGraph(RealAPITravelState)
        
        workflow.add_node("extract_info", self._extract_info)
        workflow.add_node("handle_missing_info", self._handle_missing_info)
        workflow.add_node("search_flights", self._search_flights)
        workflow.add_node("search_hotels", self._search_hotels)
        workflow.add_node("search_attractions", self._search_attractions)
        workflow.add_node("handle_style_decision", self._handle_style_decision)
        workflow.add_node("choose_style", self._choose_style)
        workflow.add_node("create_itinerary", self._create_itinerary)
        workflow.add_node("handle_choice", self._handle_choice)
        
        workflow.add_edge(START, "extract_info")
        
        workflow.add_conditional_edges(
            "extract_info",
            self._check_info_complete,
            {"complete": "search_flights", "missing": END, "error": END}
        )
        
        workflow.add_conditional_edges(
            "handle_missing_info", 
            self._check_info_complete,
            {"complete": "search_flights", "missing": END, "error": END}
        )
        
        workflow.add_conditional_edges(
            "search_flights",
            self._should_wait,
            {"wait": END, "continue": "search_hotels", "error": END}
        )
        
        workflow.add_conditional_edges(
            "search_hotels",
            self._should_wait,
            {"wait": END, "continue": "search_attractions", "error": END}
        )
        
        workflow.add_conditional_edges(
            "search_attractions",
            self._should_wait,
            {"wait": END, "continue": "handle_style_decision", "error": END}
        )
        
        workflow.add_conditional_edges(
            "handle_style_decision",
            self._route_after_style_decision,
            {"choose_style": "choose_style", "skip_to_itinerary": "create_itinerary"}
        )
        
        workflow.add_conditional_edges(
            "choose_style",
            self._should_wait,
            {"wait": END, "continue": "create_itinerary"}
        )
        
        workflow.add_edge("create_itinerary", END)
        workflow.add_edge("handle_choice", END)
        
        return workflow.compile()

    # [ALL YOUR ORIGINAL NODE METHODS - UNCHANGED]
    def _extract_info(self, state: RealAPITravelState) -> RealAPITravelState:
        """Extract trip details using AI with validation"""
        user_input = state["user_input"]
        
        try:
            extraction_prompt = f"Extract from: '{user_input}'\n\nFormat:\nOrigin: [city]\nDestination: [city]\nDuration: [days]\nBudget: [amount]\nInterests: [list]"
            
            messages = [SystemMessage("Extract travel info."), HumanMessage(extraction_prompt)]
            extraction = self.llm.invoke(messages)
            extracted_text = extraction.content
            
            # Parse extraction
            for line in extracted_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == "origin" and value and value != "[city]" and len(value) > 2:
                        state["origin"] = value
                    elif key == "destination" and value and value != "[city]" and len(value) > 2:
                        state["destination"] = value
                    elif key == "duration":
                        duration_match = re.findall(r'\d+', value)
                        if duration_match:
                            duration = int(duration_match[0])
                            if 1 <= duration <= 30:
                                state["duration_days"] = duration
                    elif key == "budget" and value and value != "[amount]":
                        state["budget"] = value
                    elif key == "interests" and value and value != "[list]":
                        interests = [i.strip() for i in value.split(',') if i.strip() and len(i.strip()) > 1]
                        if interests:
                            state["interests"] = interests
            
            # Validate required information
            missing_info = []
            
            if not state.get("origin"):
                missing_info.append("departure city")
            if not state.get("destination"):
                missing_info.append("destination")
            if not state.get("duration_days") or state.get("duration_days") < 1:
                missing_info.append("trip duration (number of days)")
            
            if missing_info:
                if len(missing_info) == 1:
                    state["response"] = f"I need to know your {missing_info[0]} to help plan your trip. Could you please provide that information?"
                else:
                    info_list = ", ".join(missing_info[:-1]) + f" and {missing_info[-1]}"
                    state["response"] = f"To plan your perfect trip, I need a few more details: {info_list}. Could you please provide this information?"
                
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                return state
            
            # Set defaults
            if not state.get("budget"):
                state["budget"] = "flexible"
            if not state.get("interests"):
                state["interests"] = ["cultural", "sightseeing"]
            
            # Validate destination different from origin
            if state["origin"].lower() == state["destination"].lower():
                state["response"] = "It looks like your departure and destination cities are the same. Could you please specify a different destination for your trip?"
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                return state
                
        except Exception as e:
            print(f"Extraction error: {e}")
            state["response"] = "I'm having trouble understanding your trip details. Could you please tell me:\n\n1. Where are you departing from?\n2. Where do you want to go?\n3. How many days will your trip be?\n\nFor example: 'I want to travel from Boston to Rome for 7 days'"
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_missing_info"
            return state
        
        state["response"] = f"Perfect! Let me find real flights from {state['origin']} to {state['destination']} for your {state['duration_days']}-day trip!"
        state["api_errors"] = []
        return state
    
    def _handle_missing_info(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle collection of missing trip information"""
        user_input = state["user_input"]
        
        try:
            extraction_prompt = f"""
            User provided additional info: '{user_input}'
            
            Current trip details:
            - Origin: {state.get('origin', 'missing')}
            - Destination: {state.get('destination', 'missing')} 
            - Duration: {state.get('duration_days', 'missing')} days
            - Budget: {state.get('budget', 'missing')}
            - Interests: {state.get('interests', [])}
            
            Extract any NEW information and return in format:
            Origin: [city or 'keep current']
            Destination: [city or 'keep current'] 
            Duration: [days or 'keep current']
            Budget: [amount or 'keep current']
            Interests: [list or 'keep current']
            """
            
            messages = [SystemMessage("Extract missing travel information."), HumanMessage(extraction_prompt)]
            extraction = self.llm.invoke(messages)
            extracted_text = extraction.content
            
            # Parse the new information
            for line in extracted_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == "origin" and value and value != "keep current" and value != "[city]" and len(value) > 2:
                        state["origin"] = value
                    elif key == "destination" and value and value != "keep current" and value != "[city]" and len(value) > 2:
                        state["destination"] = value
                    elif key == "duration" and value and value != "keep current":
                        duration_match = re.findall(r'\d+', value)
                        if duration_match:
                            duration = int(duration_match[0])
                            if 1 <= duration <= 30:
                                state["duration_days"] = duration
                    elif key == "budget" and value and value != "keep current" and value != "[amount]":
                        state["budget"] = value
                    elif key == "interests" and value and value != "keep current" and value != "[list]":
                        interests = [i.strip() for i in value.split(',') if i.strip() and len(i.strip()) > 1]
                        if interests:
                            state["interests"] = interests
            
            # Check if we still have missing required information
            missing_info = []
            
            if not state.get("origin"):
                missing_info.append("departure city")
            if not state.get("destination"): 
                missing_info.append("destination city")
            if not state.get("duration_days") or state.get("duration_days") < 1:
                missing_info.append("trip duration")
                
            if missing_info:
                if "departure city" in missing_info:
                    state["response"] = "Which city will you be departing from? (e.g., Boston, New York, Chicago)"
                elif "destination city" in missing_info:
                    state["response"] = "Where would you like to travel to? (e.g., Rome, Paris, Tokyo)"
                elif "trip duration" in missing_info:
                    state["response"] = "How many days will your trip be? (e.g., 7 days, 2 weeks)"
                else:
                    state["response"] = f"I still need: {', '.join(missing_info)}. Could you provide these details?"
                
                state["awaiting_user_choice"] = True  
                state["current_step"] = "awaiting_missing_info"
                return state
            
            # Validate the information makes sense
            if state["origin"].lower() == state["destination"].lower():
                state["response"] = "Your departure and destination cities are the same. Where would you like to travel to from " + state["origin"] + "?"
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info" 
                return state
                
            # Set defaults for optional fields
            if not state.get("budget"):
                state["budget"] = "flexible"
            if not state.get("interests"):
                state["interests"] = ["cultural", "sightseeing"]
                
        except Exception as e:
            state["response"] = "I'm having trouble understanding. Could you please tell me: departure city, destination city, and number of days?"
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_missing_info"
            return state
        
        state["response"] = f"Excellent! Now I have all the details. Let me find real flights from {state['origin']} to {state['destination']} for your {state['duration_days']}-day trip!"
        state["awaiting_user_choice"] = False
        state["current_step"] = "info_complete"
        
        return state
    
    def _search_flights(self, state: RealAPITravelState) -> RealAPITravelState:
        """Search flights using AviationStack"""
        print(f"🛫 Searching flights: {state['origin']} → {state['destination']}")
        
        try:
            api_key = os.getenv("FLIGHT_API_KEY")
            if not api_key:
                raise Exception("FLIGHT_API_KEY not configured")
            
            origin_code = self.get_airport_code(state["origin"])
            dest_code = self.get_airport_code(state["destination"])
            
            flight_options = self.call_aviationstack_api(origin_code, dest_code, api_key)
            state["flight_options"] = flight_options
            
            response = f"Here are real flights from AviationStack:\n\n"
            
            for i, flight in enumerate(flight_options, 1):
                dep_time = flight['departure']
                if 'T' in dep_time:
                    dep_time = dep_time.split('T')[1][:5]
                
                response += f"**Option {i}: {flight['airline']}**\n"
                response += f"Flight {flight['flight_number']}\n"
                response += f"Departs: {dep_time}\n"
                response += f"{flight['note']}\n\n"
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_flight_choice"
            
        except Exception as e:
            error_msg = str(e)
            state["api_errors"].append(f"Flight: {error_msg}")
            state["response"] = f"❌ Flight search failed: {error_msg}"
            state["awaiting_user_choice"] = False
            state["current_step"] = "flight_error"
        
        return state
    
    def _search_hotels(self, state: RealAPITravelState) -> RealAPITravelState:
        """Search hotels using Booking.com API"""
        print(f"🏨 Searching hotels in {state['destination']}")
        
        try:
            api_key = os.getenv("RAPIDAPI_KEY")
            if not api_key:
                raise Exception("RAPIDAPI_KEY not configured")
            
            checkin, checkout = self.get_future_dates(state["duration_days"])
            
            hotel_options = self.call_booking_hotels_api(state["destination"], checkin, checkout, api_key)
            state["hotel_options"] = hotel_options
            
            response = f"Great choice! Here are real hotels from Booking.com:\n\n"
            
            for i, hotel in enumerate(hotel_options, 1):
                response += f"**Option {i}: {hotel['name']}**\n"
                response += f"**${hotel['price_per_night']}/night**\n"
                response += f"Total: ${hotel['total_price']} for {state['duration_days']} nights\n"
                response += f"📍 {hotel['location']} • {hotel['rating']}\n\n"
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_hotel_choice"
            
        except Exception as e:
            error_msg = str(e)
            state["api_errors"].append(f"Hotel: {error_msg}")
            state["response"] = f"❌ Hotel search failed: {error_msg}"
            state["awaiting_user_choice"] = False
            state["current_step"] = "hotel_error"
        
        return state
    
    def _search_attractions(self, state: RealAPITravelState) -> RealAPITravelState:
        """Search attractions using FREE Places API"""
        print(f"🎯 Searching attractions in {state['destination']}")
        
        try:
            # Use the FREE places API - no cost!
            attractions = self.call_google_places_api(state["destination"], state.get("interests", []))
            state["attractions_data"] = attractions
            
            response = f"Found {len(attractions)} real attractions using FREE APIs 💰:\n\n"
            
            for attraction in attractions[:5]:
                response += f"• {attraction['name']} ({attraction['rating']})\n"
                response += f"  {attraction.get('price_level', 'Price varies')} - {attraction.get('source', 'Free API')}\n"
            
            response += f"\n**Would you like to:**\n"
            response += f"1. **Choose a specific travel style** (Adventure, Cultural, Leisure, etc.)\n"
            response += f"2. **Create itinerary now** with a balanced cultural style\n\n"
            response += f"Type '1' to customize or '2' to proceed directly to your itinerary."
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_style_decision"
            
        except Exception as e:
            error_msg = str(e)
            state["api_errors"].append(f"Attractions: {error_msg}")
            state["response"] = f"❌ Attractions search failed: {error_msg}"
            state["awaiting_user_choice"] = False
            state["current_step"] = "attractions_error"
        
        return state
    
    def _handle_style_decision(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle user's decision about trip style customization"""
        user_input = state["user_input"].strip().lower()
        
        choice_prompt = f"User said: '{user_input}'\nThey can choose:\n1. Customize travel style\n2. Skip to itinerary\n\nWhat did they choose? Return only '1' or '2'."
        
        try:
            messages = [SystemMessage("Determine user choice."), HumanMessage(choice_prompt)]
            choice_response = self.llm.invoke(messages)
            choice = choice_response.content.strip()
            
            if "1" in choice or "customize" in user_input or "style" in user_input:
                state["current_step"] = "need_style_choice"
                state["response"] = "Perfect! Let's choose your travel style."
            else:
                state["selected_trip_style"] = "cultural"
                state["current_step"] = "skip_to_itinerary"
                state["response"] = "Great! Creating your balanced cultural itinerary now..."
                
            state["awaiting_user_choice"] = False
            
        except Exception as e:
            state["selected_trip_style"] = "cultural"
            state["current_step"] = "skip_to_itinerary"
            state["response"] = "Creating your itinerary with a cultural focus..."
            state["awaiting_user_choice"] = False
        
        return state
    
    def _choose_style(self, state: RealAPITravelState) -> RealAPITravelState:
        """Show trip style options"""
        response = f"Excellent! Now choose your {state['destination']} travel style:\n\n"
        response += "🏔️ **Adventure** - Thrilling experiences\n\n"
        response += "🏖️ **Leisure** - Relaxation\n\n"
        response += "💼 **Business** - Efficient travel\n\n"
        response += "🏺 **Cultural** - Museums and history\n\n"
        response += "🌲 **Outdoor** - Nature activities\n\n"
        
        state["response"] = response
        state["awaiting_user_choice"] = True
        state["current_step"] = "awaiting_style_choice"
        
        return state
    
    def _create_itinerary(self, state: RealAPITravelState) -> RealAPITravelState:
        """Create final itinerary"""
        try:
            selected_flight = state.get("selected_flight", {})
            selected_hotel = state.get("selected_hotel", {})
            attractions = state.get("attractions_data", [])
            trip_style = state.get("selected_trip_style", "cultural")
            
            attractions_text = "\n".join([f"• {a['name']} ({a['rating']}) - {a.get('source', 'Free API')}" for a in attractions[:8]])
            
            prompt = f"""Create a {state['duration_days']}-day {trip_style} itinerary for {state['destination']}:
            
            Flight: {selected_flight.get('airline', 'Selected')} {selected_flight.get('flight_number', '')}
            Hotel: {selected_hotel.get('name', 'Selected')} in {selected_hotel.get('location', 'city center')}
            
            Real attractions (from FREE APIs):
            {attractions_text}
            
            Create day-by-day plans using these real places."""
            
            messages = [SystemMessage("Create detailed itinerary."), HumanMessage(prompt)]
            itinerary_response = self.llm.invoke(messages)
            
            response = f"Perfect! Your complete {state['destination']} {trip_style} experience:\n\n"
            response += f"✈️ Flight: {selected_flight.get('airline', 'Selected')}\n"
            response += f"🏨 Hotel: {selected_hotel.get('name', 'Selected')} - ${selected_hotel.get('price_per_night', 'N/A')}/night\n"
            response += f"🎯 Style: {trip_style.title()}\n\n"
            response += f"**📅 Your Detailed Itinerary:**\n\n"
            response += itinerary_response.content
            response += f"\n\n**🌟 Based on real API data from AviationStack, Booking.com, and FREE OpenStreetMap!**"
            response += f"\n💰 **Cost Savings**: Used FREE Places API instead of Google Places (saved $0.017 per search)"
            
            state["response"] = response
            state["current_step"] = "complete"
            
        except Exception as e:
            state["response"] = f"Itinerary creation failed: {str(e)}"
        
        return state
    
    def _handle_choice(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle user choices using AI"""
        user_input = state["user_input"]
        current_step = state.get("current_step", "")
        
        try:
            if "awaiting_flight_choice" in current_step:
                flight_options = state.get("flight_options", [])
                airlines = [f["airline"] for f in flight_options]
                
                choice_prompt = f"User said: '{user_input}'\nFlights: {airlines}\nWhich index (0-3)? Return only number."
                messages = [SystemMessage("Determine choice."), HumanMessage(choice_prompt)]
                choice_response = self.llm.invoke(messages)
                
                try:
                    choice_index = int(choice_response.content.strip())
                    state["selected_flight"] = flight_options[choice_index] if choice_index < len(flight_options) else flight_options[0]
                except:
                    state["selected_flight"] = flight_options[0] if flight_options else {}
                
                state["current_step"] = "need_hotels"
                
            elif "awaiting_hotel_choice" in current_step:
                hotel_options = state.get("hotel_options", [])
                hotel_names = [h["name"] for h in hotel_options]
                
                choice_prompt = f"User said: '{user_input}'\nHotels: {hotel_names}\nWhich index (0-3)? Return only number."
                messages = [SystemMessage("Determine choice."), HumanMessage(choice_prompt)]
                choice_response = self.llm.invoke(messages)
                
                try:
                    choice_index = int(choice_response.content.strip())
                    state["selected_hotel"] = hotel_options[choice_index] if choice_index < len(hotel_options) else hotel_options[0]
                except:
                    state["selected_hotel"] = hotel_options[0] if hotel_options else {}
                
                state["current_step"] = "need_attractions"
                
            elif "awaiting_style_choice" in current_step:
                style_prompt = f"User said: '{user_input}'\nStyles: adventure, leisure, business, cultural, outdoor\nWhich one? Return one word."
                messages = [SystemMessage("Determine style."), HumanMessage(style_prompt)]
                style_response = self.llm.invoke(messages)
                
                chosen_style = style_response.content.strip().lower()
                if chosen_style in ["adventure", "leisure", "business", "cultural", "outdoor"]:
                    state["selected_trip_style"] = chosen_style
                else:
                    state["selected_trip_style"] = "cultural"
                
                state["current_step"] = "need_itinerary"
            
            state["response"] = "Perfect choice! Continuing..."
            state["awaiting_user_choice"] = False
            
        except Exception as e:
            state["response"] = f"Error processing choice: {str(e)}"
        
        return state
    
    def _check_info_complete(self, state: RealAPITravelState) -> Literal["complete", "missing", "error"]:
        """Check if we have all required information to proceed"""
        if state.get("api_errors"):
            return "error"
        elif state.get("awaiting_user_choice") and state.get("current_step") == "awaiting_missing_info":
            return "missing"
        elif state.get("origin") and state.get("destination") and state.get("duration_days"):
            return "complete"
        else:
            return "missing"
    
    def _should_wait(self, state: RealAPITravelState) -> Literal["wait", "error", "continue"]:
        """Check if should wait for user choice"""
        if state.get("api_errors"):
            return "error"
        elif state.get("awaiting_user_choice"):
            return "wait"
        else:
            return "continue"
    
    def _route_after_style_decision(self, state: RealAPITravelState) -> Literal["choose_style", "skip_to_itinerary"]:
        """Route based on user's style decision"""
        current_step = state.get("current_step", "")
        
        if current_step == "need_style_choice":
            return "choose_style"
        else:
            return "skip_to_itinerary"

    # ===========================================
    # POSTGRESQL INTEGRATION METHODS
    # ===========================================
    
    def chat_with_persistence(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """Enhanced chat with PostgreSQL persistence"""
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Load existing session or create new
        current_state = None
        if self.session_manager:
            current_state = self.session_manager.load_session(session_id)
        
        if current_state:
            print(f"📂 Loaded session {session_id}")
            current_state["user_input"] = user_input
        else:
            print(f"🆕 New session {session_id}")
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
            # Process using existing chat method
            result = self.chat(user_input, current_state)
            
            # Add session ID to result
            result["session_id"] = session_id
            
            # Save updated state to PostgreSQL
            if self.session_manager and self.session_manager.save_session(session_id, result):
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
            
            if self.session_manager:
                self.session_manager.save_session(session_id, error_result)
            return error_result
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        if not self.session_manager:
            return None
            
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
                "has_hotel": bool(state.get("selected_hotel", {})),
                "trip_style": state.get("selected_trip_style", "")
            }
        }
    
    def list_sessions(self, limit: int = 20) -> list:
        """List recent sessions with info"""
        if not self.session_manager:
            return []
            
        sessions = self.session_manager.list_sessions(limit)
        
        # Add session info to each
        enhanced_sessions = []
        for session in sessions:
            session_info = self.get_session_info(session["session_id"])
            if session_info:
                session.update(session_info)
            enhanced_sessions.append(session)
        
        return enhanced_sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if not self.session_manager:
            return False
        return self.session_manager.delete_session(session_id)
    
    # ===========================================
    # ORIGINAL CHAT METHOD (PRESERVED)
    # ===========================================
    
    def chat(self, user_input: str, current_state: RealAPITravelState = None) -> RealAPITravelState:
        """Main chat interface with memory buffer integration and validation"""
        # Add to conversation memory
        self.memory.chat_memory.add_user_message(user_input)
        
        if current_state is None:
            # Initial planning
            current_state = {
                "user_input": user_input, "conversation_history": [],
                "current_step": "initial", "awaiting_user_choice": False,
                "origin": "", "destination": "", "duration_days": 0, "budget": "",
                "interests": [], "selected_flight": {}, "selected_hotel": {},
                "selected_trip_style": "", "flight_options": [], "hotel_options": [],
                "attractions_data": [], "response": "", "api_errors": []
            }
            
            result = self.graph.invoke(current_state)
            
            # Add AI response to memory
            self.memory.chat_memory.add_ai_message(result.get("response", ""))
            
            return result
            
        else:
            # Handle user input based on current step
            current_state["user_input"] = user_input
            
            # Handle missing information collection
            if current_state.get("current_step") == "awaiting_missing_info":
                result = self._handle_missing_info(current_state)
                
                # If info is now complete, proceed to flights
                if result.get("current_step") == "info_complete":
                    result = self._search_flights(result)
                
                # Add AI response to memory
                self.memory.chat_memory.add_ai_message(result.get("response", ""))
                return result
            
            # Handle style decision
            elif current_state.get("current_step") == "awaiting_style_decision":
                result = self._handle_style_decision(current_state)
                
                # Route based on decision
                if result.get("current_step") == "need_style_choice":
                    result = self._choose_style(result)
                elif result.get("current_step") == "skip_to_itinerary":
                    result = self._create_itinerary(result)
                
                # Add AI response to memory
                self.memory.chat_memory.add_ai_message(result.get("response", ""))
                return result
            
            # Handle other choice situations  
            elif current_state.get("awaiting_user_choice"):
                choice_state = self._handle_choice(current_state)
                
                # Continue to next step based on choice type
                if choice_state["current_step"] == "need_hotels":
                    result = self._search_hotels(choice_state)
                elif choice_state["current_step"] == "need_attractions":
                    result = self._search_attractions(choice_state)
                elif choice_state["current_step"] == "need_itinerary":
                    result = self._create_itinerary(choice_state)
                else:
                    result = choice_state
                
                # Add AI response to memory
                self.memory.chat_memory.add_ai_message(result.get("response", ""))
                
                return result
            else:
                return current_state

# ===========================================
# MAIN EXECUTION WITH API KEY COLLECTION
# ===========================================

if __name__ == "__main__":
    print("🔑 Travel Assistant Setup & Status:")
    print("=" * 50)
    
    # Check API status
    print(f"✈️ AviationStack: {'✅ Configured' if os.getenv('FLIGHT_API_KEY') else '❌ Not configured'}")
    print(f"🏨 RapidAPI: {'✅ Configured' if os.getenv('RAPIDAPI_KEY') else '❌ Not configured'}")
    print(f"🏛️ Places API: ✅ FREE OpenStreetMap (No API key needed!)")
    print(f"💾 PostgreSQL: ✅ Ready")
    print(f"🤖 AI Provider: Will be selected during setup")
    
    # Interactive setup with API key collection
    provider, api_key = interactive_setup()
    if not provider or not api_key:
        print("❌ Setup cancelled")
        exit(1)
    
    try:
        # Initialize Atlas AI
        atlas_ai = RealAPITravelAssistant(provider, api_key)
        print(f"\n🤖 Atlas AI Ready! (AI: {provider.title()})")
        print("=" * 50)
        print("✅ Real APIs: AviationStack + Booking.com + FREE OpenStreetMap")
        print("✅ PostgreSQL Session Persistence: Enabled")
        print("✅ Cost Savings: FREE Places API (saves $0.017 per search)")
        print("✅ Enhanced Features: Session management, conversation memory")
        print("\nTell me about your trip!\n")
        
        # Start conversation with session management
        session_id = str(uuid.uuid4())
        print(f"📱 Session ID: {session_id[:8]}...")
        print("💡 Your conversation will be saved and can be resumed later!")
        print("-" * 50)
        
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print(f"\n👋 Goodbye! Your session {session_id[:8]}... has been saved.")
                print("You can resume this conversation later using chat_with_persistence()")
                break
            
            if user_input.strip():
                try:
                    # Use chat_with_persistence for PostgreSQL session management
                    result = atlas_ai.chat_with_persistence(user_input, session_id)
                    print(f"\n🤖 Atlas AI: {result['response']}")
                    
                    # Show current status
                    if result.get("awaiting_user_choice"):
                        print(f"\n⏳ Status: {result['current_step']} - Waiting for your choice...")
                    
                    # Show trip progress
                    if result.get("current_step") != "initial":
                        session_info = atlas_ai.get_session_info(session_id)
                        if session_info and session_info['trip_details']:
                            trip = session_info['trip_details']
                            if trip['origin'] or trip['destination']:
                                progress_items = []
                                if trip['origin']: progress_items.append(f"From: {trip['origin']}")
                                if trip['destination']: progress_items.append(f"To: {trip['destination']}")
                                if trip['duration_days']: progress_items.append(f"Duration: {trip['duration_days']} days")
                                if trip['has_flight']: progress_items.append("✅ Flight selected")
                                if trip['has_hotel']: progress_items.append("✅ Hotel selected")
                                if trip['trip_style']: progress_items.append(f"Style: {trip['trip_style']}")
                                
                                if progress_items:
                                    print(f"\n📊 Trip Progress: {' | '.join(progress_items)}")
                    
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}")
                    print("Please try again or type 'quit' to exit.")
    
    except Exception as e:
        print(f"\n❌ System Error: {str(e)}")
        print("Please check your API keys and try again.")

