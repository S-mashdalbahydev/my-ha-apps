import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

LOCAL_TZ = timezone(timedelta(hours=3))


class PatternAnalyzer:
    def __init__(self, data_path="/data/patterns.json"):
        self.data_path       = data_path
        self.seq_path        = data_path.replace("patterns.json", "sequences.json")
        self.patterns        = self._load_patterns()
        self.sequence_counts = defaultdict(lambda: defaultdict(int))
        self.disable_weekday = False

    def _load_patterns(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, "r") as f:
                return json.load(f)
        return {}

    def _save_patterns(self):
        with open(self.data_path, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def reset(self):
        self.patterns = {}
        self.sequence_counts.clear()

        if os.path.exists(self.data_path):
            os.remove(self.data_path)
            print("[pattern_analyzer] patterns.json deleted")

        if os.path.exists(self.seq_path):
            os.remove(self.seq_path)
            print("[pattern_analyzer] sequences.json deleted")

        print("[pattern_analyzer] Reset complete")

    def _build_key(self, entity_id: str, hour: int, weekday: int) -> str:

        if self.disable_weekday:
            return f"{entity_id}|{hour}"
        else:
            return f"{entity_id}|{hour}|{weekday}"

    def _update_bayesian_confidence(self, key: str, entity_id: str,
                                    hour: int, weekday: int):
        if key not in self.patterns:
            self.patterns[key] = {
                "entity_id":   entity_id,
                "hour":        hour,
                "weekday":     weekday,
                "occurrences": 0,
                "missed":      0,
                "confidence":  0.0,
                "confirmed":   False
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

        trigger_entity = prev_event["entity_id"]
        action_entity  = curr_event["entity_id"]
        if trigger_entity == action_entity:
            return

        prev_key = f"{prev_event['entity_id']}|{prev_event['state']}"
        curr_key = f"{curr_event['entity_id']}|{curr_event['state']}"

        self.sequence_counts[prev_key][curr_key] += 1

    def analyze(self, history: list, entity_id: str, min_occurrences: int = 3):

        # ── THE FIX ──
        # Reset occurrences for this entity before reanalyzing
        # So we always get the true count from history
        keys_to_reset = [
            k for k in self.patterns
            if k.startswith(entity_id)
        ]
        for k in keys_to_reset:
            self.patterns[k]["occurrences"] = 0
            self.patterns[k]["missed"]      = 0
            # confidence will be recalculated below
            # co
        # ─────────────

        # Reset sequence counts
        self.sequence_counts.clear()

        # Step 1: Flatten nested list
        flat_history = []
        for record in history:
            if isinstance(record, list):
                flat_history.extend(record)

        # Step 2: Sort oldest to newest
        flat_history.sort(key=lambda x: x.get("last_changed", ""))

        # Debug
        print(f"[pattern_analyzer] Total events: {len(flat_history)}")
        on_count = sum(1 for e in flat_history if e.get("state") == "on")
        print(f"[pattern_analyzer] 'on' events: {on_count}")

        prev_event = None

        for state_change in flat_history:

            # Step 3: Filter active states only
            active_states = ["on", "cool", "heat", "auto", "home", "playing"]
            if state_change.get("state") not in active_states:
                prev_event = state_change
                continue

            # Step 4: Convert UTC → local time
            try:
                dt_utc   = datetime.fromisoformat(state_change["last_changed"])
                dt_local = dt_utc.astimezone(LOCAL_TZ)
            except Exception:
                continue

            # Step 5: Build key
            hour    = dt_local.hour
            weekday = dt_local.weekday()
            key     = self._build_key(entity_id, hour, weekday)

            print(f"[pattern_analyzer] Event: "
                  f"state={state_change.get('state')} "
                  f"local={dt_local.strftime('%H:%M %A')} "
                  f"key={key}")

            # Step 6: Update Bayesian and Sequence
            self._update_bayesian_confidence(key, entity_id, hour, weekday)
            self._update_sequence(prev_event, state_change)
            prev_event = state_change

        # Step 7: Remove weak patterns
        self.patterns = {
            k: v for k, v in self.patterns.items()
            if v["occurrences"] >= min_occurrences
        }

        # Step 8: Save
        self._save_patterns()

        # Debug output
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
        confidence_threshold: float = 0.6,
        force_suggestion: bool = False,
        disable_weekday_check: bool = False
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
                if not v["confirmed"] and
                   v["confidence"] >= confidence_threshold
            }
            if unconfirmed:
                strongest = max(
                    unconfirmed.values(),
                    key=lambda p: p["occurrences"]
                )
                upcoming.append(strongest)
                print(f"[pattern_analyzer] 🔁 Forced: "
                      f"{strongest['entity_id']}")
            else:
                print("[pattern_analyzer] All patterns confirmed")

        return upcoming

    def get_top_sequences(self, min_count: int = 3):
        sequences = []

        for trigger, actions in self.sequence_counts.items():
            if "|" not in trigger or trigger.endswith("|"):
                continue

            for action, count in actions.items():
                trigger_entity = trigger.split("|")[0]
                action_entity  = action.split("|")[0]

                if trigger_entity == action_entity:
                    continue

                if count >= min_count:
                    sequences.append({
                        "trigger": trigger,
                        "action":  action,
                        "count":   count
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
            print(f"[pattern_analyzer] Confirmed: {key}")