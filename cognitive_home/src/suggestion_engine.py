import os
import requests


DAYS = {
    0: "Monday",   1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday",  5: "Saturday",
    6: "Sunday"
}


class SuggestionEngine:
    def __init__(self):
        self.ollama_url = os.environ.get(
            "OLLAMA_URL", "http://ollama:11434/api/chat"
        )
        self.model = os.environ.get("OLLAMA_MODEL", "SmolLM2:360M")

        self.system_prompt = """
You are a smart home assistant that helps users automate their home routines.
Your job is to suggest automations based on patterns you have noticed.
Keep suggestions short, friendly, and clear — one or two sentences maximum.
Always end with a question asking if the user wants to automate it.
"""

    def _build_prompt(self, pattern: dict) -> str:
        day_name    = DAYS.get(pattern["weekday"], "unknown day")
        entity      = pattern["entity_id"]
        hour        = pattern["hour"]
        occurrences = pattern["occurrences"]
        confidence  = int(pattern["confidence"] * 100)

        prompt = (
            f"I noticed the following pattern in the home:\n"
            f"- Device: {entity}\n"
            f"- Usually activated at: {hour:02d}:00\n"
            f"- Day: {day_name}\n"
            f"- Occurred: {occurrences} times\n"
            f"- Confidence: {confidence}%\n\n"
            f"Write a short friendly suggestion to the user "
            f"asking if they want to automate this."
        )
        return prompt

    def _build_sequence_prompt(self, sequence: dict) -> str:
        trigger_parts  = sequence["trigger"].split("|")
        action_parts   = sequence["action"].split("|")
        trigger_entity = trigger_parts[0]
        trigger_state  = trigger_parts[1] if len(trigger_parts) > 1 else "activated"
        action_entity  = action_parts[0]
        action_state   = action_parts[1] if len(action_parts) > 1 else "activated"
        count          = sequence["count"]

        prompt = (
            f"I noticed the following sequence in the home:\n"
            f"- When: {trigger_entity} changes to '{trigger_state}'\n"
            f"- Then: {action_entity} is set to '{action_state}'\n"
            f"- This happened: {count} times\n\n"
            f"Write a short friendly suggestion to the user "
            f"asking if they want to automate this sequence."
        )
        return prompt

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
                data = response.json()
                return data["message"]["content"].strip()
            else:
                print(f"[suggestion_engine] Ollama error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print("[suggestion_engine] Ollama timed out")
            return None
        except Exception as e:
            print(f"[suggestion_engine] Ollama call failed: {e}")
            return None

    def _fallback_message(self, pattern: dict) -> str:
        # ── FIX: use correct day and friendly wording ──
        day_name = DAYS.get(pattern["weekday"], "regularly")
        entity   = pattern["entity_id"].split(".")[-1].replace("_", " ").title()
        hour     = pattern["hour"]
        occ      = pattern["occurrences"]

        # Format time nicely: 18 → "6:00 PM", 9 → "9:00 AM"
        if hour == 0:
            time_str = "12:00 AM"
        elif hour < 12:
            time_str = f"{hour}:00 AM"
        elif hour == 12:
            time_str = "12:00 PM"
        else:
            time_str = f"{hour - 12}:00 PM"

        return (
            f"I noticed you usually turn on {entity} "
            f"around {time_str} on {day_name} "
            f"({occ} times recorded). "
            f"Would you like me to automate this for you?"
        )

    def _fallback_sequence_message(self, sequence: dict) -> str:
        # ── FIX: better sequence fallback ──
        trigger_parts  = sequence["trigger"].split("|")
        action_parts   = sequence["action"].split("|")

        trigger_entity = trigger_parts[0].split(".")[-1].replace("_", " ").title()
        trigger_state  = trigger_parts[1] if len(trigger_parts) > 1 else "activated"
        action_entity  = action_parts[0].split(".")[-1].replace("_", " ").title()
        count          = sequence["count"]

        return (
            f"I noticed that whenever {trigger_entity} turns {trigger_state}, "
            f"you usually also activate {action_entity} "
            f"({count} times). "
            f"Would you like me to automate this?"
        )

    def generate_suggestion(self, pattern: dict) -> str:
        print(f"[suggestion_engine] Generating for: {pattern['entity_id']}")

        suggestion = self._call_ollama(self._build_prompt(pattern))

        if not suggestion:
            print("[suggestion_engine] Using fallback message")
            suggestion = self._fallback_message(pattern)

        print(f"[suggestion_engine] Result: {suggestion}")
        return suggestion

    def generate_sequence_suggestion(self, sequence: dict) -> str:
        print(f"[suggestion_engine] Generating sequence suggestion")

        suggestion = self._call_ollama(self._build_sequence_prompt(sequence))

        if not suggestion:
            suggestion = self._fallback_sequence_message(sequence)

        print(f"[suggestion_engine] Sequence result: {suggestion}")
        return suggestion