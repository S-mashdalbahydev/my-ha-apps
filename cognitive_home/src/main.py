import os
import time
import schedule
from ha_client import HAClient
from pattern_analyzer import PatternAnalyzer
from suggestion_engine import SuggestionEngine



CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "15"))
MIN_OCCURRENCES = int(os.environ.get("MIN_OCCURRENCES", "3"))


ha = HAClient()
analyzer = PatternAnalyzer()
suggester = SuggestionEngine()


sent_today = set()




def learn_patterns():
    """
    Fetches history from HA for all target devices
    and runs pattern analysis on each one.

    This is the "learning" phase — we're not suggesting
    anything here, just updating what we know.
    """
    print("[main] Starting pattern learning...")

    # Get all devices we care about (AC, lights, switches, TV)
    target_entities = ha.get_target_entities()

    if not target_entities:
        print("[main] No target entities found, skipping learning")
        return

    print(f"[main] Analyzing {len(target_entities)} entities...")

    # Loop through each device and analyze its history
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


# ─────────────────────────────────────────
# TASK 2 — SUGGESTING (runs every 15 mins)
# ─────────────────────────────────────────

def check_and_suggest():
    """
    Checks if any learned patterns are expected
    to happen in the next 60 minutes.
    If yes, generates a suggestion and sends it
    as a notification in HA.
    """
    print("[main] Checking for upcoming patterns...")

    # Get patterns expected in the next 60 minutes
    upcoming = analyzer.get_upcoming_patterns(lookahead_minutes=60)

    if not upcoming:
        print("[main] No upcoming patterns found")
        return

    print(f"[main] Found {len(upcoming)} upcoming patterns")

    for pattern in upcoming:
        entity_id = pattern["entity_id"]
        hour = pattern["hour"]
        weekday = pattern["weekday"]

        # Build a unique ID for this suggestion
        # Format: "climate.ac|18|0"
        # This is the same key used in patterns.json
        suggestion_id = f"{entity_id}|{hour}|{weekday}"

        # Skip if we already sent this suggestion today
        # We don't want to spam the user every 15 minutes
        if suggestion_id in sent_today:
            print(f"[main] Already sent suggestion for {entity_id} today, skipping")
            continue

        # Generate the suggestion text using Ollama
        suggestion_text = suggester.generate_suggestion(pattern)

        # Send it as a notification in HA
        ha.send_notification(
            title="💡 Smart Suggestion",
            message=suggestion_text,
            notification_id=suggestion_id
        )

        # Mark as sent so we don't send it again today
        sent_today.add(suggestion_id)
        print(f"[main] Suggestion sent for {entity_id}")

    # Also check sequence patterns
    # These are "A leads to B" patterns
    top_sequences = analyzer.get_top_sequences(min_count=MIN_OCCURRENCES)

    for sequence in top_sequences:
        # Build unique ID for this sequence suggestion
        seq_id = f"seq|{sequence['trigger']}|{sequence['action']}"

        if seq_id in sent_today:
            continue

        suggestion_text = suggester.generate_sequence_suggestion(sequence)

        ha.send_notification(
            title="🔗 Sequence Suggestion",
            message=suggestion_text,
            notification_id=seq_id
        )

        sent_today.add(seq_id)
        print(f"[main] Sequence suggestion sent: {seq_id}")


def reset_daily_tracker():
    """
    Clears the sent_today set at midnight.
    This allows suggestions to be sent again
    the next day.
    """
    sent_today.clear()
    print("[main] Daily suggestion tracker reset")


# ─────────────────────────────────────────
# SCHEDULER SETUP
# ─────────────────────────────────────────

def setup_schedule():
    """
    Sets up all scheduled tasks.
    schedule library runs tasks at the specified intervals.
    """
    # Learn patterns every min for testing
    schedule.every(1).minutes.do(learn_patterns)
    # Check and suggest every X minutes (from HA config)
    schedule.every(CHECK_INTERVAL).minutes.do(check_and_suggest)

    # Reset daily tracker at midnight
    schedule.every().day.at("00:00").do(reset_daily_tracker)

    print(f"[main] Schedule set up:")
    print(f"[main]   Learning    → every 1 min")
    print(f"[main]   Suggesting  → every {CHECK_INTERVAL} minutes")
    print(f"[main]   Daily reset → midnight")


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    try:
        print("[main] Cognitive Home starting...")
        print(f"[main] MIN_OCCURRENCES = {MIN_OCCURRENCES}")
        print(f"[main] CHECK_INTERVAL  = {CHECK_INTERVAL} minutes")

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