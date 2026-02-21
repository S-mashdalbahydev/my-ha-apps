#!/usr/bin/with-contenv bashio
bashio::log.info "Starting Mic Sound Detector..."
python3 /sound_monitor.py
```

---

**How to use it:**

1. Install the add-on and start it
2. Go to **Logs** in the add-on panel
3. Make noise near your mic — you should see lines like:
```
   [2024-01-15 10:32:05] 🔊 SOUND DETECTED! Level: 823