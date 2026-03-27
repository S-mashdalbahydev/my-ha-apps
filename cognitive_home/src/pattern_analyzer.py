import json
import os
from datetime import datetime
from collections import defaultdict


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
                dt = datetime.fromisoformat(state_change["last_changed"])
            except Exception:
                continue

            key = self._build_key(entity_id, dt.hour, dt.weekday())
            self._update_bayesian_confidence(key, entity_id, dt.hour, dt.weekday())
            self._update_sequence(prev_event, state_change)
            prev_event = state_change

        self.patterns = {
            k: v for k, v in self.patterns.items()
            if v["occurrences"] >= min_occurrences
        }

        self._save_patterns()

        # Debug — print all detected patterns
        print(f"[pattern_analyzer] Total patterns: {len(self.patterns)}")
        for k, v in self.patterns.items():
            print(f"[pattern_analyzer] Pattern: {k} | "
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
        now = datetime.now()
        current_hour = now.hour
        next_hour    = (now.hour + 1) % 24

        print(f"[pattern_analyzer] Time: {now.strftime('%H:%M')} | "
              f"current_hour={current_hour} | next_hour={next_hour}")
        print(f"[pattern_analyzer] confidence>={confidence_threshold} | "
              f"force={force_suggestion} | "
              f"skip_weekday={disable_weekday_check}")
        print(f"[pattern_analyzer] Total patterns in memory: {len(self.patterns)}")

        for k, v in self.patterns.items():
            print(f"[pattern_analyzer] Available: {k} | "
                  f"hour={v['hour']} | "
                  f"confidence={v['confidence']:.2f} | "
                  f"occurrences={v['occurrences']}")

        upcoming = []

        for key, pattern in self.patterns.items():
            is_right_hour = pattern["hour"] in [current_hour, next_hour]
            is_right_day  = True if disable_weekday_check else \
                            pattern["weekday"] == now.weekday()
            is_confident  = pattern["confidence"] >= confidence_threshold
            not_confirmed = not pattern["confirmed"]

            if is_right_hour and is_right_day and is_confident and not_confirmed:
                upcoming.append(pattern)
                print(f"[pattern_analyzer] ✅ Match: {key}")

        # Forced suggestion mode — pick strongest if nothing matched
        if not upcoming and force_suggestion and self.patterns:
            print("[pattern_analyzer] ⚠️ No match — forced suggestion mode")
            strongest = max(
                self.patterns.values(),
                key=lambda p: p["occurrences"]
            )
            if not strongest["confirmed"] and \
               strongest["confidence"] >= confidence_threshold:
                upcoming.append(strongest)
                print(f"[pattern_analyzer] 🔁 Forced: {strongest['entity_id']} | "
                      f"occurrences={strongest['occurrences']}")

        return upcoming

    def get_top_sequences(self, min_count: int = 3):
        sequences = []
        for trigger, actions in self.sequence_counts.items():
            for action, count in actions.items():
                if count >= min_count:
                    sequences.append({
                        "trigger": trigger,
                        "action": action,
                        "count": count
                    })
        sequences.sort(key=lambda x: x["count"], reverse=True)

        print(f"[pattern_analyzer] Top sequences: {len(sequences)}")
        for s in sequences[:3]:
            print(f"[pattern_analyzer] Sequence: {s['trigger']} → "
                  f"{s['action']} | count={s['count']}")

        return sequences

    def confirm_pattern(self, key: str):
        if key in self.patterns:
            self.patterns[key]["confirmed"] = True
            self._save_patterns()
            print(f"[pattern_analyzer] Pattern confirmed: {key}")