import os
from typing import TypedDict, List, Dict, Any, Literal
import requests
import json
from datetime import datetime, timedelta
import re

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

# Unified LLM Interface
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
    """Interactive setup"""
    print("🌍 Travel Planning System Setup")
    print("=" * 40)
    
    available_providers = detect_available_providers()
    if not available_providers:
        return None, None
    
    if len(available_providers) == 1:
        provider_name = list(available_providers.keys())[0]
        provider_key = available_providers[provider_name]
        print(f"Using {provider_name}")
    else:
        print("\nChoose AI Provider:")
        for i, name in enumerate(available_providers.keys(), 1):
            print(f"{i}. {name}")
        
        while True:
            try:
                choice = int(input("\nEnter choice: "))
                provider_name = list(available_providers.keys())[choice - 1]
                provider_key = available_providers[provider_name]
                break
            except (ValueError, IndexError):
                print("Invalid choice")
    
    if provider_key == "openai":
        env_key = os.getenv("OPENAI_API_KEY")
    else:
        env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if env_key:
        print(f"Found {provider_name} API key")
        api_key = env_key
    else:
        api_key = input(f"Enter {provider_name} API key: ").strip()
        if not api_key:
            return None, None
    
    return provider_key, api_key

# Real API Travel Assistant
class RealAPITravelAssistant:
    def __init__(self, provider: str, api_key: str):
        self.llm = UnifiedLLM(provider, api_key)
        self.memory = ConversationBufferMemory()
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
            print(f"API URL: {url}")
            print(f"Params: {params}")
            
            response = requests.get(url, params=params, timeout=15)
            
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                raise Exception("AviationStack 401: Invalid API key")
            elif response.status_code == 403:
                raise Exception("AviationStack 403: Access denied - check API key or quota exceeded")
            elif response.status_code == 404:
                raise Exception("AviationStack 404: Endpoint not found")
            elif response.status_code != 200:
                raise Exception(f"AviationStack HTTP error {response.status_code}: {response.text}")
            
            # Check if response has content
            if not response.content:
                raise Exception("AviationStack returned empty response")
            
            print(f"Raw response content: {response.text[:500]}...")
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise Exception(f"AviationStack returned invalid JSON: {str(e)}")
            
            # Check if data is None
            if data is None:
                raise Exception("AviationStack returned null data")
            
            # Check for API errors in response
            if "error" in data:
                error_info = data["error"]
                if isinstance(error_info, dict):
                    error_msg = error_info.get("message", "Unknown API error")
                    error_code = error_info.get("code", "Unknown code")
                    raise Exception(f"AviationStack API error {error_code}: {error_msg}")
                else:
                    raise Exception(f"AviationStack API error: {error_info}")
            
            # Get flights data safely
            flights_data = data.get("data", []) if isinstance(data, dict) else []
            
            if not flights_data:
                # Check if there's pagination info
                pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
                total = pagination.get("total", 0)
                
                if total == 0:
                    raise Exception(f"No flights found for route {origin} → {destination}")
                else:
                    raise Exception("No flight data in current page")
            
            print(f"Found {len(flights_data)} flights")
            
            # Process flight data safely
            flights = []
            for i, flight in enumerate(flights_data[:4]):
                try:
                    if not isinstance(flight, dict):
                        print(f"Skipping flight {i}: not a dictionary")
                        continue
                    
                    airline_info = flight.get("airline", {}) or {}
                    flight_info = flight.get("flight", {}) or {}
                    departure_info = flight.get("departure", {}) or {}
                    arrival_info = flight.get("arrival", {}) or {}
                    aircraft_info = flight.get("aircraft", {}) or {}
                    
                    processed_flight = {
                        "airline": airline_info.get("name", "Unknown Airline"),
                        "flight_number": flight_info.get("number", "N/A"),
                        "departure": departure_info.get("scheduled", "N/A"),
                        "arrival": arrival_info.get("scheduled", "N/A"),
                        "aircraft": aircraft_info.get("registration", "N/A"),
                        "source": "AviationStack",
                        "note": "Contact airline for pricing"
                    }
                    
                    flights.append(processed_flight)
                    print(f"Processed flight {i+1}: {processed_flight['airline']} {processed_flight['flight_number']}")
                    
                except Exception as flight_error:
                    print(f"Error processing flight {i}: {flight_error}")
                    continue
            
            if not flights:
                raise Exception("Could not process any flight data from response")
            
            return flights
            
        except requests.exceptions.Timeout:
            raise Exception("AviationStack API timeout - please try again")
        except requests.exceptions.ConnectionError:
            raise Exception("Could not connect to AviationStack API - check internet connection")
        except requests.exceptions.RequestException as e:
            raise Exception(f"AviationStack request failed: {str(e)}")
        except Exception as e:
            # Re-raise our custom exceptions
            if "AviationStack" in str(e):
                raise e
            else:
                raise Exception(f"AviationStack API failed: {str(e)}")
    
    def call_booking_hotels_api(self, destination: str, checkin: str, checkout: str, api_key: str) -> List[Dict[str, Any]]:
        """Call Booking.com API with proper error handling and date management"""
        try:
            # Step 1: Get destination ID
            search_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
            }
            
            search_params = {"name": destination, "locale": "en-gb"}
            print(f"Getting destination ID for {destination}...")
            
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
            
            print(f"Destination ID: {dest_id}")
            
            # Step 2: Search hotels with all required parameters
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
            
            print(f"Searching hotels for {checkin} to {checkout}...")
            hotel_response = requests.get(hotel_url, headers=headers, params=hotel_params, timeout=20)
            
            if hotel_response.status_code == 401:
                raise Exception("Hotel search authentication failed")
            elif hotel_response.status_code == 403:
                raise Exception("Hotel search forbidden - subscription required")
            elif hotel_response.status_code == 422:
                error_data = hotel_response.json()
                error_msgs = [detail.get("msg", "Unknown error") for detail in error_data.get("detail", [])]
                raise Exception(f"Invalid parameters: {', '.join(error_msgs)}")
            elif hotel_response.status_code != 200:
                raise Exception(f"Hotel search failed: HTTP {hotel_response.status_code}")
            
            try:
                hotel_data = hotel_response.json()
            except:
                raise Exception("Invalid JSON response from hotel search")
            
            # Handle response structure
            hotels = hotel_data.get("result", [])
            if not hotels:
                raise Exception("No hotels found in the response")
            
            # Format hotel data
            formatted_hotels = []
            nights = self.calculate_nights(checkin, checkout)
            
            for hotel in hotels[:4]:
                try:
                    hotel_name = hotel.get("hotel_name", "Hotel Name Not Available")
                    
                    # Handle different price structures
                    price_info = hotel.get("min_total_price", hotel.get("composite_price_breakdown", {}))
                    if isinstance(price_info, dict):
                        total_price = price_info.get("gross_amount_per_night", {}).get("value", 150)
                    else:
                        total_price = float(price_info) if price_info else 150
                    
                    per_night = total_price / nights if nights > 0 else total_price
                    
                    location = hotel.get("district", hotel.get("city", "City center"))
                    rating = hotel.get("review_score", "N/A")
                    rating_display = f"{rating}⭐" if rating != "N/A" else "No rating"
                    
                    formatted_hotels.append({
                        "name": hotel_name,
                        "price_per_night": int(per_night),
                        "total_price": int(total_price),
                        "location": location,
                        "rating": rating_display,
                        "amenities": hotel.get("hotel_facilities", "Standard amenities"),
                        "source": "Booking.com",
                        "booking_url": hotel.get("url", ""),
                        "raw_data": hotel
                    })
                    
                except Exception as parse_error:
                    print(f"Error parsing hotel: {parse_error}")
                    continue
            
            if not formatted_hotels:
                raise Exception("Could not parse any hotel data from response")
            
            return formatted_hotels
            
        except Exception as e:
            raise Exception(f"Booking.com API failed: {str(e)}")
    
    def call_google_places_api(self, destination: str, interests: List[str]) -> List[Dict[str, Any]]:
        """Call Google Places API"""
        try:
            google_key = os.getenv("GOOGLE_PLACES_API_KEY")
            if not google_key:
                raise Exception("GOOGLE_PLACES_API_KEY not configured")
            
            print(f"Calling Google Places for {destination}...")
            
            attractions = []
            search_terms = interests if interests else ["tourist attraction"]
            
            for term in search_terms[:2]:
                url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                params = {
                    "query": f"{term} {destination}",
                    "key": google_key,
                    "type": "tourist_attraction"
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    print(f"Google Places error for {term}: {response.status_code}")
                    continue
                    
                data = response.json()
                results = data.get("results", [])
                
                for place in results[:5]:
                    attractions.append({
                        "name": place["name"],
                        "rating": place.get("rating", "N/A"),
                        "address": place.get("formatted_address", ""),
                        "types": place.get("types", []),
                        "price_level": self.get_price_description(place.get("price_level")),
                        "source": "Google Places"
                    })
            
            # Remove duplicates
            unique_attractions = []
            seen_names = set()
            for attraction in attractions:
                if attraction["name"] not in seen_names:
                    unique_attractions.append(attraction)
                    seen_names.add(attraction["name"])
            
            return unique_attractions[:8]
            
        except Exception as e:
            raise Exception(f"Google Places failed: {str(e)}")
    
    def get_airport_code(self, city: str) -> str:
        """Convert city to airport code"""
        codes = {
            "boston": "BOS", "new york": "JFK", "los angeles": "LAX",
            "chicago": "ORD", "miami": "MIA", "san francisco": "SFO",
            "paris": "CDG", "london": "LHR", "rome": "FCO",
            "tokyo": "NRT", "barcelona": "BCN", "amsterdam": "AMS"
        }
        return codes.get(city.lower(), city[:3].upper())
    
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
        # Start from 30 days in the future to avoid date validation issues
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=30 + duration_days)).strftime("%Y-%m-%d")
        return checkin, checkout
    
    def _build_conversational_graph(self) -> StateGraph:
        """Build step-by-step conversational graph with style decision"""
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
        
        # Handle missing information flow
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
        
        # Continue with flight and hotel flow
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
        
        # After attractions, ask about style customization
        workflow.add_conditional_edges(
            "search_attractions",
            self._should_wait,
            {"wait": END, "continue": "handle_style_decision", "error": END}
        )
        
        # Handle style decision routing
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
                            if 1 <= duration <= 30:  # Reasonable trip duration
                                state["duration_days"] = duration
                    elif key == "budget" and value and value != "[amount]":
                        state["budget"] = value
                    elif key == "interests" and value and value != "[list]":
                        interests = [i.strip() for i in value.split(',') if i.strip() and len(i.strip()) > 1]
                        if interests:
                            state["interests"] = interests
            
            # Validate required information and ask for missing details
            missing_info = []
            
            if not state.get("origin"):
                missing_info.append("departure city")
            if not state.get("destination"):
                missing_info.append("destination")
            if not state.get("duration_days") or state.get("duration_days") < 1:
                missing_info.append("trip duration (number of days)")
            
            # If critical information is missing, ask for it
            if missing_info:
                if len(missing_info) == 1:
                    state["response"] = f"I need to know your {missing_info[0]} to help plan your trip. Could you please provide that information?"
                else:
                    info_list = ", ".join(missing_info[:-1]) + f" and {missing_info[-1]}"
                    state["response"] = f"To plan your perfect trip, I need a few more details: {info_list}. Could you please provide this information?"
                
                state["awaiting_user_choice"] = True
                state["current_step"] = "awaiting_missing_info"
                return state
            
            # Optional information - set defaults if missing
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
            
            # Validate trip duration
            if state["duration_days"] > 30:
                state["response"] = f"{state['duration_days']} days seems like a very long trip! Could you confirm the duration or specify a shorter timeframe (1-30 days)?"
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
            # Use AI to extract information from the user's response
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
                
            # If still missing info, ask again with more specific guidance
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
        
        # Information is complete, proceed to flight search
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
            
            # Get future dates to avoid date validation errors
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
        """Search attractions using Google Places"""
        print(f"🎯 Searching attractions in {state['destination']}")
        
        try:
            attractions = self.call_google_places_api(state["destination"], state.get("interests", []))
            state["attractions_data"] = attractions
            
            response = f"Found {len(attractions)} real attractions:\n\n"
            
            for attraction in attractions[:5]:
                response += f"• {attraction['name']} ({attraction['rating']}⭐)\n"
            
            # Ask user if they want to customize trip style
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
        
        # Use AI to interpret user's choice
        choice_prompt = f"User said: '{user_input}'\nThey can choose:\n1. Customize travel style\n2. Skip to itinerary\n\nWhat did they choose? Return only '1' or '2'."
        
        try:
            messages = [SystemMessage("Determine user choice."), HumanMessage(choice_prompt)]
            choice_response = self.llm.invoke(messages)
            choice = choice_response.content.strip()
            
            if "1" in choice or "customize" in user_input or "style" in user_input:
                # User wants to choose trip style
                state["current_step"] = "need_style_choice"
                state["response"] = "Perfect! Let's choose your travel style."
            else:
                # User wants to skip to itinerary - set default style
                state["selected_trip_style"] = "cultural"
                state["current_step"] = "skip_to_itinerary"
                state["response"] = "Great! Creating your balanced cultural itinerary now..."
                
            state["awaiting_user_choice"] = False
            
        except Exception as e:
            # Default to cultural style if there's an error
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
            
            attractions_text = "\n".join([f"• {a['name']} ({a['rating']}⭐)" for a in attractions[:8]])
            
            prompt = f"""Create a {state['duration_days']}-day {trip_style} itinerary for {state['destination']}:
            
            Flight: {selected_flight.get('airline', 'Selected')} {selected_flight.get('flight_number', '')}
            Hotel: {selected_hotel.get('name', 'Selected')} in {selected_hotel.get('location', 'city center')}
            
            Real attractions:
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
            response += f"\n\n**🌟 Based on real API data from AviationStack, Booking.com, and Google Places!**"
            
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

# Main execution
if __name__ == "__main__":
    print("🔑 Required API Keys:")
    print(f"AviationStack: {'✅' if os.getenv('FLIGHT_API_KEY') else '❌'}")
    print(f"RapidAPI: {'✅' if os.getenv('RAPIDAPI_KEY') else '❌'}")
    print(f"Google Places: {'✅' if os.getenv('GOOGLE_PLACES_API_KEY') else '❌'}")
    
    provider, api_key = interactive_setup()
    if not provider or not api_key:
        exit(1)
    
    try:
        atlas_ai = RealAPITravelAssistant(provider, api_key)
        print(f"\n🤖 Atlas AI Ready! (AI: {provider.title()})")
        print("Real APIs: AviationStack + Booking.com + Google Places")
        print("Tell me about your trip!\n")
        
        state = None
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if user_input.strip():
                try:
                    state = atlas_ai.chat(user_input, state)
                    print(f"\n🤖 Atlas AI: {state['response']}\n")
                    
                    if state.get("awaiting_user_choice"):
                        print(f"[Waiting for choice: {state['current_step']}]")
                    
                    print("-" * 40)
                except Exception as e:
                    print(f"❌ Error: {str(e)}")
    
    except Exception as e:
        print(f"❌ Failed: {str(e)}")