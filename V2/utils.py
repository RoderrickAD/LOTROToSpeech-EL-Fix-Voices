import json
import os
import datetime

CONFIG_FILE = "config.json"
MAPPING_FILE = "voice_mapping.json"
LOG_FILE = "app.log"

DEFAULT_CONFIG = {
    "api_key": "",
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "lotro_log_path": os.path.join(os.path.expanduser("~"), "Documents", "The Lord of the Rings Online", "Script.log"),
    "ocr_coords": [0, 0, 500, 200],
    "hotkey": "ctrl+alt+s"  # NEU: Standard-Hotkey
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            # Stelle sicher, dass neue Keys auch in alten Configs landen
            data = json.load(f)
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val
            return data
    except:
        return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)

def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        return {}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_mapping(mapping_data):
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping_data, f, indent=4)

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
