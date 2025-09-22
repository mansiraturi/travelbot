#!/usr/bin/env python3
"""
Atlas AI Travel MCP Server - FastMCP Version
Simplified MCP server using FastMCP for your travel tools
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import requests
import psycopg2
from dotenv import load_dotenv

# Import MCP FastMCP
from mcp.server.fastmcp import FastMCP

load_dotenv()  

# Initialize MCP server (must be global for mcp dev to detect)
app = FastMCP("Atlas AI Travel Assistant")

# ===========================================
# FLIGHT SEARCH TOOL
# ===========================================

@app.tool()
def search_flights(origin: str, destination: str, api_key: str = None) -> dict:
    """Search for real flights using AviationStack API
    
    Args:
        origin: Origin city or airport code
        destination: Destination city or airport code  
        api_key: AviationStack API key (optional, uses env if not provided)
    
    Returns:
        Dictionary with flight search results
    """
    try:
        # Use provided API key or environment variable
        if not api_key:
            api_key = os.getenv("FLIGHT_API_KEY")
        
        if not api_key:
            return {"error": "FLIGHT_API_KEY not configured"}
        
        # Convert cities to airport codes
        origin_code = get_airport_code(origin)
        dest_code = get_airport_code(destination)
        
        # Call AviationStack API
        url = "http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": api_key,
            "dep_iata": origin_code,
            "arr_iata": dest_code,
            "limit": 6
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"API error: HTTP {response.status_code}"}
        
        data = response.json()
        
        if "error" in data:
            return {"error": f"AviationStack error: {data['error']}"}
        
        flights = data.get("data", [])
        flight_results = []
        
        for flight in flights[:6]:
            airline_info = flight.get("airline", {}) or {}
            flight_info = flight.get("flight", {}) or {}
            departure_info = flight.get("departure", {}) or {}
            arrival_info = flight.get("arrival", {}) or {}
            
            flight_results.append({
                "airline": airline_info.get("name", "Unknown"),
                "flight_number": flight_info.get("number", "N/A"),
                "departure": departure_info.get("scheduled", "N/A"),
                "arrival": arrival_info.get("scheduled", "N/A"),
                "source": "AviationStack Real Data"
            })
        
        return {
            "status": "success",
            "route": f"{origin_code} → {dest_code}",
            "flights": flight_results,
            "count": len(flight_results)
        }
        
    except Exception as e:
        return {"error": f"Flight search failed: {str(e)}"}

# ===========================================
# HOTEL SEARCH TOOL
# ===========================================

@app.tool()
def search_hotels(destination: str, checkin: str, checkout: str, api_key: str = None) -> dict:
    """Search for real hotels using Booking.com API via RapidAPI
    
    Args:
        destination: Destination city
        checkin: Check-in date (YYYY-MM-DD)
        checkout: Check-out date (YYYY-MM-DD) 
        api_key: RapidAPI key (optional, uses env if not provided)
    
    Returns:
        Dictionary with hotel search results
    """
    try:
        # Use provided API key or environment variable
        if not api_key:
            api_key = os.getenv("RAPIDAPI_KEY")
            
        if not api_key:
            return {"error": "RAPIDAPI_KEY not configured"}
        
        # Step 1: Get destination ID
        search_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
        }
        
        search_response = requests.get(
            search_url, 
            headers=headers, 
            params={"name": destination, "locale": "en-gb"}, 
            timeout=10
        )
        
        if search_response.status_code != 200:
            return {"error": f"Location search failed: HTTP {search_response.status_code}"}
        
        search_data = search_response.json()
        if not search_data:
            return {"error": f"No location found for {destination}"}
        
        dest_id = search_data[0].get("dest_id")
        dest_type = search_data[0].get("dest_type", "city")
        
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
            "dest_type": dest_type,
            "units": "metric",
            "page_number": "0"
        }
        
        hotel_response = requests.get(hotel_url, headers=headers, params=hotel_params, timeout=20)
        
        if hotel_response.status_code != 200:
            return {"error": f"Hotel search failed: HTTP {hotel_response.status_code}"}
        
        hotel_data = hotel_response.json()
        hotels = hotel_data.get("result", [])
        
        hotel_results = []
        nights = calculate_nights(checkin, checkout)
        
        for hotel in hotels[:4]:
            price_info = hotel.get("min_total_price", 0)
            total_price = float(price_info) if price_info else 0
            per_night = total_price / nights if nights > 0 and total_price > 0 else total_price
            
            hotel_results.append({
                "name": hotel.get("hotel_name", "Hotel"),
                "price_per_night": round(per_night, 2) if per_night > 0 else "Check with hotel",
                "total_price": round(total_price, 2) if total_price > 0 else "Check with hotel",
                "location": hotel.get("district", "City center"),
                "rating": f"{hotel.get('review_score', 0)}/10",
                "review_count": hotel.get("review_nr", 0),
                "source": "Booking.com Real Data"
            })
        
        return {
            "status": "success",
            "destination": destination,
            "dates": f"{checkin} to {checkout}",
            "hotels": hotel_results,
            "count": len(hotel_results)
        }
        
    except Exception as e:
        return {"error": f"Hotel search failed: {str(e)}"}

# ===========================================
# ATTRACTIONS SEARCH TOOL
# ===========================================

@app.tool()
def search_attractions(destination: str, interests: List[str] = None) -> dict:
    """Search for real attractions using OpenStreetMap API
    
    Args:
        destination: Destination city
        interests: List of interests (optional)
    
    Returns:
        Dictionary with attractions search results
    """
    try:
        if interests is None:
            interests = []
            
        # Get coordinates
        coords = get_coordinates(destination)
        if not coords:
            return {"error": f"Could not find coordinates for {destination}"}
        
        lat, lon = coords
        
        # Query OpenStreetMap Overpass API
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
        
        if response.status_code != 200:
            return {"error": f"Overpass API error: HTTP {response.status_code}"}
        
        data = response.json()
        attractions = []
        
        for element in data.get('elements', [])[:15]:
            tags = element.get('tags', {})
            name = tags.get('name', 'Tourist Attraction')
            
            if name and name != 'yes' and len(name) > 1 and not name.isdigit():
                attraction_type = get_attraction_type(tags)
                
                attractions.append({
                    'name': name,
                    'type': attraction_type,
                    'address': format_address(tags, destination),
                    'price_info': get_price_info(tags),
                    'source': 'OpenStreetMap Real Data'
                })
        
        return {
            "status": "success",
            "destination": destination,
            "coordinates": [lat, lon],
            "attractions": attractions,
            "count": len(attractions)
        }
        
    except Exception as e:
        return {"error": f"Attractions search failed: {str(e)}"}

# ===========================================
# SESSION MANAGEMENT TOOL
# ===========================================

@app.tool()
def manage_session(action: str, session_id: str = None, session_data: dict = None) -> dict:
    """Manage travel planning sessions in PostgreSQL database
    
    Args:
        action: Action to perform (save, load, list, delete)
        session_id: Session ID (required for save, load, delete)
        session_data: Session data to save (required for save)
    
    Returns:
        Dictionary with operation result
    """
    try:
        db_config = {
            'host': '35.224.149.145',
            'port': 5432,
            'database': 'travel_sessions',
            'user': 'chatbot_user',
            'password': '#Mansi1234'
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        if action == "save" and session_id:
            if not session_data:
                session_data = {}
                
            state_json = json.dumps(session_data, default=str)
            cursor.execute('''
                INSERT INTO enhanced_travel_sessions 
                (session_id, conversation_state, current_step, awaiting_user_choice, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    conversation_state = %s,
                    current_step = %s,
                    awaiting_user_choice = %s,
                    updated_at = %s
            ''', (
                session_id, state_json, 
                session_data.get("current_step", ""),
                session_data.get("awaiting_user_choice", False),
                datetime.now(),
                # For UPDATE
                state_json,
                session_data.get("current_step", ""),
                session_data.get("awaiting_user_choice", False),
                datetime.now()
            ))
            conn.commit()
            result = {"status": "saved", "session_id": session_id}
            
        elif action == "load" and session_id:
            cursor.execute('SELECT conversation_state FROM enhanced_travel_sessions WHERE session_id = %s', (session_id,))
            row = cursor.fetchone()
            if row:
                result = {"status": "loaded", "data": json.loads(row[0])}
            else:
                result = {"status": "not_found"}
                
        elif action == "list":
            cursor.execute('''
                SELECT session_id, current_step, updated_at
                FROM enhanced_travel_sessions 
                ORDER BY updated_at DESC 
                LIMIT 20
            ''')
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row[0],
                    "current_step": row[1],
                    "last_activity": row[2].isoformat() if row[2] else None
                })
            result = {"status": "listed", "sessions": sessions}
            
        elif action == "delete" and session_id:
            cursor.execute('DELETE FROM enhanced_travel_sessions WHERE session_id = %s', (session_id,))
            conn.commit()
            result = {"status": "deleted", "session_id": session_id}
        
        else:
            result = {"status": "error", "message": "Invalid action or missing parameters"}
        
        cursor.close()
        conn.close()
        
        return result
        
    except Exception as e:
        return {"error": f"Session management failed: {str(e)}"}

# ===========================================
# HELPER FUNCTIONS
# ===========================================

def get_airport_code(city: str) -> str:
    """Convert city to airport code"""
    codes = {
        "boston": "BOS", "new york": "JFK", "chicago": "ORD", 
        "dallas": "DFW", "miami": "MIA", "paris": "CDG", 
        "london": "LHR", "rome": "FCO", "tokyo": "NRT"
    }
    city_clean = city.lower().split(',')[0].strip()
    return codes.get(city_clean, city[:3].upper())

def calculate_nights(checkin: str, checkout: str) -> int:
    """Calculate nights between dates"""
    try:
        checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
        checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
        return (checkout_date - checkin_date).days
    except:
        return 7

def get_coordinates(destination: str):
    """Get coordinates using Nominatim API"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {'q': destination, 'format': 'json', 'limit': 1}
        headers = {'User-Agent': 'AtlasAI-MCP/1.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
        return None
    except Exception:
        return None

def get_attraction_type(tags: dict) -> str:
    """Get attraction type from OSM tags"""
    if tags.get('tourism'):
        return tags['tourism'].replace('_', ' ').title()
    elif tags.get('historic'):
        return f"Historic {tags['historic'].replace('_', ' ').title()}"
    elif tags.get('amenity'):
        return tags['amenity'].replace('_', ' ').title()
    return 'Tourist Attraction'

def get_price_info(tags: dict) -> str:
    """Get price info from OSM tags"""
    if tags.get('fee') == 'no':
        return 'Free'
    elif tags.get('fee') == 'yes':
        return 'Admission required'
    elif tags.get('charge'):
        return f"Fee: {tags['charge']}"
    return 'Contact venue for pricing'

def format_address(tags: dict, destination: str) -> str:
    """Format address from OSM tags"""
    address_parts = []
    for key in ['addr:housenumber', 'addr:street', 'addr:city']:
        if tags.get(key):
            address_parts.append(tags[key])
    
    return ', '.join(address_parts) if address_parts else destination

# ===========================================
# SERVER STARTUP
# ===========================================

if __name__ == "__main__":
    print("Starting Atlas AI Travel MCP Server...")
    print("Available MCP Tools:")
    print("  • search_flights - Real flight data via AviationStack")
    print("  • search_hotels - Real hotel data via Booking.com")
    print("  • search_attractions - Real attractions via OpenStreetMap")
    print("  • manage_session - PostgreSQL session management")
    print("=" * 50)
    
    # Run the MCP server
    app.run()