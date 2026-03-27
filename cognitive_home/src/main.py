import os
import time
import schedule
import web_server
from ha_client import HAClient
from pattern_analyzer import PatternAnalyzer
from suggestion_engine import SuggestionEngine

# Read all settings from environment variables set by run.sh
CHECK_INTERVAL        = int(os.environ.get("CHECK_INTERVAL", "1"))
MIN_OCCURRENCES       = int(os.environ.get("MIN_OCCURRENCES", "1"))
CONFIDENCE_THRESHOLD  = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.2"))
LOOKAHEAD_MINUTES     = int(os.environ.get("LOOKAHEAD_MINUTES", "60"))
FORCE_SUGGESTION_MODE = os.environ.get("FORCE_SUGGESTION_MODE", "true").lower() == "true"
DISABLE_WEEKDAY_CHECK = os.environ.get("DISABLE_WEEKDAY_CHECK", "true").lower() == "true"

ha        = HAClient()
analyzer  = PatternAnalyzer()
suggester = SuggestionEngine()

# Share instances with web_server
web_server.ha       = ha
web_server.analyzer = analyzer

sent_today = set()


def learn_patterns():
    print("[main] Starting pattern learning...")

    target_entities = ha.get_target_entities()

    if not target_entities:
        print("[main] No target entities found, skipping learning")
        return

    print(f"[main] Analyzing {len(target_entities)} entities...")

    for entity_id in target_entities:
        print(f"[main] Analyzing: {entity_id}")
        try:
            history = ha.get_history(entity_id, days=1)

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
    print(f"[main] Settings → confidence>={CONFIDENCE_THRESHOLD} | "
          f"lookahead={LOOKAHEAD_MINUTES}m | "
          f"force={FORCE_SUGGESTION_MODE} | "
          f"skip_weekday={DISABLE_WEEKDAY_CHECK}")

    upcoming = analyzer.get_upcoming_patterns(
        lookahead_minutes=LOOKAHEAD_MINUTES,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        force_suggestion=FORCE_SUGGESTION_MODE,
        disable_weekday_check=DISABLE_WEEKDAY_CHECK
    )

    if not upcoming:
        print("[main] No upcoming patterns found")
        return

    print(f"[main] Found {len(upcoming)} upcoming patterns")

    for pattern in upcoming:
        entity_id = pattern["entity_id"]
        hour      = pattern["hour"]
        weekday   = pattern["weekday"]

        suggestion_id = f"{entity_id}|{hour}|{weekday}"

        if suggestion_id in sent_today:
            print(f"[main] Already sent suggestion for {entity_id} today, skipping")
            continue

        suggestion_text = suggester.generate_suggestion(pattern)

        # Send notification with link to confirmation page
        ha.send_notification(
            title="💡 Smart Suggestion",
            message=f"{suggestion_text}\n\n"
                    f"👉 Confirm at: http://homeassistant.local:8099",
            notification_id=suggestion_id
        )

        # Register with web server so user can confirm
        web_server.register_pending(suggestion_id, pattern)

        sent_today.add(suggestion_id)
        print(f"[main] Suggestion sent for {entity_id}")

    # Sequence suggestions
    top_sequences = analyzer.get_top_sequences(min_count=MIN_OCCURRENCES)

    for sequence in top_sequences:
        seq_id = f"seq|{sequence['trigger']}|{sequence['action']}"

        if seq_id in sent_today:
            continue

        suggestion_text = suggester.generate_sequence_suggestion(sequence)

        ha.send_notification(
            title="🔗 Sequence Suggestion",
            message=f"{suggestion_text}\n\n"
                    f"👉 Confirm at: http://homeassistant.local:8099",
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
        print(f"[main] CHECK_INTERVAL       = {CHECK_INTERVAL} minutes")
        print(f"[main] CONFIDENCE_THRESHOLD = {CONFIDENCE_THRESHOLD}")
        print(f"[main] LOOKAHEAD_MINUTES    = {LOOKAHEAD_MINUTES}")
        print(f"[main] FORCE_SUGGESTION     = {FORCE_SUGGESTION_MODE}")
        print(f"[main] DISABLE_WEEKDAY      = {DISABLE_WEEKDAY_CHECK}")

        # Start web server for confirmations
        web_server.start_server(port=8099)

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