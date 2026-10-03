import requests

BASE_URL = "http://127.0.0.1:8000"

# 1. Signup
signup_response = requests.post(f"{BASE_URL}/signup", json={
    "email": "testscript@example.com",
    "password": "testpass123"
})
print("Signup:", signup_response.status_code, signup_response.json())

# 2. Login
login_response = requests.post(f"{BASE_URL}/login", json={
    "email": "testscript@example.com",
    "password": "testpass123"
})
login_data = login_response.json()
access_token = login_data["access_token"]
print("Login:", login_response.status_code)

# 3. Notify
headers = {"Authorization": f"Bearer {access_token}"}
notify_response = requests.post(f"{BASE_URL}/notify", json={
    "type": "email",
    "recipient": "someone@example.com",
    "content": "Hello from test script!"
}, headers=headers)
notify_data = notify_response.json()
print("Notify:", notify_response.status_code, notify_data)

# 4. Check status
status_response = requests.get(f"{BASE_URL}/status/{notify_data['id']}", headers=headers)
print("Status:", status_response.status_code, status_response.json())

