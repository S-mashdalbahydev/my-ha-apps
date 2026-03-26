import os
import requests
from datetime import datetime, timedelta

class HAClient:
    def __init__(self):
        self.token = os.environ.get("SUPERVISOR_TOKEN")
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    # return all devices/entities currently in HA
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
                return []
        except Exception as e:
            print(f"[ha_client] get_all_entities error: {e}")
            return []
        
#  show the history of a specific device for the last n days(return raw data)
    def get_history(self, entity_id: str, days: int = 14):
      
        try:
            start_time = (datetime.now() - timedelta(days=days)).isoformat()
            response = requests.get(
                f"{self.base_url}/history/period/{start_time}",
                headers=self.headers,
                params={"filter_entity_id": entity_id}
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ha_client] get_history failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"[ha_client] get_history error: {e}")
            return []
    # return only the devices we care about for pattern learning
    def get_target_entities(self):
       
        all_entities = self.get_all_entities()
        target_prefixes = ("climate.", "light.", "switch.", "media_player.")

        targets = [
            entity["entity_id"]
            for entity in all_entities
            if entity["entity_id"].startswith(target_prefixes)
        ]

        print(f"[ha_client] Found {len(targets)} target entities")
        return targets
    #  Sends a notification to the HA dashboard
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
        except Exception as e:
            print(f"[ha_client] send_notification error: {e}")
