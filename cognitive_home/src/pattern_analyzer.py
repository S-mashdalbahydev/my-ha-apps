import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Riyadh = UTC+3 — change if needed
LOCAL_TZ = timezone(timedelta(hours=3))


class PatternAnalyzer:
    def __init__(self, data_path="/data/patterns.json"):
        self.data_path = data_path
        self.patterns = self._load_patterns()
        self.sequence_counts = defaultdict(lambda: defaultdict(int))

    def _load_patterns(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, "r") as f:
                return json.load(f)
        return {}

    def _save_patterns(self):
        with open(self.data_path, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def reset(self):
        """Wipes all learned patterns from memory and disk."""
        self.patterns = {}
        self.sequence_counts.clear()
        if os.path.exists(self.data_path):
            os.remove(self.data_path)
            print("[pattern_analyzer] patterns.json deleted")
        print("[pattern_analyzer] Reset complete")

    def _build_key(self, entity_id: str, hour: int, weekday: int) -> str:
        return f"{entity_id}|{hour}|{weekday}"

    def _update_bayesian_confidence(self, key: str, entity_id: str,
                                    hour: int, weekday: int):
        if key not in self.patterns:
            self.patterns[key] = {
                "entity_id": entity_id,
                "hour": hour,
                "weekday": weekday,
                "occurrences": 0,
                "missed": 0,
                "confidence": 0.0,
                "confirmed": False
            }
        self.patterns[key]["occurrences"] += 1
        occ    = self.patterns[key]["occurrences"]
        missed = self.patterns[key]["missed"]
        self.patterns[key]["confidence"] = occ / (occ + missed)

    def _update_sequence(self, prev_event: dict, curr_event: dict):
        if prev_event is None:
            return
        if not prev_event.get("state") or not curr_event.get("state"):
            return
        prev_key = f"{prev_event['entity_id']}|{prev_event['state']}"
        curr_key = f"{curr_event['entity_id']}|{curr_event['state']}"
        self.sequence_counts[prev_key][curr_key] += 1

    def analyze(self, history: list, entity_id: str, min_occurrences: int = 3):
        flat_history = []
        for record in history:
            if isinstance(record, list):
                flat_history.extend(record)

        flat_history.sort(key=lambda x: x.get("last_changed", ""))

        prev_event = None

        for state_change in flat_history:
            active_states = ["on", "cool", "heat", "auto", "home", "playing"]
            if state_change.get("state") not in active_states:
                prev_event = state_change
                continue

            try:
                # Convert UTC timestamp to local time
                dt_utc   = datetime.fromisoformat(state_change["last_changed"])
                dt_local = dt_utc.astimezone(LOCAL_TZ)
            except Exception:
                continue

            key = self._build_key(entity_id, dt_local.hour, dt_local.weekday())
            self._update_bayesian_confidence(
                key, entity_id, dt_local.hour, dt_local.weekday()
            )
            self._update_sequence(prev_event, state_change)
            prev_event = state_change

        self.patterns = {
            k: v for k, v in self.patterns.items()
            if v["occurrences"] >= min_occurrences
        }

        self._save_patterns()

        print(f"[pattern_analyzer] Total patterns: {len(self.patterns)}")
        for k, v in self.patterns.items():
            print(f"[pattern_analyzer] {k} | "
                  f"occurrences={v['occurrences']} | "
                  f"confidence={v['confidence']:.2f} | "
                  f"confirmed={v['confirmed']}")

        return self.patterns

    def get_upcoming_patterns(
        self,
        lookahead_minutes: int = 60,
        confidence_threshold: float = 0.2,
        force_suggestion: bool = True,
        disable_weekday_check: bool = True
    ):
        now          = datetime.now(LOCAL_TZ)
        current_hour = now.hour
        next_hour    = (now.hour + 1) % 24

        print(f"[pattern_analyzer] Local time: {now.strftime('%H:%M %A')}")
        print(f"[pattern_analyzer] Total patterns: {len(self.patterns)}")

        for k, v in self.patterns.items():
            print(f"[pattern_analyzer] Available: {k} | "
                  f"hour={v['hour']} | "
                  f"confidence={v['confidence']:.2f} | "
                  f"occurrences={v['occurrences']}")

        upcoming = []

        for key, pattern in self.patterns.items():
            is_right_hour = pattern["hour"] in [current_hour, next_hour]
            is_right_day  = (True if disable_weekday_check
                             else pattern["weekday"] == now.weekday())
            is_confident  = pattern["confidence"] >= confidence_threshold
            not_confirmed = not pattern["confirmed"]

            if is_right_hour and is_right_day and is_confident and not_confirmed:
                upcoming.append(pattern)
                print(f"[pattern_analyzer] ✅ Match: {key}")

        if not upcoming and force_suggestion and self.patterns:
            print("[pattern_analyzer] ⚠️ Forced suggestion mode")
            unconfirmed = {
                k: v for k, v in self.patterns.items()
                if not v["confirmed"] and v["confidence"] >= confidence_threshold
            }
            if unconfirmed:
                strongest = max(
                    unconfirmed.values(),
                    key=lambda p: p["occurrences"]
                )
                upcoming.append(strongest)
                print(f"[pattern_analyzer] 🔁 Forced: {strongest['entity_id']}")
            else:
                print("[pattern_analyzer] All patterns confirmed")

        return upcoming

    def get_top_sequences(self, min_count: int = 3):
        sequences = []
        for trigger, actions in self.sequence_counts.items():
            if "|" not in trigger or trigger.endswith("|"):
                continue
            for action, count in actions.items():
                if count >= min_count:
                    sequences.append({
                        "trigger": trigger,
                        "action": action,
                        "count": count
                    })
        sequences.sort(key=lambda x: x["count"], reverse=True)
        return sequences

    def confirm_pattern(self, key: str):
        if key in self.patterns:
            self.patterns[key]["confirmed"] = True
            self._save_patterns()
            print(f"[pattern_analyzer] Confirmed: {key}")