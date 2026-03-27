import os
import requests

DAYS = {
    0: "Monday",   1: "Tuesday",  2: "Wednesday",
    3: "Thursday", 4: "Friday",   5: "Saturday",
    6: "Sunday"
}


def format_time(hour: int) -> str:
    if hour == 0:
        return "12:00 AM"
    elif hour < 12:
        return f"{hour}:00 AM"
    elif hour == 12:
        return "12:00 PM"
    else:
        return f"{hour - 12}:00 PM"


def friendly_name(entity_id: str) -> str:
    return entity_id.split(".")[-1].replace("_", " ").title()


class SuggestionEngine:
    def __init__(self):
        self.ollama_url = os.environ.get(
            "OLLAMA_URL", "http://ollama:11434/api/chat"
        )
        self.model = os.environ.get("OLLAMA_MODEL", "SmolLM2:360M")
        self.system_prompt = """
You are a smart home assistant that helps users automate their home routines.
Suggest automations based on detected patterns.
Keep suggestions short, friendly, and clear — one or two sentences maximum.
Always end with a question asking if the user wants to automate it.
"""

    def _call_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user",   "content": prompt}
                    ],
                    "stream": False
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["message"]["content"].strip()
            return None
        except Exception as e:
            print(f"[suggestion_engine] Ollama call failed: {e}")
            return None

    def generate_suggestion(self, pattern: dict) -> str:
        day_name = DAYS.get(pattern["weekday"], "regularly")
        entity   = friendly_name(pattern["entity_id"])
        time_str = format_time(pattern["hour"])
        occ      = pattern["occurrences"]

        prompt = (
            f"Device: {entity}\n"
            f"Usually activated at: {time_str} on {day_name}\n"
            f"Occurred: {occ} times\n"
            f"Write a short friendly suggestion asking if the user "
            f"wants to automate this."
        )

        suggestion = self._call_ollama(prompt)

        if not suggestion:
            suggestion = (
                f"I noticed you usually turn on {entity} "
                f"at {time_str} on {day_name} "
                f"({occ} times recorded). "
                f"Would you like me to automate this for you?"
            )

        print(f"[suggestion_engine] {suggestion}")
        return suggestion

    def generate_sequence_suggestion(self, sequence: dict) -> str:
        trigger_parts  = sequence["trigger"].split("|")
        action_parts   = sequence["action"].split("|")
        trigger_entity = friendly_name(trigger_parts[0])
        trigger_state  = trigger_parts[1] if len(trigger_parts) > 1 else "activated"
        action_entity  = friendly_name(action_parts[0])
        count          = sequence["count"]

        prompt = (
            f"When {trigger_entity} turns {trigger_state}, "
            f"the user usually activates {action_entity}. "
            f"This happened {count} times. "
            f"Write a short friendly suggestion asking if they want "
            f"to automate this sequence."
        )

        suggestion = self._call_ollama(prompt)

        if not suggestion:
            suggestion = (
                f"I noticed that whenever {trigger_entity} turns {trigger_state}, "
                f"you usually also activate {action_entity} "
                f"({count} times recorded). "
                f"Would you like me to automate this?"
            )

        print(f"[suggestion_engine] {suggestion}")
        return suggestion