import requests
import sys

BASE_URL = "http://localhost:8003"

def test_auth():
    print(f"Testing auth on {BASE_URL}...")
    
    # 1. Register
    email = "test@example.com"
    username = "testuser"
    password = "password123"
    
    print(f"\n1. Registering user {username}...")
    register_data = {
        "email": email,
        "username": username,
        "password": password,
        "full_name": "Test User"
    }
    
    try:
        # Check if user already exists (for re-runs)
        # We can't delete easily, so we might fail if exists. 
        # Let's try to login first, if success, we skip register
        login_data = {
            "username": username,
            "password": password
        }
        res = requests.post(f"{BASE_URL}/auth/login", data=login_data)
        if res.status_code == 200:
            print("User already exists, skipping registration.")
        else:
            response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
            if response.status_code == 200:
                print("Registration successful!")
                print(response.json())
            elif response.status_code == 400 and "already" in response.text:
                 print("User validation caught existing user.")
            else:
                print(f"Registration failed: {response.status_code} {response.text}")
                # We might continue to login to see if that works
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 2. Login
    print(f"\n2. Logging in...")
    login_data = {
        "username": username,
        "password": password
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} {response.text}")
        return
    
    token_data = response.json()
    print("Login successful!")
    print(token_data)
    access_token = token_data["access_token"]
    
    # 3. Get Me
    print(f"\n3. Getting user profile...")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    
    if response.status_code == 200:
        print("Profile retrieval successful!")
        print(response.json())
    else:
        print(f"Profile retrieval failed: {response.status_code} {response.text}")

if __name__ == "__main__":
    test_auth()
