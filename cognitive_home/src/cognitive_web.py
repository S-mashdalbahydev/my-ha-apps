import json
import os
import threading
from flask import Flask, request, jsonify
from ha_client import HAClient
from pattern_analyzer import PatternAnalyzer

app = Flask(__name__)
ha = HAClient()
analyzer = PatternAnalyzer()

# Stores pending suggestions waiting for confirmation
# key   → suggestion_id e.g. "climate.ac|18|0"
# value → full pattern dict
pending_suggestions = {}


def register_pending(suggestion_id: str, pattern: dict):
    """
    Called from main.py when a suggestion is sent.
    Stores the pattern so the web server can act on it
    when the user confirms.
    """
    pending_suggestions[suggestion_id] = pattern
    print(f"[web_server] Registered pending: {suggestion_id}")


@app.route("/")
def index():
    """
    Main page — shows all pending suggestions
    with Yes/No buttons for each one.
    """
    if not pending_suggestions:
        return """
        <html>
        <head>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <style>
                body { font-family: Arial; padding: 20px;
                       background: #1a1a2e; color: white; text-align: center; }
                h2   { color: #e94560; }
            </style>
        </head>
        <body>
            <h2>🏠 Cognitive Home</h2>
            <p>No pending suggestions right now.</p>
            <p>Check back after the system detects a pattern!</p>
        </body>
        </html>
        """

    # Build a card for each pending suggestion
    cards = ""
    for sid, pattern in pending_suggestions.items():
        days = {
            0: "Monday", 1: "Tuesday", 2: "Wednesday",
            3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
        }
        day_name = days.get(pattern["weekday"], "unknown")
        entity   = pattern["entity_id"]
        hour     = pattern["hour"]
        occ      = pattern["occurrences"]
        conf     = int(pattern["confidence"] * 100)

        cards += f"""
        <div class='card'>
            <h3>💡 Smart Suggestion</h3>
            <p>Device: <strong>{entity}</strong></p>
            <p>Usually activated at: <strong>{hour:02d}:00</strong></p>
            <p>Day: <strong>{day_name}</strong></p>
            <p>Seen <strong>{occ}</strong> times
               ({conf}% confidence)</p>
            <div class='buttons'>
                <a href='/confirm/{sid}' class='btn yes'>
                    ✅ Yes, automate it
                </a>
                <a href='/reject/{sid}' class='btn no'>
                    ❌ No thanks
                </a>
            </div>
        </div>
        """

    return f"""
    <html>
    <head>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{
                font-family: Arial;
                padding: 20px;
                background: #1a1a2e;
                color: white;
            }}
            h2 {{
                color: #e94560;
                text-align: center;
            }}
            .card {{
                background: #16213e;
                border-radius: 12px;
                padding: 20px;
                margin: 20px auto;
                max-width: 500px;
                border: 1px solid #e94560;
            }}
            .buttons {{
                display: flex;
                gap: 10px;
                margin-top: 15px;
            }}
            .btn {{
                flex: 1;
                padding: 12px;
                border-radius: 8px;
                text-align: center;
                text-decoration: none;
                font-weight: bold;
                font-size: 16px;
            }}
            .yes {{ background: #0f3460; color: #00ff88; }}
            .no  {{ background: #3d0000; color: #ff4444; }}
        </style>
    </head>
    <body>
        <h2>🏠 Cognitive Home</h2>
        {cards}
    </body>
    </html>
    """


@app.route("/confirm/<path:suggestion_id>")
def confirm(suggestion_id: str):
    """
    User clicked YES.
    1. Get the pattern from pending
    2. Create the automation in HA
    3. Mark pattern as confirmed
    4. Dismiss the HA notification
    5. Show success page
    """
    pattern = pending_suggestions.get(suggestion_id)

    if not pattern:
        return "<h2 style='color:red'>Suggestion not found or already handled.</h2>"

    entity_id = pattern["entity_id"]
    hour      = pattern["hour"]
    weekday   = pattern["weekday"]

    print(f"[web_server] User confirmed: {suggestion_id}")

    # Create the real automation in HA
    success = ha.create_automation(entity_id, hour, weekday)

    if success:
        # Mark as confirmed in pattern_analyzer
        analyzer.confirm_pattern(suggestion_id)

        # Dismiss the HA notification
        ha.dismiss_notification(suggestion_id)

        # Remove from pending
        del pending_suggestions[suggestion_id]

        return f"""
        <html>
        <head>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <style>
                body {{ font-family: Arial; padding: 40px;
                        background: #1a1a2e; color: white; text-align: center; }}
                h2   {{ color: #00ff88; }}
            </style>
        </head>
        <body>
            <h2>✅ Automation Created!</h2>
            <p><strong>{entity_id}</strong> will now
               turn on automatically at <strong>{hour:02d}:00</strong>.</p>
            <p>You can find it in HA under
               Settings → Automations.</p>
            <br>
            <a href='/' style='color: #e94560'>← Back to suggestions</a>
        </body>
        </html>
        """
    else:
        return """
        <html>
        <body style='background:#1a1a2e; color:white;
                     font-family:Arial; padding:40px; text-align:center'>
            <h2 style='color:red'>❌ Failed to create automation</h2>
            <p>Check the addon logs for details.</p>
            <a href='/' style='color:#e94560'>← Back</a>
        </body>
        </html>
        """


@app.route("/reject/<path:suggestion_id>")
def reject(suggestion_id: str):
    """
    User clicked NO.
    1. Dismiss the HA notification
    2. Remove from pending
    3. Show thank you page
    """
    print(f"[web_server] User rejected: {suggestion_id}")

    ha.dismiss_notification(suggestion_id)

    if suggestion_id in pending_suggestions:
        del pending_suggestions[suggestion_id]

    return """
    <html>
    <head>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{ font-family: Arial; padding: 40px;
                    background: #1a1a2e; color: white; text-align: center; }}
        </style>
    </head>
    <body>
        <h2>👍 Got it!</h2>
        <p>Suggestion dismissed. I'll keep learning your patterns.</p>
        <br>
        <a href='/' style='color: #e94560'>← Back to suggestions</a>
    </body>
    </html>
    """


def start_server(port: int = 8099):
    """
    Starts the Flask server in a background thread
    so it doesn't block main.py
    """
    print(f"[web_server] Starting on port {port}")
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False)
    )
    t.daemon = True
    t.start()
    print(f"[web_server] Running at http://homeassistant.local:8099")