import os
import requests
from datetime import datetime, timedelta, timezone


class HAClient:
    def __init__(self):
        self.token = os.environ.get("SUPERVISOR_TOKEN")
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_all_entities(self):
        try:
            response = requests.get(
                f"{self.base_url}/states",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ha_client] get_all_entities failed: {response.status_code}")
                print(f"[ha_client] get_all_entities body: {response.text[:500]}")
                return []
        except Exception as e:
            print(f"[ha_client] get_all_entities error: {e}")
            return []

    def get_history(self, entity_id: str, days: int = 1):
        try:
            start_time = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            end_time   = datetime.now(timezone.utc).isoformat()

            response = requests.get(
                f"{self.base_url}/history/period/{start_time}",
                headers=self.headers,
                params={
                    "filter_entity_id": entity_id,
                    "end_time": end_time,
                    "no_attributes": "true",
                },
                timeout=30,
            )

            print(f"[ha_client] get_history status for {entity_id}: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"[ha_client] get_history raw preview: {str(data)[:300]}")
                return data
            else:
                print(f"[ha_client] get_history failed: {response.status_code}")
                return []

        except Exception as e:
            print(f"[ha_client] get_history error: {e}")
            return []

    def get_target_entities(self):
        all_entities = self.get_all_entities()
        target_prefixes = (
            "climate.",
            "light.",
            "switch.",
            "media_player.",
            "input_boolean.",
        )

        targets = [
            entity["entity_id"]
            for entity in all_entities
            if entity["entity_id"].startswith(target_prefixes)
        ]

        print(f"[ha_client] Found {len(targets)} target entities")
        return targets

    def send_notification(self, title: str, message: str, notification_id: str):
        try:
            response = requests.post(
                f"{self.base_url}/services/persistent_notification/create",
                headers=self.headers,
                json={
                    "title": title,
                    "message": message,
                    "notification_id": notification_id
                }
            )
            if response.status_code == 200:
                print(f"[ha_client] Notification sent: {title}")
            else:
                print(f"[ha_client] Notification failed: {response.status_code}")
                print(f"[ha_client] Notification body: {response.text[:500]}")
        except Exception as e:
            print(f"[ha_client] send_notification error: {e}")

    def create_automation(self, entity_id: str, hour: int, weekday: int) -> bool:
        """
        Creates a real HA automation based on a confirmed pattern.
        Trigger: time is HH:00
        Action:  turn on the entity
        """
        days_map = {
            0: "mon", 1: "tue", 2: "wed",
            3: "thu", 4: "fri", 5: "sat", 6: "sun"
        }

        time_str  = f"{hour:02d}:00:00"
        domain    = entity_id.split(".")[0]
        auto_id   = entity_id.replace(".", "_") + f"_{hour}"

        automation = {
            "alias": f"Cognitive Home: {entity_id} at {hour:02d}:00",
            "description": "Auto-created by Cognitive Home addon",
            "mode": "single",
            "trigger": [
                {
                    "platform": "time",
                    "at": time_str
                }
            ],
            "condition": [],
            "action": [
                {
                    "service": f"{domain}.turn_on",
                    "target": {
                        "entity_id": entity_id
                    }
                }
            ]
        }

        try:
            response = requests.post(
                f"{self.base_url}/config/automation/config/{auto_id}",
                headers=self.headers,
                json=automation
            )

            if response.status_code in [200, 201]:
                print(f"[ha_client] Automation created: {entity_id} at {hour:02d}:00")
                return True
            else:
                print(f"[ha_client] Automation failed: {response.status_code}")
                print(f"[ha_client] Response: {response.text[:300]}")
                return False

        except Exception as e:
            print(f"[ha_client] create_automation error: {e}")
            return False

    def dismiss_notification(self, notification_id: str):
        """Dismisses a notification from the HA dashboard."""
        try:
            response = requests.post(
                f"{self.base_url}/services/persistent_notification/dismiss",
                headers=self.headers,
                json={"notification_id": notification_id}
            )
            if response.status_code == 200:
                print(f"[ha_client] Notification dismissed: {notification_id}")
        except Exception as e:
            print(f"[ha_client] dismiss_notification error: {e}")