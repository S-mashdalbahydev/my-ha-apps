import json
import os
from datetime import datetime
from collections import defaultdict


class PatternAnalyzer:
    def __init__(self, data_path="/data/patterns.json"):
      
        self.data_path = data_path
        self.patterns = self._load_patterns()

      
        self.sequence_counts = defaultdict(lambda: defaultdict(int))

    # ─────────────────────────────────────────
    # PERSISTENCE — saving and loading patterns
    # ─────────────────────────────────────────

    def _load_patterns(self):
        """
        Loads patterns from disk when the addon starts.
        If no file exists yet, returns empty dict.
        This is how the addon remembers what it learned
        even after a restart.
        """
        if os.path.exists(self.data_path):
            with open(self.data_path, "r") as f:
                return json.load(f)
        return {}

    def _save_patterns(self):
        """
        Saves current patterns to disk.
        Called every time we update a pattern so nothing is lost
        if the addon crashes or restarts.
        """
        with open(self.data_path, "w") as f:
            json.dump(self.patterns, f, indent=2)

    # ─────────────────────────────────────────
    # BAYESIAN ANALYSIS
    # ─────────────────────────────────────────

    def _build_key(self, entity_id: str, hour: int, weekday: int) -> str:
        """
        Creates a unique key for each pattern.
        Example: "climate.ac|18|0"
                  entity    hour  Monday

        We use this as the dict key in patterns.json
        so each unique combination has its own entry.
        """
        return f"{entity_id}|{hour}|{weekday}"

    def _update_bayesian_confidence(self, key: str, entity_id: str,
                                     hour: int, weekday: int):
        """
        This is the core of Bayesian inference.
        Every time we see the same pattern, we increase confidence.
        Every time we check and it didn't happen, confidence slightly drops.

        The formula:
            confidence = occurrences / (occurrences + missed)

        Example:
            happened 5 times, missed 1 time
            confidence = 5 / (5 + 1) = 0.83 → 83%

        Why is this better than just counting?
        Because it naturally handles exceptions.
        Missing one day doesn't destroy the pattern —
        it just slightly lowers confidence.
        """
        if key not in self.patterns:
            # First time we see this pattern — create it
            self.patterns[key] = {
                "entity_id": entity_id,
                "hour": hour,
                "weekday": weekday,
                "occurrences": 0,    # how many times it happened
                "missed": 0,         # how many times it didn't happen
                "confidence": 0.0,   # Bayesian confidence 0.0 → 1.0
                "confirmed": False   # did the user approve this?
            }

        # Increment occurrence count
        self.patterns[key]["occurrences"] += 1

        # Recalculate confidence using Bayesian formula
        occ = self.patterns[key]["occurrences"]
        missed = self.patterns[key]["missed"]
        self.patterns[key]["confidence"] = occ / (occ + missed)

    # ─────────────────────────────────────────
    # SEQUENCE ANALYSIS
    # ─────────────────────────────────────────

    def _update_sequence(self, prev_event: dict, curr_event: dict):
        """
        Tracks what action tends to follow another action.

        Example:
            prev: person arrives home
            curr: AC turns on
            → "person_home → AC on" happened again

        We store this as:
            sequence_counts["person.home|home"]["climate.ac|cool"] = 7

        This lets us later say:
        "When you arrive home, you usually turn on the AC"
        """
        if prev_event is None:
            return

        # Build keys for previous and current events
        prev_key = f"{prev_event['entity_id']}|{prev_event['state']}"
        curr_key = f"{curr_event['entity_id']}|{curr_event['state']}"

        # Increment the sequence count
        self.sequence_counts[prev_key][curr_key] += 1

    # ─────────────────────────────────────────
    # MAIN ANALYSIS — called from main.py
    # ─────────────────────────────────────────

    def analyze(self, history: list, entity_id: str, min_occurrences: int = 3):
        """
        Main method — takes raw HA history for one entity
        and runs both Bayesian and Sequence analysis on it.

        history       → raw data from ha_client.get_history()
        entity_id     → e.g. "climate.ac"
        min_occurrences → minimum times before we consider it a pattern
        """

        # The history comes as a list of lists from HA
        # We flatten it to get a simple list of state changes
        flat_history = []
        for record in history:
            if isinstance(record, list):
                flat_history.extend(record)

        # Sort by time so sequence analysis works correctly
        flat_history.sort(key=lambda x: x.get("last_changed", ""))

        prev_event = None  # used for sequence tracking

        for state_change in flat_history:

            # We only care about "active" states
            # off/unavailable/unknown mean nothing for our patterns
            active_states = ["on", "cool", "heat", "auto", "home", "playing"]
            if state_change.get("state") not in active_states:
                prev_event = state_change
                continue

            # Parse the timestamp
            # HA gives us ISO format: "2026-03-15T18:03:22+03:00"
            try:
                dt = datetime.fromisoformat(state_change["last_changed"])
            except Exception:
                continue

            # Build the pattern key using entity + hour + weekday
            # We use hour (not exact minute) to group approximate times
            # 18:03 and 18:07 both become hour=18 → same pattern
            key = self._build_key(entity_id, dt.hour, dt.weekday())

            # Run Bayesian update for this observation
            self._update_bayesian_confidence(key, entity_id, dt.hour, dt.weekday())

            # Run sequence update — what followed what
            self._update_sequence(prev_event, state_change)

            prev_event = state_change

        # After processing, remove weak patterns below min_occurrences
        # We don't want to suggest something that happened only once or twice
        self.patterns = {
            k: v for k, v in self.patterns.items()
            if v["occurrences"] >= min_occurrences
        }

        # Save everything to disk
        self._save_patterns()

        return self.patterns

    # ─────────────────────────────────────────
    # SUGGESTIONS — called every 15 minutes
    # ─────────────────────────────────────────

    def get_upcoming_patterns(self, lookahead_minutes: int = 60):
        """
        Called every 15 minutes by main.py.
        Returns patterns that are expected to happen
        within the next `lookahead_minutes`.

        Example:
            It's 5:10 PM now, lookahead = 60 mins
            → returns patterns with hour = 18 (6 PM)
            → "AC usually turns on at 6 PM"

        We only return patterns that:
        1. Are expected soon (within lookahead window)
        2. Have high enough confidence (>= 0.6)
        3. Haven't been confirmed yet (not already automated)
        """
        now = datetime.now()

        # Calculate what hour we're looking ahead to
        future_hour = (now.hour + (now.minute + lookahead_minutes) // 60) % 24

        upcoming = []

        for key, pattern in self.patterns.items():
            is_right_hour = pattern["hour"] == future_hour
            is_right_day = pattern["weekday"] == now.weekday()
            is_confident = pattern["confidence"] >= 0.6
            not_confirmed = not pattern["confirmed"]

            if is_right_hour and is_right_day and is_confident and not_confirmed:
                upcoming.append(pattern)

        return upcoming

    def get_top_sequences(self, min_count: int = 3):
        """
        Returns the strongest sequences we've learned.
        These are "A usually leads to B" patterns.

        Example return:
        [
            {
                "trigger": "person.home|home",
                "action": "climate.ac|cool",
                "count": 7
            }
        ]
        """
        sequences = []

        for trigger, actions in self.sequence_counts.items():
            for action, count in actions.items():
                if count >= min_count:
                    sequences.append({
                        "trigger": trigger,
                        "action": action,
                        "count": count
                    })

        # Sort by strongest sequence first
        sequences.sort(key=lambda x: x["count"], reverse=True)
        return sequences

    def confirm_pattern(self, key: str):
        """
        Called when the user approves a suggestion.
        Marks the pattern as confirmed so we stop suggesting it.
        """
        if key in self.patterns:
            self.patterns[key]["confirmed"] = True
            self._save_patterns()
            print(f"[pattern_analyzer] Pattern confirmed: {key}")
