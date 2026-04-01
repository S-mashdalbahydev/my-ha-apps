import os
import time
import schedule
import cognitive_web
from ha_client import HAClient
from pattern_analyzer import PatternAnalyzer
from suggestion_engine import SuggestionEngine


def _safe_float(val, default: float) -> float:
    try:
        if val in (None, "null", "None", ""):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int) -> int:
    try:
        if val in (None, "null", "None", ""):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


# Read all settings from environment variables set by run.sh
CHECK_INTERVAL        = _safe_int(os.environ.get("CHECK_INTERVAL"), 1)
MIN_OCCURRENCES       = _safe_int(os.environ.get("MIN_OCCURRENCES"), 1)
CONFIDENCE_THRESHOLD  = _safe_float(os.environ.get("CONFIDENCE_THRESHOLD"), 0.2)
LOOKAHEAD_MINUTES     = _safe_int(os.environ.get("LOOKAHEAD_MINUTES"), 60)
FORCE_SUGGESTION_MODE = os.environ.get(
    "FORCE_SUGGESTION_MODE", "false").lower() == "true"
DISABLE_WEEKDAY_CHECK = os.environ.get(
    "DISABLE_WEEKDAY_CHECK", "false").lower() == "true"
RESET_ON_STARTUP      = os.environ.get(
    "RESET_ON_STARTUP", "false").lower() == "true"
HISTORY_DAYS          = _safe_float(os.environ.get("HISTORY_DAYS"), 14)
INGRESS_ENTRY         = os.environ.get("INGRESS_ENTRY", "")

# Create instances
ha        = HAClient()
analyzer  = PatternAnalyzer()
suggester = SuggestionEngine()

# ── Pass disable_weekday to analyzer ──
# This changes how pattern keys are built:
# disable_weekday=True  → key = "entity|hour"
#   Monday + Tuesday + Wednesday all count together
# disable_weekday=False → key = "entity|hour|weekday"
#   Only same-weekday occurrences count
analyzer.disable_weekday = DISABLE_WEEKDAY_CHECK

# Share instances with web server
cognitive_web.ha            = ha
cognitive_web.analyzer      = analyzer
cognitive_web.ingress_entry = INGRESS_ENTRY

sent_today = set()


def learn_patterns():
    print("[main] Starting pattern learning...")

    target_entities = ha.get_target_entities()

    if not target_entities:
        print("[main] No target entities found, skipping")
        return

    print(f"[main] Analyzing {len(target_entities)} entities "
          f"(last {HISTORY_DAYS} days)...")

    for entity_id in target_entities:
        print(f"[main] Analyzing: {entity_id}")
        try:
            history = ha.get_history(entity_id, days=HISTORY_DAYS)
            if not history:
                print(f"[main] No history for {entity_id}, skipping")
                continue
            analyzer.analyze(history, entity_id, MIN_OCCURRENCES)
        except Exception as e:
            print(f"[main] Error analyzing {entity_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("[main] Pattern learning complete")


def check_and_suggest():
    print("[main] Checking for upcoming patterns...")
    print(f"[main] Patterns in memory: {len(analyzer.patterns)}")
    print(f"[main] Settings → "
          f"confidence>={CONFIDENCE_THRESHOLD} | "
          f"lookahead={LOOKAHEAD_MINUTES}m | "
          f"force={FORCE_SUGGESTION_MODE} | "
          f"skip_weekday={DISABLE_WEEKDAY_CHECK}")

    upcoming = analyzer.get_upcoming_patterns(
        lookahead_minutes    = LOOKAHEAD_MINUTES,
        confidence_threshold = CONFIDENCE_THRESHOLD,
        force_suggestion     = FORCE_SUGGESTION_MODE,
        disable_weekday_check= DISABLE_WEEKDAY_CHECK
    )

    if not upcoming:
        print("[main] No upcoming patterns found")
        return

    print(f"[main] Found {len(upcoming)} upcoming patterns")

    for pattern in upcoming:
        entity_id     = pattern["entity_id"]
        hour          = pattern["hour"]
        weekday       = pattern["weekday"]
        suggestion_id = f"{entity_id}|{hour}|{weekday}"

        if suggestion_id in sent_today:
            print(f"[main] Already sent today: {entity_id}, skipping")
            continue

        suggestion_text = suggester.generate_suggestion(pattern)

        ha.send_notification(
            title="💡 Smart Suggestion",
            message=f"{suggestion_text}\n\n"
                    f"👉 Open the Cognitive Home app to review",
            notification_id=suggestion_id
        )

        cognitive_web.register_pending(suggestion_id, pattern)
        sent_today.add(suggestion_id)
        print(f"[main] Suggestion sent for {entity_id}")

    top_sequences = analyzer.get_top_sequences(min_count=MIN_OCCURRENCES)

    for sequence in top_sequences:
        seq_id = f"seq|{sequence['trigger']}|{sequence['action']}"

        if seq_id in sent_today:
            continue

        suggestion_text = suggester.generate_sequence_suggestion(sequence)

        ha.send_notification(
            title="🔗 Sequence Suggestion",
            message=f"{suggestion_text}\n\n"
                    f"👉 Open the Cognitive Home app to review",
            notification_id=seq_id
        )

        sent_today.add(seq_id)
        print(f"[main] Sequence suggestion sent: {seq_id}")


def reset_daily_tracker():
    sent_today.clear()
    print("[main] Daily suggestion tracker reset")


def setup_schedule():
    schedule.every(1).minutes.do(learn_patterns)
    schedule.every(CHECK_INTERVAL).minutes.do(check_and_suggest)
    schedule.every().day.at("00:00").do(reset_daily_tracker)

    print(f"[main] Schedule → learning every 1 min | "
          f"suggesting every {CHECK_INTERVAL} min")


if __name__ == "__main__":
    try:
        print("[main] Cognitive Home starting...")
        print(f"[main] MIN_OCCURRENCES      = {MIN_OCCURRENCES}")
        print(f"[main] CHECK_INTERVAL       = {CHECK_INTERVAL} min")
        print(f"[main] CONFIDENCE_THRESHOLD = {CONFIDENCE_THRESHOLD}")
        print(f"[main] LOOKAHEAD_MINUTES    = {LOOKAHEAD_MINUTES}")
        print(f"[main] FORCE_SUGGESTION     = {FORCE_SUGGESTION_MODE}")
        print(f"[main] DISABLE_WEEKDAY      = {DISABLE_WEEKDAY_CHECK}")
        print(f"[main] RESET_ON_STARTUP     = {RESET_ON_STARTUP}")
        print(f"[main] HISTORY_DAYS         = {HISTORY_DAYS}")
        print(f"[main] INGRESS_ENTRY        = {INGRESS_ENTRY}")

        if RESET_ON_STARTUP:
            print("[main] Clearing old patterns...")
            analyzer.reset()

        cognitive_web.start_server(port=8099)

        print("[main] Running initial learning...")
        learn_patterns()

        print("[main] Running initial suggestion check...")
        check_and_suggest()

        setup_schedule()

        print("[main] Entering main loop...")

        while True:
            schedule.run_pending()
            time.sleep(60)

    except Exception as e:
        print(f"[main] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
