import psycopg2

def test_connection():
    print("🔄 Testing PostgreSQL connection...")
    
    try:
        conn = psycopg2.connect(
            host='35.224.149.145',  # Your Cloud SQL IP
            port=5432,
            database='travel_sessions', 
            user='chatbot_user',
            password='#Mansi1234'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected! PostgreSQL: {version[0][:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()