import threading
from flask import Flask

app = Flask(__name__)

ha       = None
analyzer = None

pending_suggestions = {}

DAYS = {
    0: "Monday",   1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday",  5: "Saturday",
    6: "Sunday"
}


def _format_time(hour: int) -> str:
    """Converts 24h hour to friendly 12h format."""
    if hour == 0:
        return "12:00 AM"
    elif hour < 12:
        return f"{hour}:00 AM"
    elif hour == 12:
        return "12:00 PM"
    else:
        return f"{hour - 12}:00 PM"


def register_pending(suggestion_id: str, pattern: dict):
    pending_suggestions[suggestion_id] = pattern
    print(f"[cognitive_web] Registered pending: {suggestion_id}")


@app.route("/")
def index():
    if not pending_suggestions:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <title>Cognitive Home</title>
            <style>
                * { box-sizing: border-box; margin: 0; padding: 0; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont,
                                 'Segoe UI', Arial, sans-serif;
                    background: #0f0f1a;
                    color: #e0e0e0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-direction: column;
                    padding: 20px;
                    text-align: center;
                }
                .icon { font-size: 64px; margin-bottom: 20px; }
                h1 { color: #e94560; font-size: 28px; margin-bottom: 10px; }
                p  { color: #888; font-size: 16px; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class='icon'>🏠</div>
            <h1>Cognitive Home</h1>
            <p>No pending suggestions right now.</p>
            <p>I'm still learning your routines.<br>
               Check back soon!</p>
        </body>
        </html>
        """

    cards = ""
    for sid, pattern in pending_suggestions.items():
        day_name  = DAYS.get(pattern["weekday"], "unknown")
        entity    = pattern["entity_id"].split(".")[-1].replace("_", " ").title()
        time_str  = _format_time(pattern["hour"])
        occ       = pattern["occurrences"]
        conf      = int(pattern["confidence"] * 100)

        cards += f"""
        <div class='card'>
            <div class='card-icon'>💡</div>
            <h2>Smart Suggestion</h2>
            <div class='detail'>
                <div class='detail-row'>
                    <span class='label'>Device</span>
                    <span class='value'>{entity}</span>
                </div>
                <div class='detail-row'>
                    <span class='label'>Usually at</span>
                    <span class='value'>{time_str} on {day_name}</span>
                </div>
                <div class='detail-row'>
                    <span class='label'>Seen</span>
                    <span class='value'>{occ} times ({conf}% confidence)</span>
                </div>
            </div>
            <p class='question'>
                Want me to automate this for you?
            </p>
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
    <!DOCTYPE html>
    <html>
    <head>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <title>Cognitive Home</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont,
                             'Segoe UI', Arial, sans-serif;
                background: #0f0f1a;
                color: #e0e0e0;
                min-height: 100vh;
                padding: 20px;
            }}
            header {{
                text-align: center;
                padding: 30px 0 20px;
            }}
            header h1 {{
                color: #e94560;
                font-size: 28px;
                margin-bottom: 6px;
            }}
            header p {{
                color: #666;
                font-size: 14px;
            }}
            .card {{
                background: #16213e;
                border-radius: 16px;
                padding: 24px;
                margin: 16px auto;
                max-width: 480px;
                border: 1px solid #1a2a4a;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }}
            .card-icon {{
                font-size: 36px;
                margin-bottom: 12px;
                text-align: center;
            }}
            h2 {{
                text-align: center;
                font-size: 20px;
                color: #ffffff;
                margin-bottom: 16px;
            }}
            .detail {{
                background: #0f1929;
                border-radius: 10px;
                padding: 14px;
                margin-bottom: 16px;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 6px 0;
                border-bottom: 1px solid #1a2a3a;
                font-size: 14px;
            }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ color: #888; }}
            .value {{ color: #e0e0e0; font-weight: 500; }}
            .question {{
                text-align: center;
                color: #aaa;
                font-size: 15px;
                margin-bottom: 16px;
            }}
            .buttons {{
                display: flex;
                gap: 10px;
            }}
            .btn {{
                flex: 1;
                padding: 14px;
                border-radius: 10px;
                text-align: center;
                text-decoration: none;
                font-weight: 600;
                font-size: 15px;
                transition: opacity 0.2s;
            }}
            .btn:hover {{ opacity: 0.85; }}
            .yes {{ background: #0d4f35; color: #00e676; }}
            .no  {{ background: #4f0d0d; color: #ff5252; }}
        </style>
    </head>
    <body>
        <header>
            <h1>🏠 Cognitive Home</h1>
            <p>I've noticed some patterns in your home routine</p>
        </header>
        {cards}
    </body>
    </html>
    """


@app.route("/confirm/<path:suggestion_id>")
def confirm(suggestion_id: str):
    pattern = pending_suggestions.get(suggestion_id)

    if not pattern:
        return _simple_page(
            "⚠️ Not Found",
            "This suggestion has already been handled.",
            "#e94560"
        )

    entity_id = pattern["entity_id"]
    hour      = pattern["hour"]
    weekday   = pattern["weekday"]
    entity    = entity_id.split(".")[-1].replace("_", " ").title()
    time_str  = _format_time(hour)
    day_name  = DAYS.get(weekday, "daily")

    print(f"[cognitive_web] User confirmed: {suggestion_id}")

    success = ha.create_automation(entity_id, hour, weekday)

    if success:
        analyzer.confirm_pattern(suggestion_id)
        ha.dismiss_notification(suggestion_id)
        del pending_suggestions[suggestion_id]

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <title>Automation Created</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont,
                                 'Segoe UI', Arial, sans-serif;
                    background: #0f0f1a;
                    color: #e0e0e0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-direction: column;
                    padding: 30px;
                    text-align: center;
                }}
                .icon  {{ font-size: 72px; margin-bottom: 24px; }}
                h1     {{ color: #00e676; font-size: 26px; margin-bottom: 12px; }}
                p      {{ color: #aaa; font-size: 15px;
                          line-height: 1.7; margin-bottom: 8px; }}
                strong {{ color: #ffffff; }}
                .back  {{
                    margin-top: 30px;
                    color: #e94560;
                    text-decoration: none;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class='icon'>✅</div>
            <h1>Automation Created!</h1>
            <p><strong>{entity}</strong> will now turn on automatically</p>
            <p>every <strong>{day_name}</strong> at <strong>{time_str}</strong></p>
            <p style='margin-top:16px; color:#666; font-size:13px'>
                Find it in HA → Settings → Automations
            </p>
            <a href='/' class='back'>← Back to suggestions</a>
        </body>
        </html>
        """
    else:
        return _simple_page(
            "❌ Failed",
            "Could not create the automation. Check addon logs.",
            "#ff5252"
        )


@app.route("/reject/<path:suggestion_id>")
def reject(suggestion_id: str):
    print(f"[cognitive_web] User rejected: {suggestion_id}")

    ha.dismiss_notification(suggestion_id)

    if suggestion_id in pending_suggestions:
        del pending_suggestions[suggestion_id]

    return _simple_page(
        "👍 Got it!",
        "Suggestion dismissed. I'll keep learning your routines.",
        "#e0e0e0"
    )


def _simple_page(title: str, message: str, color: str) -> str:
    """Helper for simple one-message pages."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont,
                             'Segoe UI', Arial, sans-serif;
                background: #0f0f1a;
                color: #e0e0e0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                padding: 30px;
                text-align: center;
            }}
            h1  {{ color: {color}; font-size: 26px; margin-bottom: 12px; }}
            p   {{ color: #888; font-size: 15px; }}
            a   {{ margin-top: 24px; color: #e94560;
                   text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        <p>{message}</p>
        <a href='/'>← Back to suggestions</a>
    </body>
    </html>
    """


def start_server(port: int = 8099):
    print(f"[cognitive_web] Starting on port {port}")
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False)
    )
    t.daemon = True
    t.start()
    print(f"[cognitive_web] Running at http://homeassistant.local:8099")
