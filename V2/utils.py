import json
import os
import datetime

CONFIG_FILE = "config.json"
# MAPPING_FILE wurde entfernt, da das Mapping nicht mehr direkt über UI verwaltet wird.
LOG_FILE = "app.log"

DEFAULT_CONFIG = {
    "api_key": "",
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "lotro_log_path": os.path.join(os.path.expanduser("~"), "Documents", "The Lord of the Rings Online", "Script.log"),
    "ocr_coords": None, # None bedeutet: Ganzer Monitor wird gescannt
    "hotkey": "ctrl+alt+s",
    "monitor_index": 1, # 1 = Hauptmonitor
    "audio_delay": 0.5,  # Sekunden Pause vor Sprachausgabe
    "debug_mode": False # Neu: Schaltet das Speichern von Debug-Bildern (last_detection_debug.png)
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Fehlende Keys mit Defaults ergänzen
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val
            return data
    except:
        return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)

# load_mapping und save_mapping entfernt

def log_message(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except:
        pass
    return entry
