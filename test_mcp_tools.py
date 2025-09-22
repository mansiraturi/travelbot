# Create test_mcp_tools.py
from travel_mcp_server import search_attractions, manage_session

# Test attractions (should work - uses free OpenStreetMap)
print("Testing attractions...")
result = search_attractions("Rome", ["cultural"])
print(f"Status: {'success' if result.get('status') == 'success' else 'error'}")
print(f"Found: {result.get('count', 0)} attractions")

# Test session management (should work with your PostgreSQL)
print("\nTesting sessions...")
result = manage_session("list")
print(f"Status: {'success' if result.get('status') == 'listed' else 'error'}")
print(f"Found: {len(result.get('sessions', []))} sessions")