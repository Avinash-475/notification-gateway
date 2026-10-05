from locust import HttpUser, task, between


class NotificationUser(HttpUser):
    wait_time = between(1, 2)  

    def on_start(self):
        """Runs once per simulated user when it starts: sign up (or log in) and store a token."""
        import random
        self.email = f"loadtest{random.randint(1, 1_000_000)}@example.com"
        self.password = "secret123"

        self.client.post("/signup", json={
            "email": self.email,
            "password": self.password
        })

        response = self.client.post("/login", json={
            "email": self.email,
            "password": self.password
        })

        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            self.token = None

    @task
    def send_notification(self):
        if not self.token:
            return  

        self.client.post(
            "/notify",
            json={
                "type": "sms",
                "recipient": "12345",
                "content": "load test message"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )