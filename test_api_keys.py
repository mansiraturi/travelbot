import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_aviationstack_api():
    """Test AviationStack API"""
    print("🛫 Testing AviationStack API...")
    
    api_key = os.getenv("FLIGHT_API_KEY")
    if not api_key:
        print("❌ FLIGHT_API_KEY not found in environment")
        return False
    
    try:
        # Test basic API access first
        url = "http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": api_key,
            "limit": 1  # Just get 1 result to test
        }
        
        print(f"🔗 Testing URL: {url}")
        print(f"🔑 API Key: {api_key[:10]}...")
        
        response = requests.get(url, params=params, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ AviationStack API working!")
            print(f"📋 Response keys: {list(data.keys())}")
            
            if data.get("data"):
                print(f"📈 Found {len(data['data'])} flights in response")
                # Show first flight sample
                first_flight = data["data"][0]
                airline = first_flight.get("airline", {}).get("name", "Unknown")
                print(f"📄 Sample flight: {airline}")
                return True
            else:
                print("⚠️ API works but no flight data returned")
                return False
                
        elif response.status_code == 403:
            print("❌ 403 Forbidden - Possible issues:")
            print("   • Invalid API key")
            print("   • Free tier quota exceeded (100 requests/month)")
            print("   • API key doesn't have flight search permissions")
            
            # Try to get more error details
            try:
                error_data = response.json()
                print(f"📋 Error details: {error_data}")
            except:
                print(f"📋 Raw error: {response.text}")
                
            return False
            
        elif response.status_code == 429:
            print("❌ 429 Too Many Requests - Rate limit exceeded")
            return False
            
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"📋 Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_rapidapi_booking():
    """Test Booking.com via RapidAPI"""
    print("\n🏨 Testing Booking.com via RapidAPI...")
    
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        print("❌ RAPIDAPI_KEY not found in environment")
        return False
    
    try:
        print(f"🔑 RapidAPI Key: {api_key[:10]}...")
        
        # Test 1: Get destination ID for Rome
        search_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
        }
        search_params = {
            "name": "Rome",
            "locale": "en-gb"
        }
        
        print(f"🔗 Testing location search: {search_url}")
        search_response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
        
        print(f"📊 Location Search Status: {search_response.status_code}")
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            print(f"✅ Location search working!")
            
            if search_data:
                dest_id = search_data[0]["dest_id"]
                dest_name = search_data[0]["name"]
                print(f"📄 Found destination: {dest_name} (ID: {dest_id})")
                
                # Test 2: Search hotels
                hotel_url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
                hotel_params = {
                    "dest_id": dest_id,
                    "order_by": "popularity",
                    "filter_by_currency": "USD",
                    "adults_number": "2",
                    "checkin_date": "2025-03-15",
                    "checkout_date": "2025-03-22",
                    "room_number": "1",
                    "units": "metric"
                }
                
                print(f"🔗 Testing hotel search: {hotel_url}")
                hotel_response = requests.get(hotel_url, headers=headers, params=hotel_params, timeout=15)
                
                print(f"📊 Hotel Search Status: {hotel_response.status_code}")
                
                if hotel_response.status_code == 200:
                    hotel_data = hotel_response.json()
                    hotels = hotel_data.get("result", [])
                    print(f"✅ Booking.com hotel search working!")
                    print(f"📈 Found {len(hotels)} hotels")
                    
                    if hotels:
                        first_hotel = hotels[0]
                        hotel_name = first_hotel.get("hotel_name", "Unknown")
                        price = first_hotel.get("min_total_price", "N/A")
                        print(f"📄 Sample hotel: {hotel_name} - ${price}")
                    
                    return True
                    
                else:
                    print(f"❌ Hotel search failed: {hotel_response.status_code}")
                    try:
                        error_data = hotel_response.json()
                        print(f"📋 Hotel error: {error_data}")
                    except:
                        print(f"📋 Raw hotel error: {hotel_response.text[:200]}")
                    return False
            else:
                print("❌ No location data found")
                return False
                
        elif search_response.status_code == 403:
            print("❌ 403 Forbidden - RapidAPI issues:")
            print("   • Invalid RapidAPI key")
            print("   • Not subscribed to Booking.com API")
            print("   • Free tier quota exceeded")
            print("   • API key doesn't have permission")
            
            try:
                error_data = search_response.json()
                print(f"📋 Error details: {error_data}")
            except:
                print(f"📋 Raw error: {search_response.text}")
            return False
            
        elif search_response.status_code == 429:
            print("❌ 429 Too Many Requests - Rate limit exceeded")
            return False
            
        else:
            print(f"❌ Unexpected status: {search_response.status_code}")
            print(f"📋 Response: {search_response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_google_places_api():
    """Test Google Places API"""
    print("\n🎯 Testing Google Places API...")
    
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("❌ GOOGLE_PLACES_API_KEY not found in environment")
        return False
    
    try:
        print(f"🔑 API Key: {api_key[:10]}...")
        
        # Test text search
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": "tourist attractions in Rome",
            "key": api_key,
            "type": "tourist_attraction"
        }
        
        print(f"🔗 Testing URL: {url}")
        response = requests.get(url, params=params, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Google Places API working!")
            print(f"📋 Response keys: {list(data.keys())}")
            
            results = data.get("results", [])
            if results:
                print(f"📈 Found {len(results)} attractions")
                print(f"📄 Sample attraction: {results[0]['name']}")
                return True
            else:
                print("⚠️ API works but no results returned")
                return False
                
        elif response.status_code == 403:
            print("❌ 403 Forbidden - Possible issues:")
            print("   • Invalid API key")
            print("   • Places API not enabled in Google Cloud Console")
            print("   • Billing not set up on Google Cloud")
            print("   • API key has domain/IP restrictions")
            
            try:
                error_data = response.json()
                print(f"📋 Error details: {error_data}")
            except:
                print(f"📋 Raw error: {response.text}")
            return False
            
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"📋 Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_all_apis():
    """Test all APIs and provide summary"""
    print("🧪 API Key Testing Suite")
    print("=" * 50)
    
    results = {
        "AviationStack": test_aviationstack_api(),
        "RapidAPI Booking.com": test_rapidapi_booking(), 
        "Google Places": test_google_places_api()
    }
    
    print("\n📊 API Test Summary:")
    print("=" * 30)
    
    working_apis = []
    failed_apis = []
    
    for api_name, status in results.items():
        if status:
            print(f"✅ {api_name}: Working")
            working_apis.append(api_name)
        else:
            print(f"❌ {api_name}: Failed")
            failed_apis.append(api_name)
    
    print(f"\n🎯 Summary: {len(working_apis)}/3 APIs working")
    
    if len(working_apis) == 3:
        print("🎉 All APIs working! Your travel assistant will have full functionality.")
    elif len(working_apis) >= 1:
        print(f"⚠️ Partial functionality - {len(failed_apis)} APIs need fixing:")
        for api in failed_apis:
            print(f"   • Fix {api} API configuration")
    else:
        print("❌ No APIs working - check all your API key configurations")
    
    print("\n🔧 Setup Instructions:")
    print("=" * 25)
    
    if not results.get("AviationStack"):
        print("🛫 AviationStack Setup:")
        print("   1. Go to https://aviationstack.com")
        print("   2. Sign up for free account") 
        print("   3. Get your access key from dashboard")
        print("   4. Add FLIGHT_API_KEY=your_key to .env")
    
    if not results.get("RapidAPI Booking.com"):
        print("🏨 RapidAPI Booking.com Setup:")
        print("   1. Go to https://rapidapi.com")
        print("   2. Sign up for free account")
        print("   3. Subscribe to Booking.com API (free tier)")
        print("   4. Get your X-RapidAPI-Key from Apps > Default Application")
        print("   5. Add RAPIDAPI_KEY=your_key to .env")
    
    if not results.get("Google Places"):
        print("🎯 Google Places Setup:")
        print("   1. Go to https://console.cloud.google.com")
        print("   2. Create project and enable Places API")
        print("   3. Set up billing (required even for free tier)")
        print("   4. Create API key with Places API permission")
        print("   5. Add GOOGLE_PLACES_API_KEY=your_key to .env")
    
    return results

def check_env_file():
    """Check .env file configuration"""
    print("\n🔧 Checking .env file configuration...")
    
    env_vars = [
        "FLIGHT_API_KEY",       # AviationStack
        "RAPIDAPI_KEY",         # RapidAPI for Booking.com
        "GOOGLE_PLACES_API_KEY", # Google Places
        "OPENAI_API_KEY",       # OpenAI (optional)
        "GEMINI_API_KEY"        # Gemini (optional)
    ]
    
    print("📋 Environment Variables Status:")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: Set ({len(value)} characters)")
        else:
            print(f"❌ {var}: Not set")
    
    # Check if .env file exists
    if os.path.exists(".env"):
        print("\n✅ .env file exists")
        with open(".env", "r") as f:
            lines = f.readlines()
            print(f"📄 .env file has {len(lines)} lines")
    else:
        print("\n❌ .env file not found")
        print("💡 Create a .env file with your API keys")

def test_rapidapi_key_only():
    """Quick test of just the RapidAPI key"""
    print("\n🔧 Quick RapidAPI Key Test...")
    
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        print("❌ RAPIDAPI_KEY not found")
        return False
    
    try:
        # Test with a simple RapidAPI endpoint to verify key works
        test_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
        }
        params = {"name": "Rome", "locale": "en-gb"}
        
        response = requests.get(test_url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            print("✅ RapidAPI key is valid and working")
            return True
        elif response.status_code == 403:
            print("❌ RapidAPI key invalid or not subscribed to Booking.com API")
            return False
        elif response.status_code == 429:
            print("❌ RapidAPI rate limit exceeded")
            return False
        else:
            print(f"❌ RapidAPI error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ RapidAPI test failed: {e}")
        return False

if __name__ == "__main__":
    # Check environment first
    check_env_file()
    
    # Quick RapidAPI test
    test_rapidapi_key_only()
    
    # Test all APIs
    results = test_all_apis()
    
    print("\n💡 Next Steps:")
    print("=" * 15)
    
    if results.get("RapidAPI Booking.com"):
        print("✅ RapidAPI Booking.com working - you can use hotels!")
    else:
        print("❌ Set up RapidAPI key for hotels")
    
    if results.get("AviationStack"):
        print("✅ AviationStack working - you can get flight schedules!")
    else:
        print("❌ Fix AviationStack key or check quota")
    
    if results.get("Google Places"):
        print("✅ Google Places working - you can get real attractions!")
    else:
        print("❌ Set up Google Places API")
    
    working_count = sum(results.values())
    if working_count >= 2:
        print(f"\n🎉 {working_count}/3 APIs working - your travel assistant will work!")
    else:
        print(f"\n⚠️ Only {working_count}/3 APIs working - fix the failed ones for full functionality")