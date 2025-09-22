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
# ENHANCED POSTGRESQL SESSION MANAGER - COMPLETE
# ===========================================

class EnhancedPostgreSQLManager:
    """Enhanced PostgreSQL session management - works with psycopg2"""
    
    def __init__(self):
        self.connection_config = {
            'host': '35.224.149.145',
            'port': 5432,
            'database': 'travel_sessions',
            'user': 'chatbot_user',
            'password': '#Mansi1234'
        }
        self._setup_enhanced_tables()
    
    def _setup_enhanced_tables(self):
        """Create enhanced tables"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enhanced_travel_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    conversation_state TEXT,
                    current_step VARCHAR(100),
                    awaiting_user_choice BOOLEAN DEFAULT FALSE,
                    origin VARCHAR(255),
                    destination VARCHAR(255),
                    duration_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            cursor.close()
            conn.close()
            print("Enhanced PostgreSQL tables ready")
            
        except Exception as e:
            print(f"Enhanced PostgreSQL setup failed: {e}")
    
    def save_session(self, session_id: str, state: Dict[str, Any]) -> bool:
        """Save session state"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            state_json = json.dumps(state, default=str)
            current_time = datetime.now()
            
            cursor.execute('''
                INSERT INTO enhanced_travel_sessions 
                (session_id, conversation_state, current_step, awaiting_user_choice,
                 origin, destination, duration_days, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    conversation_state = %s,
                    current_step = %s,
                    awaiting_user_choice = %s,
                    origin = %s,
                    destination = %s,
                    duration_days = %s,
                    updated_at = %s
            ''', (
                session_id, state_json, state.get("current_step", ""),
                state.get("awaiting_user_choice", False), state.get("origin", ""),
                state.get("destination", ""), state.get("duration_days", 0), current_time,
                # For UPDATE
                state_json, state.get("current_step", ""),
                state.get("awaiting_user_choice", False), state.get("origin", ""),
                state.get("destination", ""), state.get("duration_days", 0), current_time
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Failed to save session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('SELECT conversation_state FROM enhanced_travel_sessions WHERE session_id = %s', (session_id,))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            print(f"Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(self, limit: int = 20) -> list:
        """List recent sessions"""
        try:
            conn = psycopg2.connect(**self.connection_config)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, current_step, awaiting_user_choice, origin, destination,
                       duration_days, updated_at
                FROM enhanced_travel_sessions 
                ORDER BY updated_at DESC 
                LIMIT %s
            ''', (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            sessions = []
            for row in results:
                sessions.append({
                    "session_id": row[0],
                    "current_step": row[1],
                    "awaiting_user_choice": row[2],
                    "last_activity": row[6].isoformat() if row[6] else None,
                    "trip_details": {
                        "origin": row[3] or "",
                        "destination": row[4] or "",
                        "duration_days": row[5] or 0
                    }
                })
            
            return sessions
            
        except Exception as e:
            print(f"Failed to list sessions: {e}")
            return []

# ===========================================
# REAL PLACES API - COMPLETE IMPLEMENTATION
# ===========================================

class RealPlacesAPI:
    """Real places API using OpenStreetMap - gets actual data from APIs"""
    
    def get_attractions_real(self, destination: str, interests: list = None):
        """Get attractions using real APIs - no hardcoded data"""
        try:
            print(f"Calling REAL OpenStreetMap API for {destination}...")
            
            # Get coordinates using free Nominatim
            coords = self._get_coordinates(destination)
            if not coords:
                print("No coordinates found, cannot get real attraction data")
                return []
            
            lat, lon = coords
            print(f"Found coordinates: {lat}, {lon}")
            
            # Query OpenStreetMap for attractions - REAL API CALL
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
                
                for element in data.get('elements', [])[:20]:
                    tags = element.get('tags', {})
                    name = tags.get('name', 'Tourist Attraction')
                    
                    if name and name != 'yes' and len(name) > 1 and not name.isdigit():
                        attraction_type = self._get_attraction_type(tags)
                        price_info = self._get_real_price_info(tags)
                        
                        attractions.append({
                            'name': name,
                            'rating': self._get_real_rating_info(tags),
                            'address': self._format_address(tags, destination),
                            'types': [attraction_type],
                            'price_level': price_info,
                            'source': 'OpenStreetMap API'
                        })
                
                print(f"Found {len(attractions)} REAL attractions from OpenStreetMap API")
                return attractions[:15]
            else:
                print(f"OpenStreetMap API error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Real API error: {e}")
            return []
    
    def _get_coordinates(self, destination: str):
        """Get real coordinates using free Nominatim API"""
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
        """Get attraction type from real OSM tags"""
        if tags.get('tourism'):
            return tags['tourism'].replace('_', ' ').title()
        elif tags.get('historic'):
            return f"Historic {tags['historic'].replace('_', ' ').title()}"
        elif tags.get('amenity'):
            return tags['amenity'].replace('_', ' ').title()
        else:
            return 'Tourist Attraction'
    
    def _get_real_price_info(self, tags: Dict) -> str:
        """Get real price info from OSM tags - no hardcoded prices"""
        if tags.get('fee') == 'no':
            return 'Free'
        elif tags.get('fee') == 'yes':
            return 'Admission required'
        elif tags.get('charge'):
            return f"Fee: {tags['charge']}"
        elif tags.get('tourism') == 'museum':
            return 'Museum admission required'
        else:
            return 'Contact venue for pricing'
    
    def _get_real_rating_info(self, tags: Dict) -> str:
        """Get real rating info - no hardcoded ratings"""
        if tags.get('stars'):
            return f"{tags['stars']} stars"
        elif tags.get('rating'):
            return f"Rating: {tags['rating']}"
        else:
            return "Check online reviews for rating"
    
    def _format_address(self, tags: Dict, destination: str) -> str:
        """Format address from real OSM tags"""
        address_parts = []
        for key in ['addr:housenumber', 'addr:street', 'addr:city', 'addr:country']:
            if tags.get(key):
                address_parts.append(tags[key])
        
        if address_parts:
            return ', '.join(address_parts)
        else:
            return destination

# ===========================================
# UNIFIED LLM INTERFACE - COMPLETE
# ===========================================

class UnifiedLLM:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider.lower()
        
        if self.provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(api_key=api_key, model="gpt-3.5-turbo", temperature=0.7)
                self.use_langchain = True
                print("OpenAI initialized")
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
                        print(f"Gemini initialized with {model_name}")
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
        print("OpenAI available")
    except ImportError:
        print("OpenAI not available")
    
    try:
        import google.generativeai as genai
        providers["Gemini"] = "gemini"
        print("Gemini available")
    except ImportError:
        print("Gemini not available")
    
    return providers

# ===========================================
# ENHANCED TRAVEL ASSISTANT - COMPLETE
# ===========================================

class EnhancedTravelAssistant:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.llm = UnifiedLLM(provider, api_key)
        self.memory = ConversationBufferMemory()
        
        # Initialize enhanced PostgreSQL session management
        try:
            self.session_manager = EnhancedPostgreSQLManager()
            print("Enhanced PostgreSQL session management ready")
        except Exception as e:
            print(f"Enhanced PostgreSQL failed: {e}")
            self.session_manager = None
        
        # Add real places API
        self.places_api = RealPlacesAPI()
        print("Real Places API ready (OpenStreetMap)")
        
        # Build LangGraph workflow
        self.graph = self._build_conversational_graph()
        print("LangGraph workflow built successfully")
    
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

    # API METHODS - COMPLETE IMPLEMENTATION
    def call_aviationstack_api(self, origin: str, destination: str, api_key: str) -> List[Dict[str, Any]]:
        """Call AviationStack for REAL flight data with enhanced debugging"""
        try:
            url = "http://api.aviationstack.com/v1/flights"
            params = {
                "access_key": api_key,
                "dep_iata": origin,
                "arr_iata": destination,
                "limit": 6  # Request more flights
            }
            
            print(f"Calling AviationStack: {origin} → {destination}")
            print(f"Request params: {params}")
            
            response = requests.get(url, params=params, timeout=15)
            print(f"AviationStack response: {response.status_code}")
            
            if response.status_code != 200:
                print(f"AviationStack error: {response.text}")
                raise Exception(f"AviationStack HTTP error {response.status_code}")
            
            data = response.json()
            
            if "error" in data:
                raise Exception(f"AviationStack API error: {data['error']}")
            
            flights_data = data.get("data", [])
            print(f"Found {len(flights_data)} flights in API response")
            
            if not flights_data:
                raise Exception(f"No flights found for route {origin} → {destination}")
            
            flights = []
            for flight in flights_data[:6]:
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
                        "source": "AviationStack Real Data",
                        "note": "Contact airline for pricing"
                    }
                    
                    flights.append(processed_flight)
                    
                except Exception:
                    continue
            
            print(f"Successfully processed {len(flights)} flights")
            return flights
            
        except Exception as e:
            raise Exception(f"AviationStack API failed: {str(e)}")
    
    def call_booking_hotels_api(self, destination: str, checkin: str, checkout: str, api_key: str) -> List[Dict[str, Any]]:
        """Call Booking.com API with enhanced debugging and better error handling"""
        try:
            print(f"=== BOOKING.COM API DEBUG ===")
            print(f"Destination: {destination}")
            print(f"Check-in: {checkin}")
            print(f"Check-out: {checkout}")
            print(f"API Key (first 10 chars): {api_key[:10]}...")
            
            # Step 1: Get destination ID
            search_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
            }
            
            search_params = {"name": destination, "locale": "en-gb"}
            print(f"Step 1 - Location search URL: {search_url}")
            print(f"Step 1 - Search params: {search_params}")
            
            search_response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
            print(f"Step 1 - Response code: {search_response.status_code}")
            
            if search_response.status_code != 200:
                print(f"Step 1 - Error response: {search_response.text}")
                raise Exception(f"Location search failed: HTTP {search_response.status_code}")
            
            search_data = search_response.json()
            print(f"Step 1 - Found locations: {len(search_data) if search_data else 0}")
            
            if not search_data:
                raise Exception(f"No location found for {destination}")
            
            dest_id = search_data[0].get("dest_id")
            dest_type = search_data[0].get("dest_type", "city")
            print(f"Step 1 - Destination ID: {dest_id}, Type: {dest_type}")
            
            if not dest_id:
                raise Exception("Could not extract destination ID")
            
            # Step 2: Search hotels with proper parameters
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
                "dest_type": dest_type,
                "units": "metric",
                "page_number": "0"
            }
            
            print(f"Step 2 - Hotel search URL: {hotel_url}")
            print(f"Step 2 - Hotel params: {hotel_params}")
            
            hotel_response = requests.get(hotel_url, headers=headers, params=hotel_params, timeout=20)
            print(f"Step 2 - Response code: {hotel_response.status_code}")
            
            if hotel_response.status_code == 422:
                print(f"Step 2 - HTTP 422 Error Details: {hotel_response.text}")
                try:
                    error_details = hotel_response.json()
                    print(f"Step 2 - Detailed error: {error_details}")
                except:
                    pass
                raise Exception(f"Hotel search parameter validation failed - check dates: {checkin} to {checkout}")
            elif hotel_response.status_code != 200:
                print(f"Step 2 - Error response: {hotel_response.text}")
                raise Exception(f"Hotel search failed: HTTP {hotel_response.status_code}")
            
            hotel_data = hotel_response.json()
            hotels = hotel_data.get("result", [])
            print(f"Step 2 - Found hotels: {len(hotels) if hotels else 0}")
            
            if not hotels:
                print(f"Step 2 - No hotels in response. Full response keys: {list(hotel_data.keys()) if hotel_data else 'None'}")
                raise Exception("No hotels found in API response")
            
            # Format REAL hotel data
            formatted_hotels = []
            nights = self.calculate_nights(checkin, checkout)
            print(f"Calculating for {nights} nights")
            
            for i, hotel in enumerate(hotels[:4]):
                try:
                    hotel_name = hotel.get("hotel_name", "Hotel")
                    
                    # Get REAL pricing from API
                    price_info = hotel.get("min_total_price", 0)
                    total_price = float(price_info) if price_info else 0
                    per_night = total_price / nights if nights > 0 and total_price > 0 else total_price
                    
                    # Get REAL review data from API
                    review_score = hotel.get("review_score", 0)
                    review_count = hotel.get("review_nr", 0)
                    
                    formatted_hotel = {
                        "name": hotel_name,
                        "price_per_night": round(per_night, 2) if per_night > 0 else "Check with hotel",
                        "total_price": round(total_price, 2) if total_price > 0 else "Check with hotel",
                        "location": hotel.get("district", "City center"),
                        "rating": f"{review_score}/10" if review_score > 0 else "No rating available",
                        "review_count": review_count,
                        "source": "Booking.com Real Data"
                    }
                    
                    formatted_hotels.append(formatted_hotel)
                    print(f"Processed hotel {i+1}: {hotel_name}")
                    
                except Exception as hotel_error:
                    print(f"Error processing hotel {i}: {hotel_error}")
                    continue
            
            print(f"Successfully processed {len(formatted_hotels)} hotels")
            return formatted_hotels
            
        except Exception as e:
            print(f"Booking.com API failed: {str(e)}")
            raise Exception(f"Booking.com API failed: {str(e)}")
    
    def call_google_places_api(self, destination: str, interests: List[str]) -> List[Dict[str, Any]]:
        """Use REAL Places API"""
        try:
            print(f"Using REAL Places API for {destination}...")
            return self.places_api.get_attractions_real(destination, interests)
        except Exception as e:
            print(f"Real Places API failed: {e}")
            return []
    
    def get_airport_code(self, city: str) -> str:
        """Convert city to airport code"""
        codes = {
            "boston": "BOS", "new york": "JFK", "chicago": "ORD", "dallas": "DFW",
            "miami": "MIA", "paris": "CDG", "london": "LHR", "rome": "FCO", "tokyo": "NRT"
        }
        city_clean = city.lower().split(',')[0].strip()
        return codes.get(city_clean, city[:3].upper())
    
    def calculate_nights(self, checkin: str, checkout: str) -> int:
        """Calculate nights"""
        try:
            checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
            checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
            return (checkout_date - checkin_date).days
        except:
            return 7
    
    def get_future_dates(self, duration_days: int, user_dates: Dict = None) -> tuple:
        """Get future dates - handles both user-specified dates and API-safe defaults"""
        try:
            if user_dates:
                # Try to use user-specified dates if provided
                start_date = user_dates.get("start_date")
                end_date = user_dates.get("end_date") 
                
                if start_date and end_date:
                    # Parse user dates and validate they're in the future
                    try:
                        checkin_date = datetime.strptime(start_date, "%Y-%m-%d")
                        checkout_date = datetime.strptime(end_date, "%Y-%m-%d")
                        
                        if checkin_date > datetime.now():
                            return start_date, end_date
                    except:
                        pass
            
            # Default: Use API-safe dates (14 days from now to avoid validation issues)
            checkin = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            checkout = (datetime.now() + timedelta(days=14 + duration_days)).strftime("%Y-%m-%d")
            print(f"Using API-safe dates: {checkin} to {checkout}")
            return checkin, checkout
            
        except Exception as e:
            print(f"Date calculation error: {e}")
            # Fallback to safe dates
            checkin = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            checkout = (datetime.now() + timedelta(days=14 + duration_days)).strftime("%Y-%m-%d")
            return checkin, checkout

    # ALL NODE METHODS - COMPLETE WITH PROPER VALIDATION
    def _extract_info(self, state: RealAPITravelState) -> RealAPITravelState:
        """Extract trip details using AI with proper validation - RESTORED from original"""
        user_input = state["user_input"]
        
        try:
            print(f"AI extracting info from: {user_input}")
            
            extraction_prompt = f"Extract from: '{user_input}'\n\nFormat:\nOrigin: [city]\nDestination: [city]\nDuration: [days]\nBudget: [amount]\nInterests: [list]\nStart_Date: [date if mentioned]\nEnd_Date: [date if mentioned]"
            
            messages = [SystemMessage("Extract travel info."), HumanMessage(extraction_prompt)]
            extraction = self.llm.invoke(messages)
            extracted_text = extraction.content
            
            print(f"AI extraction result: {extracted_text}")
            
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
                        interests = [i.strip() for i in value.split(',') if i.strip()]
                        if interests:
                            state["interests"] = interests
                    elif key in ["start_date", "end_date"] and value and value != "[date]":
                        # Store dates for future use
                        if 'travel_dates' not in state:
                            state['travel_dates'] = {}
                        state['travel_dates'][key] = value
            
            print(f"Extracted: origin={state.get('origin')}, dest={state.get('destination')}, days={state.get('duration_days')}, budget={state.get('budget')}")
            
            # CRITICAL: Validate required information like your original
            missing_info = []
            
            if not state.get("origin"):
                missing_info.append("departure city")
            if not state.get("destination"):
                missing_info.append("destination")
            if not state.get("duration_days") or state.get("duration_days") < 1:
                missing_info.append("trip duration (number of days)")
            
            # Check for optional but important info
            optional_missing = []
            if not state.get("budget"):
                optional_missing.append("budget")
            if not state.get("interests"):
                optional_missing.append("travel interests")
            
            # Handle missing REQUIRED information first
            if missing_info:
                if len(missing_info) == 1:
                    state["response"] = f"I need to know your {missing_info[0]} to help plan your trip. Could you please provide that information?"
                else:
                    info_list = ", ".join(missing_info[:-1]) + f" and {missing_info[-1]}"
                    state["response"] = f"To plan your perfect trip, I need a few more details: {info_list}. Could you please provide this information?"
                
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                print(f"Missing required info: {missing_info}")
                return state
            
            # Handle missing OPTIONAL information
            elif optional_missing:
                state["response"] = f"Great! I have {state['origin']} to {state['destination']} for {state['duration_days']} days. To personalize your trip, could you also tell me your {' and '.join(optional_missing)}?"
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                print(f"Missing optional info: {optional_missing}")
                return state
            
            # Set defaults only if everything is provided
            if not state.get("budget"):
                state["budget"] = "flexible"
            if not state.get("interests"):
                state["interests"] = ["cultural", "sightseeing"]
            
            # Validate destination is different from origin
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
        print("All info validated - proceeding to flight search")
        return state
    
    def _handle_missing_info(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle missing information using AI - RESTORED from original"""
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
                        interests = [i.strip() for i in value.split(',') if i.strip()]
                        if interests:
                            state["interests"] = interests
            
            # Check if we still have missing required information
            missing_info = []
            if not state.get("origin"): missing_info.append("departure city")
            if not state.get("destination"): missing_info.append("destination city")
            if not state.get("duration_days"): missing_info.append("trip duration")
                
            if missing_info:
                state["response"] = f"I still need: {', '.join(missing_info)}. Could you provide these details?"
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                return state
                
            # Set defaults for optional fields
            if not state.get("budget"): state["budget"] = "flexible"
            if not state.get("interests"): state["interests"] = ["cultural", "sightseeing"]
                
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
        """Search REAL flights"""
        print(f"Searching REAL flights: {state['origin']} → {state['destination']}")
        
        try:
            api_key = os.getenv("FLIGHT_API_KEY")
            if not api_key:
                state["response"] = "Flight API not configured. Proceeding to hotels."
                state["current_step"] = "need_hotels"
                state["awaiting_user_choice"] = False
                return state
            
            origin_code = self.get_airport_code(state["origin"])
            dest_code = self.get_airport_code(state["destination"])
            
            flight_options = self.call_aviationstack_api(origin_code, dest_code, api_key)
            state["flight_options"] = flight_options
            
            response = f"Here are REAL flights from AviationStack ({origin_code} → {dest_code}):\n\n"
            
            for i, flight in enumerate(flight_options, 1):
                dep_time = flight['departure']
                if 'T' in dep_time:
                    dep_time = dep_time.split('T')[1][:5]
                
                response += f"**Option {i}: {flight['airline']}**\n"
                response += f"Flight {flight['flight_number']}\n"
                response += f"Departs: {dep_time}\n"
                response += f"{flight['note']}\n\n"
            
            response += "Which flight option would you prefer? (Type the option number)"
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_flight_choice"
            
        except Exception as e:
            print(f"Flight search error: {e}")
            state["response"] = f"Flight search failed: {str(e)}. Proceeding to hotels."
            state["current_step"] = "need_hotels"
            state["awaiting_user_choice"] = False
        
        return state
    
    def _search_hotels(self, state: RealAPITravelState) -> RealAPITravelState:
        """Search REAL hotels with improved date handling"""
        print(f"Searching REAL hotels in {state['destination']}")
        
        try:
            api_key = os.getenv("RAPIDAPI_KEY")
            if not api_key:
                state["response"] = "Hotel API not configured. Proceeding to attractions."
                state["current_step"] = "need_attractions"
                state["awaiting_user_choice"] = False
                return state
            
            # Use improved date handling
            user_dates = state.get('travel_dates', {})
            checkin, checkout = self.get_future_dates(state["duration_days"], user_dates)
            
            print(f"Using dates for hotel search: {checkin} to {checkout}")
            
            hotel_options = self.call_booking_hotels_api(state["destination"], checkin, checkout, api_key)
            state["hotel_options"] = hotel_options
            
            response = f"Great! Here are REAL hotels from Booking.com for {checkin} to {checkout}:\n\n"
            
            for i, hotel in enumerate(hotel_options, 1):
                price_text = f"${hotel['price_per_night']}/night" if hotel['price_per_night'] != "Check with hotel" else hotel['price_per_night']
                
                response += f"**Option {i}: {hotel['name']}**\n"
                response += f"{price_text}\n"
                response += f"Location: {hotel['location']}\n"
                response += f"Rating: {hotel['rating']}"
                if hotel['review_count'] > 0:
                    response += f" ({hotel['review_count']} reviews)"
                response += "\n\n"
            
            response += "Which hotel would you prefer? (Type the option number)"
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_hotel_choice"
            
        except Exception as e:
            print(f"Hotel search error: {e}")
            # More detailed error handling for debugging
            if "422" in str(e):
                state["response"] = f"Hotel search failed due to date validation issues. Using general hotel recommendations for {state['destination']}."
            else:
                state["response"] = f"Hotel search failed: {str(e)}. Proceeding to attractions."
            state["current_step"] = "need_attractions"
            state["awaiting_user_choice"] = False
        
        return state
    
    def _search_attractions(self, state: RealAPITravelState) -> RealAPITravelState:
        """Search REAL attractions"""
        print(f"Searching REAL attractions in {state['destination']}")
        
        try:
            attractions = self.call_google_places_api(state["destination"], state.get("interests", []))
            state["attractions_data"] = attractions
            
            if attractions:
                response = f"Found {len(attractions)} REAL attractions from OpenStreetMap API:\n\n"
                
                for attraction in attractions[:5]:
                    response += f"• {attraction['name']}\n"
                    response += f"  Type: {', '.join(attraction.get('types', ['Attraction']))}\n"
                    response += f"  {attraction.get('rating', 'Check online for rating')}\n"
                    response += f"  {attraction.get('price_level', 'Check locally for pricing')}\n\n"
                
                response += "Ready to create your itinerary! What travel style do you prefer?\n\n"
                response += "1. **Cultural** - Museums, history, local culture\n"
                response += "2. **Adventure** - Exciting experiences\n"
                response += "3. **Leisure** - Relaxation and comfort\n"
                response += "4. **Business** - Efficient travel\n\n"
                response += "Type the number of your preferred style."
            else:
                response = "I can still create an itinerary for your destination. What travel style do you prefer? (Cultural, Adventure, Leisure, or Business)"
            
            state["response"] = response
            state["awaiting_user_choice"] = True
            state["current_step"] = "awaiting_style_decision"
            
        except Exception as e:
            print(f"Attractions search error: {e}")
            state["response"] = f"Attractions search had issues: {str(e)}. I can still create an itinerary. What style do you prefer?"
            state["current_step"] = "awaiting_style_decision"
            state["awaiting_user_choice"] = True
        
        return state
    
    def _handle_style_decision(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle style decision using AI"""
        user_input = state["user_input"].lower()
        
        print(f"Processing style decision: {user_input}")
        
        if any(word in user_input for word in ["1", "cultural", "culture", "museum", "history"]):
            state["selected_trip_style"] = "cultural"
        elif any(word in user_input for word in ["2", "adventure", "exciting", "thrilling"]):
            state["selected_trip_style"] = "adventure"
        elif any(word in user_input for word in ["3", "leisure", "relax", "comfort"]):
            state["selected_trip_style"] = "leisure"
        elif any(word in user_input for word in ["4", "business", "work", "efficient"]):
            state["selected_trip_style"] = "business"
        else:
            state["selected_trip_style"] = "cultural"  # Default
        
        state["current_step"] = "skip_to_itinerary"
        state["response"] = f"Perfect! Creating your {state['selected_trip_style']} itinerary using REAL data from the APIs..."
        state["awaiting_user_choice"] = False
        
        print(f"Selected style: {state['selected_trip_style']}")
        
        return state
    
    def _choose_style(self, state: RealAPITravelState) -> RealAPITravelState:
        """Show style options"""
        response = f"Choose your {state['destination']} travel style:\n\n"
        response += "1. **Cultural** - Museums, history, local experiences\n"
        response += "2. **Adventure** - Exciting and thrilling experiences\n" 
        response += "3. **Leisure** - Relaxation and comfort\n"
        response += "4. **Business** - Efficient and productive travel\n\n"
        response += "Type the number of your preferred style."
        
        state["response"] = response
        state["awaiting_user_choice"] = True
        state["current_step"] = "awaiting_style_choice"
        
        return state
    
    def _create_itinerary(self, state: RealAPITravelState) -> RealAPITravelState:
        """Create final itinerary using REAL data"""
        try:
            selected_flight = state.get("selected_flight", {})
            selected_hotel = state.get("selected_hotel", {})
            attractions = state.get("attractions_data", [])
            trip_style = state.get("selected_trip_style", "cultural")
            
            print(f"Creating itinerary with real data - {len(attractions)} attractions")
            
            attractions_text = ""
            if attractions:
                attractions_text = "\n".join([
                    f"• {a['name']} - {a.get('types', ['Attraction'])[0]}"
                    for a in attractions[:8]
                ])
            
            prompt = f"""Create a detailed {state['duration_days']}-day {trip_style} itinerary for {state['destination']} using this REAL data:
            
            Flight: {selected_flight.get('airline', 'Flight selected')} {selected_flight.get('flight_number', '')}
            Hotel: {selected_hotel.get('name', 'Hotel selected')} in {selected_hotel.get('location', 'city center')}
            Budget: {state.get('budget', 'flexible')}
            
            Real attractions from OpenStreetMap API:
            {attractions_text}
            
            Create practical day-by-day plans incorporating these actual places."""
            
            messages = [SystemMessage("Create detailed itinerary using real data."), HumanMessage(prompt)]
            itinerary_response = self.llm.invoke(messages)
            
            response = f"Your complete {state['destination']} {trip_style} itinerary:\n\n"
            
            if selected_flight.get('airline'):
                response += f"Flight: {selected_flight['airline']} {selected_flight.get('flight_number', '')}\n"
            
            if selected_hotel.get('name'):
                response += f"Hotel: {selected_hotel['name']}"
                if selected_hotel.get('price_per_night') != "Check with hotel":
                    response += f" - ${selected_hotel['price_per_night']}/night"
                response += "\n"
            
            response += f"Style: {trip_style.title()}\n"
            response += f"Budget: {state.get('budget', 'Flexible')}\n\n"
            response += f"**Your Detailed Itinerary:**\n\n"
            response += itinerary_response.content
            
            response += f"\n\n**Based on REAL data from AviationStack, Booking.com, and OpenStreetMap APIs!**"
            
            state["response"] = response
            state["current_step"] = "complete"
            
            print("Itinerary creation completed")
            
        except Exception as e:
            print(f"Itinerary creation error: {e}")
            state["response"] = f"Error creating itinerary: {str(e)}"
        
        return state
    
    def _handle_choice(self, state: RealAPITravelState) -> RealAPITravelState:
        """Handle user choices using AI"""
        user_input = state["user_input"]
        current_step = state.get("current_step", "")
        
        print(f"Handling choice: {user_input} for step: {current_step}")
        
        try:
            if "awaiting_flight_choice" in current_step:
                flight_options = state.get("flight_options", [])
                airlines = [f["airline"] for f in flight_options]
                
                choice_prompt = f"User said: '{user_input}'\nFlight options: {airlines}\nWhich option number (1-{len(airlines)}) did they choose? Return only the number."
                messages = [SystemMessage("Determine flight choice."), HumanMessage(choice_prompt)]
                choice_response = self.llm.invoke(messages)
                
                try:
                    choice_number = int(choice_response.content.strip())
                    choice_index = choice_number - 1
                    if 0 <= choice_index < len(flight_options):
                        state["selected_flight"] = flight_options[choice_index]
                        airline = flight_options[choice_index].get('airline', 'Selected flight')
                        state["response"] = f"Great choice! Selected {airline}. Now searching for REAL hotels..."
                    else:
                        state["selected_flight"] = flight_options[0]
                        state["response"] = "Selected first flight option. Now searching for REAL hotels..."
                except:
                    state["selected_flight"] = flight_options[0] if flight_options else {}
                    state["response"] = "Selected first flight option. Now searching for REAL hotels..."
                
                state["current_step"] = "need_hotels"
                state["awaiting_user_choice"] = False
                
            elif "awaiting_hotel_choice" in current_step:
                hotel_options = state.get("hotel_options", [])
                hotel_names = [h["name"] for h in hotel_options]
                
                choice_prompt = f"User said: '{user_input}'\nHotel options: {hotel_names}\nWhich option number (1-{len(hotel_names)}) did they choose? Return only the number."
                messages = [SystemMessage("Determine hotel choice."), HumanMessage(choice_prompt)]
                choice_response = self.llm.invoke(messages)
                
                try:
                    choice_number = int(choice_response.content.strip())
                    choice_index = choice_number - 1
                    if 0 <= choice_index < len(hotel_options):
                        state["selected_hotel"] = hotel_options[choice_index]
                        hotel_name = hotel_options[choice_index].get('name', 'Selected hotel')
                        state["response"] = f"Excellent choice! Selected {hotel_name}. Now finding REAL attractions..."
                    else:
                        state["selected_hotel"] = hotel_options[0]
                        state["response"] = "Selected first hotel option. Now finding REAL attractions..."
                except:
                    state["selected_hotel"] = hotel_options[0] if hotel_options else {}
                    state["response"] = "Selected first hotel option. Now finding REAL attractions..."
                
                state["current_step"] = "need_attractions"
                state["awaiting_user_choice"] = False
            
        except Exception as e:
            print(f"Choice handling error: {e}")
            state["response"] = f"I had trouble understanding your choice: {str(e)}"
        
        return state
    
    def _check_info_complete(self, state: RealAPITravelState) -> Literal["complete", "missing", "error"]:
        """Check if info is complete"""
        if state.get("api_errors"):
            return "error"
        elif state.get("awaiting_user_choice") and state.get("current_step") == "awaiting_missing_info":
            return "missing"
        elif state.get("origin") and state.get("destination") and state.get("duration_days"):
            return "complete"
        else:
            return "missing"
    
    def _should_wait(self, state: RealAPITravelState) -> Literal["wait", "error", "continue"]:
        """Check if should wait"""
        if state.get("api_errors"):
            return "error"
        elif state.get("awaiting_user_choice"):
            return "wait"
        else:
            return "continue"
    
    def _route_after_style_decision(self, state: RealAPITravelState) -> Literal["choose_style", "skip_to_itinerary"]:
        """Route after style decision"""
        if state.get("current_step") == "need_style_choice":
            return "choose_style"
        else:
            return "skip_to_itinerary"

    # ENHANCED SESSION MANAGEMENT
    def chat_with_persistence(self, user_input: str, session_id: str = None, user_id: str = "anonymous") -> Dict[str, Any]:
        """Enhanced chat with session persistence and conversation history tracking"""
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            print(f"Processing message: '{user_input}' for session {session_id[:8]}")
            
            # Load existing session or create new
            current_state = None
            if self.session_manager:
                current_state = self.session_manager.load_session(session_id)
            
            if current_state:
                print(f"Loaded existing session {session_id[:8]} - step: {current_state.get('current_step')}")
                current_state["user_input"] = user_input
                
                # Add user message to conversation history
                if "conversation_history" not in current_state:
                    current_state["conversation_history"] = []
                current_state["conversation_history"].append({
                    "role": "user", 
                    "content": user_input,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                print(f"Creating new session {session_id[:8]}")
                current_state = {
                    "user_input": user_input,
                    "conversation_history": [{
                        "role": "user", 
                        "content": user_input,
                        "timestamp": datetime.now().isoformat()
                    }],
                    "current_step": "initial",
                    "awaiting_user_choice": False,
                    "origin": "", "destination": "", "duration_days": 0, "budget": "",
                    "interests": [], "selected_flight": {}, "selected_hotel": {},
                    "selected_trip_style": "", "flight_options": [], "hotel_options": [],
                    "attractions_data": [], "response": "", "api_errors": []
                }
            
            # Use the main chat method
            result = self.chat(user_input, current_state)
            
            # Add assistant response to conversation history
            if result.get("response"):
                if "conversation_history" not in result:
                    result["conversation_history"] = current_state.get("conversation_history", [])
                result["conversation_history"].append({
                    "role": "assistant", 
                    "content": result["response"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Ensure result has a response
            if not result.get("response"):
                result["response"] = "I'm analyzing your travel request. Could you provide more details?"
                print("Warning: Empty response generated, using fallback")
            
            # Save to PostgreSQL with conversation history
            result["session_id"] = session_id
            if self.session_manager:
                saved = self.session_manager.save_session(session_id, result)
                if saved:
                    print(f"Session {session_id[:8]} with conversation history saved to PostgreSQL")
            
            print(f"Generated response: {result.get('response', 'NO RESPONSE')[:100]}...")
            
            return result
            
        except Exception as e:
            print(f"Chat processing error: {e}")
            import traceback
            traceback.print_exc()
            
            error_result = {
                "user_input": user_input,
                "conversation_history": [{
                    "role": "user", 
                    "content": user_input,
                    "timestamp": datetime.now().isoformat()
                }, {
                    "role": "assistant", 
                    "content": f"I encountered a system error: {str(e)}. Please try rephrasing your request.",
                    "timestamp": datetime.now().isoformat()
                }],
                "response": f"I encountered a system error: {str(e)}. Please try rephrasing your request.",
                "session_id": session_id,
                "current_step": "error",
                "awaiting_user_choice": False,
                "origin": "", "destination": "", "duration_days": 0, "budget": "",
                "interests": [], "selected_flight": {}, "selected_hotel": {},
                "selected_trip_style": "", "flight_options": [], "hotel_options": [],
                "attractions_data": [], "api_errors": [str(e)]
            }
            return error_result

    def chat(self, user_input: str, current_state: RealAPITravelState = None) -> RealAPITravelState:
        """Main chat interface with proper conversation history tracking"""
        
        if current_state is None:
            print("Initial planning - invoking LangGraph workflow")
            # Initial planning - invoke LangGraph workflow
            current_state = {
                "user_input": user_input, 
                "conversation_history": [
                    {"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()}
                ],
                "current_step": "initial", "awaiting_user_choice": False,
                "origin": "", "destination": "", "duration_days": 0, "budget": "",
                "interests": [], "selected_flight": {}, "selected_hotel": {},
                "selected_trip_style": "", "flight_options": [], "hotel_options": [],
                "attractions_data": [], "response": "", "api_errors": []
            }
            
            result = self.graph.invoke(current_state)
            
            # Add assistant response to conversation history
            if result.get("response"):
                if "conversation_history" not in result:
                    result["conversation_history"] = current_state["conversation_history"]
                result["conversation_history"].append({
                    "role": "assistant", 
                    "content": result["response"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Add AI response to memory
            self.memory.chat_memory.add_ai_message(result.get("response", ""))
            
            return result
            
        else:
            print(f"Continuing conversation - step: {current_state.get('current_step')}, awaiting_choice: {current_state.get('awaiting_user_choice')}")
            
            # Add user message to conversation history
            current_state["user_input"] = user_input
            if "conversation_history" not in current_state:
                current_state["conversation_history"] = []
            current_state["conversation_history"].append({
                "role": "user", 
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            })
            
            # Handle user input based on current step
            result = None
            
            if current_state.get("current_step") == "awaiting_missing_info":
                print("Processing missing info")
                result = self._handle_missing_info(current_state)
                
                if result.get("current_step") == "info_complete":
                    print("Info complete, proceeding to flight search")
                    result = self._search_flights(result)
                
            elif current_state.get("current_step") == "awaiting_style_decision":
                print("Processing style decision")
                result = self._handle_style_decision(current_state)
                
                if result.get("current_step") == "skip_to_itinerary":
                    result = self._create_itinerary(result)
                
            elif current_state.get("awaiting_user_choice"):
                print(f"Processing user choice for step: {current_state.get('current_step')}")
                choice_state = self._handle_choice(current_state)
                
                if choice_state["current_step"] == "need_hotels":
                    result = self._search_hotels(choice_state)
                elif choice_state["current_step"] == "need_attractions":
                    result = self._search_attractions(choice_state)
                elif choice_state["current_step"] == "need_itinerary":
                    result = self._create_itinerary(choice_state)
                else:
                    result = choice_state
            else:
                print("No matching step handler - returning current state")
                result = current_state
            
            # Add assistant response to conversation history
            if result and result.get("response"):
                if "conversation_history" not in result:
                    result["conversation_history"] = current_state["conversation_history"]
                result["conversation_history"].append({
                    "role": "assistant", 
                    "content": result["response"],
                    "timestamp": datetime.now().isoformat()
                })
                
                # Add AI response to memory
                self.memory.chat_memory.add_ai_message(result.get("response", ""))
            
            return result or current_state
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session info"""
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
        """List sessions"""
        if not self.session_manager:
            return []
        return self.session_manager.list_sessions(limit)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        if not self.session_manager:
            return False
        try:
            conn = psycopg2.connect(**self.session_manager.connection_config)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM enhanced_travel_sessions WHERE session_id = %s', (session_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except:
            return False

# Backwards compatibility
RealAPITravelAssistant = EnhancedTravelAssistant

# ===========================================
# MAIN EXECUTION
# ===========================================

if __name__ == "__main__":
    print("Enhanced Travel Assistant Setup & Status:")
    print("=" * 50)
    
    # Check API status
    print(f"AviationStack: {'Configured' if os.getenv('FLIGHT_API_KEY') else 'Not configured'}")
    print(f"RapidAPI: {'Configured' if os.getenv('RAPIDAPI_KEY') else 'Not configured'}")
    print(f"Places API: FREE OpenStreetMap")
    print(f"PostgreSQL: Enhanced session management")
    
    available_providers = detect_available_providers()
    if not available_providers:
        print("No AI providers available")
        exit(1)
    
    # Auto-initialize if keys available
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    provider = None
    api_key = None
    
    if openai_key and "OpenAI" in available_providers:
        provider = "openai"
        api_key = openai_key
        print("Auto-detected OpenAI API key")
    elif gemini_key and "Gemini" in available_providers:
        provider = "gemini" 
        api_key = gemini_key
        print("Auto-detected Gemini API key")
    else:
        print("No API keys found in environment")
        exit(1)
    
    try:
        # Initialize Enhanced Atlas AI
        atlas_ai = EnhancedTravelAssistant(provider, api_key)
        print(f"\nEnhanced Atlas AI Ready! (AI: {provider.title()})")
        print("=" * 50)
        print("Real APIs: AviationStack + Booking.com + OpenStreetMap")
        print("Enhanced PostgreSQL Session Management: Enabled")
        print("LangGraph Workflow: Active")
        print("\nTell me about your trip!\n")
        
        # Start conversation
        session_id = str(uuid.uuid4())
        print(f"Session ID: {session_id[:8]}...")
        print("Your conversation will be saved to PostgreSQL!")
        print("-" * 50)
        
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print(f"\nGoodbye! Your session {session_id[:8]}... has been saved.")
                break
            
            if user_input.strip():
                try:
                    result = atlas_ai.chat_with_persistence(user_input, session_id)
                    print(f"\nAtlas AI: {result['response']}")
                    
                    if result.get("awaiting_user_choice"):
                        print(f"\nStatus: {result['current_step']} - Waiting for your choice...")
                    
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"\nError: {str(e)}")
                    print("Please try again or type 'quit' to exit.")
    
    except Exception as e:
        print(f"\nSystem Error: {str(e)}")
        print("Please check your API keys and try again.")