import os
import requests


class SuggestionEngine:
    def __init__(self):
        # Read Ollama settings from environment variables
        # These were set in run.sh from HA config
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434/api/chat")
        self.model = os.environ.get("OLLAMA_MODEL", "SmolLM2:360M")

        # System prompt — tells Ollama what role it's playing
        # This is sent with every request
        self.system_prompt = """
You are a smart home assistant that helps users automate their home routines.
Your job is to suggest automations based on patterns you have noticed.
Keep suggestions short, friendly, and clear — one or two sentences maximum.
Always end with a question asking if the user wants to automate it.
"""

    def _build_prompt(self, pattern: dict) -> str:
        """
        Builds the user message we send to Ollama.
        Takes the raw pattern dict and turns it into
        a readable description for the LLM.

        pattern looks like:
        {
            "entity_id": "climate.ac",
            "hour": 18,
            "weekday": 0,
            "occurrences": 5,
            "confidence": 0.80
        }
        """
        # Convert weekday number to name
        # Python's weekday() returns 0=Monday, 6=Sunday
        days = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday"
        }

        day_name = days.get(pattern["weekday"], "unknown day")
        entity = pattern["entity_id"]
        hour = pattern["hour"]
        occurrences = pattern["occurrences"]
        confidence = int(pattern["confidence"] * 100)

        # Build a clear description of the pattern for Ollama
        prompt = (
            f"I noticed the following pattern in the home:\n"
            f"- Device: {entity}\n"
            f"- Usually activated at: {hour}:00\n"
            f"- Day: {day_name}\n"
            f"- Occurred: {occurrences} times\n"
            f"- Confidence: {confidence}%\n\n"
            f"Write a short friendly suggestion to the user "
            f"asking if they want to automate this."
        )

        return prompt

    def _build_sequence_prompt(self, sequence: dict) -> str:
        """
        Builds a prompt for sequence-based patterns.
        These are "A usually leads to B" patterns.

        sequence looks like:
        {
            "trigger": "person.home|home",
            "action": "climate.ac|cool",
            "count": 7
        }
        """
        # Split the keys back into entity and state
        trigger_parts = sequence["trigger"].split("|")
        action_parts = sequence["action"].split("|")

        trigger_entity = trigger_parts[0]
        trigger_state = trigger_parts[1]
        action_entity = action_parts[0]
        action_state = action_parts[1]
        count = sequence["count"]

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
        """
        Sends the prompt to Ollama and returns the response text.

        We wrap this in try/except because Ollama might:
        - Be slow to respond (timeout)
        - Not be running yet
        - Return an unexpected format

        In any of these cases we fall back to a simple
        hardcoded message instead of crashing.
        """
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "stream": False
                },
                timeout=30  # wait max 30 seconds for Ollama
            )

            if response.status_code == 200:
                data = response.json()
                # Navigate to the actual text in the response
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
        """
        If Ollama fails or times out, use this simple
        hardcoded message instead.
        This ensures the addon keeps working even
        if Ollama is down or busy.
        """
        days = {
            0: "Monday", 1: "Tuesday", 2: "Wednesday",
            3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
        }
        day_name = days.get(pattern["weekday"], "unknown day")
        entity = pattern["entity_id"]
        hour = pattern["hour"]

        return (
            f"I noticed you usually activate {entity} "
            f"at {hour}:00 on {day_name}. "
            f"Would you like me to automate this?"
        )

    def generate_suggestion(self, pattern: dict) -> str:
        """
        Main method — called from main.py for each upcoming pattern.

        1. Builds the prompt from the pattern data
        2. Sends it to Ollama
        3. Returns the suggestion text
        4. Falls back to hardcoded message if Ollama fails
        """
        print(f"[suggestion_engine] Generating suggestion for: {pattern['entity_id']}")

        # Build the prompt
        prompt = self._build_prompt(pattern)

        # Try Ollama first
        suggestion = self._call_ollama(prompt)

        # If Ollama failed, use fallback
        if not suggestion:
            print("[suggestion_engine] Using fallback message")
            suggestion = self._fallback_message(pattern)

        print(f"[suggestion_engine] Suggestion: {suggestion}")
        return suggestion

    def generate_sequence_suggestion(self, sequence: dict) -> str:
        """
        Same as generate_suggestion but for sequence patterns.
        Called from main.py for "A leads to B" patterns.
        """
        print(f"[suggestion_engine] Generating sequence suggestion")

        prompt = self._build_sequence_prompt(sequence)
        suggestion = self._call_ollama(prompt)

        if not suggestion:
            trigger_parts = sequence["trigger"].split("|")
            action_parts = sequence["action"].split("|")
            suggestion = (
                f"I noticed that when {trigger_parts[0]} is {trigger_parts[1]}, "
                f"you usually set {action_parts[0]} to {action_parts[1]}. "
                f"Would you like me to automate this?"
            )

        return suggestion