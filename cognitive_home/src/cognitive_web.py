import threading
from flask import Flask, request

app = Flask(__name__)

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

ha       = None
analyzer = None

pending_suggestions = {}
ingress_entry = ""

DAYS = {
    0: "Monday",   1: "Tuesday",  2: "Wednesday",
    3: "Thursday", 4: "Friday",   5: "Saturday",
    6: "Sunday"
}


def format_time(hour: int) -> str:
    if hour == 0:
        return "12:00 AM"
    elif hour < 12:
        return f"{hour}:00 AM"
    elif hour == 12:
        return "12:00 PM"
    else:
        return f"{hour - 12}:00 PM"


def friendly_name(entity_id: str) -> str:
    return entity_id.split(".")[-1].replace("_", " ").title()


def register_pending(suggestion_id: str, pattern: dict):
    pending_suggestions[suggestion_id] = pattern
    print(f"[cognitive_web] Registered: {suggestion_id}")


def _base_url() -> str:
    """
    Returns the correct base URL for links.
    When running through HA Ingress, links need the ingress prefix.
    When running directly, links are just /
    """
    if ingress_entry:
        return ingress_entry.rstrip("/")
    return ""


def _page(content: str, title: str = "Cognitive Home") -> str:
    """Base HTML wrapper with consistent styling."""
    base = _base_url()

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        <base href="{base}/">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont,
                             'Segoe UI', Roboto, Arial, sans-serif;
                background: #0b0b14;
                color: #e0e0e0;
                min-height: 100vh;
            }}

            header {{
                background: linear-gradient(135deg, #0f0f1a, #16213e);
                border-bottom: 1px solid #1e2d4a;
                padding: 20px 24px;
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            header .logo {{ font-size: 28px; }}

            header h1 {{
                font-size: 20px;
                color: #ffffff;
                font-weight: 600;
            }}

            header p {{
                font-size: 13px;
                color: #5a7a9a;
                margin-top: 2px;
            }}

            main {{
                max-width: 560px;
                margin: 0 auto;
                padding: 24px 16px;
            }}

            .empty {{
                text-align: center;
                padding: 60px 20px;
            }}
            .empty .icon {{ font-size: 56px; margin-bottom: 16px; }}
            .empty h2 {{
                font-size: 20px;
                color: #ffffff;
                margin-bottom: 8px;
            }}
            .empty p {{ color: #5a7a9a; font-size: 14px; line-height: 1.6; }}

            .card {{
                background: #13192b;
                border: 1px solid #1e2d4a;
                border-radius: 16px;
                padding: 22px;
                margin-bottom: 16px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            }}

            .card-header {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 18px;
            }}

            .card-header .badge {{ font-size: 22px; }}

            .card-header h2 {{
                font-size: 17px;
                font-weight: 600;
                color: #ffffff;
            }}

            .card-header .tag {{
                margin-left: auto;
                background: #1e3a5f;
                color: #5b9bd5;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 20px;
                font-weight: 500;
            }}

            .info-grid {{
                background: #0d1220;
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 16px;
            }}

            .info-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 11px 14px;
                border-bottom: 1px solid #1a2535;
                font-size: 14px;
            }}

            .info-row:last-child {{ border-bottom: none; }}
            .info-label {{ color: #5a7a9a; }}
            .info-value {{ color: #e0e0e0; font-weight: 500; }}

            .conf-bar {{
                height: 4px;
                background: #1a2535;
                border-radius: 2px;
                margin-top: 4px;
                overflow: hidden;
            }}
            .conf-fill {{
                height: 100%;
                background: linear-gradient(90deg, #1e6ef5, #00e676);
                border-radius: 2px;
            }}

            .question {{
                font-size: 14px;
                color: #8a9ab5;
                text-align: center;
                margin-bottom: 16px;
                line-height: 1.5;
            }}

            .buttons {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }}

            .btn {{
                padding: 13px 16px;
                border-radius: 10px;
                text-align: center;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
                letter-spacing: 0.3px;
                transition: transform 0.1s, opacity 0.2s;
                display: block;
            }}

            .btn:hover {{
                transform: translateY(-1px);
                opacity: 0.9;
            }}

            .btn-yes {{
                background: #0a3d24;
                color: #00e676;
                border: 1px solid #0d5c34;
            }}

            .btn-no {{
                background: #3d0a0a;
                color: #ff5252;
                border: 1px solid #5c0d0d;
            }}

            .result {{
                text-align: center;
                padding: 50px 20px;
            }}
            .result .icon {{ font-size: 64px; margin-bottom: 20px; }}
            .result h2 {{ font-size: 24px; margin-bottom: 10px; }}
            .result p {{
                color: #5a7a9a;
                font-size: 14px;
                line-height: 1.7;
                margin-bottom: 6px;
            }}
            .result strong {{ color: #e0e0e0; }}
            .result .back {{
                display: inline-block;
                margin-top: 28px;
                color: #1e6ef5;
                text-decoration: none;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo">🏠</div>
            <div>
                <h1>Cognitive Home</h1>
                <p>Smart automation suggestions</p>
            </div>
        </header>
        <main>
            {content}
        </main>
    </body>
    </html>
    """


@app.route("/")
def index():
    active = {
        sid: p for sid, p in pending_suggestions.items()
        if not p.get("confirmed", False)
    }

    if not active:
        content = """
        <div class="empty">
            <div class="icon">🔍</div>
            <h2>Learning your routines...</h2>
            <p>No suggestions yet. Toggle your devices a few times<br>
               and I'll start recognizing patterns.</p>
        </div>
        """
        return _page(content)

    cards = ""
    for sid, pattern in active.items():
        day_name = DAYS.get(pattern["weekday"], "regularly")
        entity   = friendly_name(pattern["entity_id"])
        time_str = format_time(pattern["hour"])
        occ      = pattern["occurrences"]
        conf     = int(pattern["confidence"] * 100)
        conf_pct = min(conf, 100)

        cards += f"""
        <div class="card">
            <div class="card-header">
                <span class="badge">💡</span>
                <h2>Suggested Automation</h2>
                <span class="tag">New</span>
            </div>

            <div class="info-grid">
                <div class="info-row">
                    <span class="info-label">Device</span>
                    <span class="info-value">{entity}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Usually at</span>
                    <span class="info-value">{time_str} · {day_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Times observed</span>
                    <span class="info-value">{occ} times</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Confidence</span>
                    <span class="info-value">
                        {conf}%
                        <div class="conf-bar">
                            <div class="conf-fill"
                                 style="width:{conf_pct}%"></div>
                        </div>
                    </span>
                </div>
            </div>

            <p class="question">
                Would you like me to automate this for you?
            </p>

            <div class="buttons">
                <a href="confirm/{sid}" class="btn btn-yes">
                    ✅ Yes, automate it
                </a>
                <a href="reject/{sid}" class="btn btn-no">
                    ❌ No thanks
                </a>
            </div>
        </div>
        """

    return _page(cards)


@app.route("/confirm/<path:suggestion_id>")
def confirm(suggestion_id: str):
    pattern = pending_suggestions.get(suggestion_id)

    if not pattern:
        content = """
        <div class="result">
            <div class="icon">⚠️</div>
            <h2 style="color:#f5a623">Already Handled</h2>
            <p>This suggestion has already been confirmed or dismissed.</p>
            <a href="./" class="back">← Back to suggestions</a>
        </div>
        """
        return _page(content, "Already Handled")

    entity_id = pattern["entity_id"]
    hour      = pattern["hour"]
    weekday   = pattern["weekday"]
    entity    = friendly_name(entity_id)
    time_str  = format_time(hour)
    day_name  = DAYS.get(weekday, "daily")

    print(f"[cognitive_web] User confirmed: {suggestion_id}")

    success = ha.create_automation(entity_id, hour, weekday)

    if success:
        analyzer.confirm_pattern(suggestion_id)
        ha.dismiss_notification(suggestion_id)
        del pending_suggestions[suggestion_id]

        content = f"""
        <div class="result">
            <div class="icon">✅</div>
            <h2 style="color:#00e676">Automation Created!</h2>
            <p><strong>{entity}</strong> will now turn on automatically</p>
            <p>every <strong>{day_name}</strong>
               at <strong>{time_str}</strong></p>
            <p style="margin-top:16px; color:#3a5a7a; font-size:13px">
                Settings → Automations → Cognitive Home: {entity}
            </p>
            <a href="./" class="back">← Back to suggestions</a>
        </div>
        """
        return _page(content, "Automation Created")
    else:
        content = """
        <div class="result">
            <div class="icon">❌</div>
            <h2 style="color:#ff5252">Something went wrong</h2>
            <p>Could not create the automation.</p>
            <p>Check the addon logs for details.</p>
            <a href="./" class="back">← Try again</a>
        </div>
        """
        return _page(content, "Error")


@app.route("/reject/<path:suggestion_id>")
def reject(suggestion_id: str):
    print(f"[cognitive_web] User rejected: {suggestion_id}")

    ha.dismiss_notification(suggestion_id)

    if suggestion_id in pending_suggestions:
        del pending_suggestions[suggestion_id]

    content = """
    <div class="result">
        <div class="icon">👍</div>
        <h2 style="color:#e0e0e0">Got it!</h2>
        <p>Suggestion dismissed.</p>
        <p>I'll keep learning your routines.</p>
        <a href="./" class="back">← Back to suggestions</a>
    </div>
    """
    return _page(content, "Dismissed")


@app.route("/reset")
def reset_patterns():
    """Wipes all learned patterns — use before a fresh demo."""
    analyzer.reset()
    pending_suggestions.clear()

    # Also clear sent_today in main
    try:
        import main as main_module
        main_module.sent_today.clear()
        print("[cognitive_web] sent_today cleared")
    except Exception:
        pass

    content = """
    <div class="result">
        <div class="icon">🔄</div>
        <h2 style="color:#00e676">Reset Complete</h2>
        <p>All learned patterns have been cleared.</p>
        <p>Toggle your devices to start fresh learning.</p>
        <a href="./" class="back">← Back to suggestions</a>
    </div>
    """
    return _page(content, "Reset")


def start_server(port: int = 8099):
    print(f"[cognitive_web] Starting on port {port}")
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False)
    )
    t.daemon = True
    t.start()
    print(f"[cognitive_web] Running at http://homeassistant.local:8099")
