import requests
import time

BASE_URL = "http://127.0.0.1:8000"

signup_data = {"email": "ratetest@test.com", "password": "ratetest123"}
signup_response = requests.post(f"{BASE_URL}/signup", json=signup_data)
print("SIGNUP:", signup_response.status_code, signup_response.json())

login_response = requests.post(f"{BASE_URL}/login", json=signup_data)
print("LOGIN STATUS:", login_response.status_code)
print("LOGIN BODY:", login_response.json())

access_token = login_response.json().get("access_token")
headers = {"Authorization": f"Bearer {access_token}"}

notify_data = {"type": "email", "recipient": "someone@test.com", "content": "Rate limit test"}

for i in range(7):
    response = requests.post(f"{BASE_URL}/notify", json=notify_data, headers=headers)
    print(f"Request {i+1}: {response.status_code} - {response.json()}")