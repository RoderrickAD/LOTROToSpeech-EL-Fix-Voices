import requests
import random
import globalVariables
import json
import datetime
import os
import hashlib

# --- KONFIGURATION ---
LOG_FILE = "assigned_voices.txt"
MAPPING_FILE = "npc_voice_mapping.json"

# --- HILFSFUNKTIONEN FÜR DAS GEDÄCHTNIS ---

def log_voice_assignment(npc_name, method, voice_name):
    """ Schreibt die Entscheidung in ein Logbuch für den Nutzer. """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] NPC: '{npc_name}' -> Stimme: '{voice_name}' (Grund: {method})\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"Log: {log_entry.strip()}")
    except Exception as e:
        print(f"Konnte Log nicht schreiben: {e}")

def load_saved_mapping():
    """ Lädt die gespeicherten Zuweisungen aus der JSON-Datei. """
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden der Mapping-Datei: {e}")
            return {}
    return {}

def save_mapping_entry(npc_name, voice_id):
    """ Speichert eine neue Zuweisung dauerhaft in der JSON-Datei ab. """
    current_mapping = load_saved_mapping()
    
    # Nur speichern, wenn sich wirklich was geändert hat (schont die Festplatte)
    if current_mapping.get(npc_name) != voice_id:
        current_mapping[npc_name] = voice_id
        try:
            with open(MAPPING_FILE, "w", encoding="utf-8") as f:
                json.dump(current_mapping, f, indent=4, ensure_ascii=False)
            print(f"Gedächtnis aktualisiert: {npc_name} wurde gespeichert.")
        except Exception as e:
            print(f"Konnte Mapping nicht speichern: {e}")

def get_stable_hash_index(text, list_length):
    """ 
    Erzeugt einen Index, der auch nach Neustarts immer GLEICH bleibt.
    Python's normales hash() ändert sich bei jedem Neustart, MD5 nicht.
    """
    hash_obj = hashlib.md5(text.encode('utf-8'))
    hex_dig = hash_obj.hexdigest()
    # Wandle Hex in Zahl um und nimm Modulo der Listenlänge
    return int(hex_dig, 16) % list_length

# --- HAUPTFUNKTIONEN ---

def fetch_elevenlabs_voices():
    """ Holt alle verfügbaren Stimmen aus deinem Account und sortiert sie. """
    
    # 1. Versuche Key aus globalVariables
    api_key = getattr(globalVariables, 'elevenlabs_api_key', None)
    
    # 2. Fallback: Versuche Key aus Datei zu lesen, falls Variable leer
    if not api_key:
        try:
            from globalVariables import config_path
            key_file = os.path.join(config_path, "api_key.txt")
            if os.path.exists(key_file):
                with open(key_file, "r") as f:
                    api_key = f.read().strip()
        except:
            pass

    if not api_key:
        print("ElevenLabs Manager: Kein API Key gefunden!")
        return None

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Fehler beim Abrufen der Stimmen: {response.text}")
            return None

        all_voices = response.json()['voices']
    except Exception as e:
        print(f"Kritischer Fehler bei ElevenLabs Verbindung: {e}")
        return None
    
    voice_pool = {
        "male": [],
        "female": [],
        "generic": []
    }

    print(f"ElevenLabs Manager: {len(all_voices)} Stimmen geladen. Sortiere...")

    for voice in all_voices:
        voice_data = {"name": voice['name'], "id": voice['voice_id']}
        
        labels = voice.get('labels', {})
        gender = labels.get('gender', '').lower() if labels else ""
        name_lower = voice['name'].lower()
        
        if 'male' in gender and 'female' not in gender:
            voice_pool["male"].append(voice_data)
        elif 'female' in gender:
            voice_pool["female"].append(voice_data)
        else:
            # Fallback auf Namen
            if "male" in name_lower:
                 voice_pool["male"].append(voice_data)
            elif "female" in name_lower:
                 voice_pool["female"].append(voice_data)
            else:
                voice_pool["generic"].append(voice_data)

    return voice_pool

def get_voice_for_npc(npc_name, npc_gender, voice_pool):
    """
    Wählt die beste Stimme. 
    Reihenfolge: 
    1. Gespeicherter Eintrag (JSON)
    2. Namens-Match (Stimme heißt wie NPC)
    3. Stabile Zuweisung nach Geschlecht (MD5 Hash)
    """
    if not voice_pool:
        return None

    npc_name = str(npc_name).strip()
    
    # --- SCHRITT 1: Gedächtnis prüfen ---
    saved_map = load_saved_mapping()
    if npc_name in saved_map:
        saved_id = saved_map[npc_name]
        
        # Sicherheitscheck: Gibt es die Stimme noch?
        all_ids = [v['id'] for cat in voice_pool.values() for v in cat]
        
        if saved_id in all_ids:
            # Name der Stimme für das Log finden
            voice_name = "Unbekannt"
            for cat in voice_pool.values():
                for v in cat:
                    if v['id'] == saved_id: voice_name = v['name']
            
            print(f"Lade gespeicherte Stimme für '{npc_name}'")
            return saved_id

    # --- SCHRITT 2: Namens-Match (Neu) ---
    all_known_voices = voice_pool["male"] + voice_pool["female"] + voice_pool["generic"]
    for voice in all_known_voices:
        if npc_name.lower() in voice['name'].lower():
            log_voice_assignment(npc_name, "Namens-Match (Stimme heißt wie NPC)", voice['name'])
            save_mapping_entry(npc_name, voice['id']) # Speichern für Zukunft
            return voice['id']

    # --- SCHRITT 3: Geschlecht & Stabile Auswahl ---
    selected_pool = []
    method_name = "Fallback"
    
    # Robustere Prüfung des Geschlechts-Strings
    g_str = str(npc_gender).lower()
    
    if "male" in g_str and "female" not in g_str:
        selected_pool = voice_pool["male"]
        method_name = "Male Pool"
    elif "female" in g_str:
        selected_pool = voice_pool["female"]
        method_name = "Female Pool"
    
    # Wenn leer, versuche Generic
    if not selected_pool:
        selected_pool = voice_pool["generic"]
        method_name = "Generic Pool"
    
    # Wenn immer noch leer, nimm alle
    if not selected_pool and all_known_voices:
        selected_pool = all_known_voices
        method_name = "Notfall Pool (Alle)"

    if selected_pool:
        # WICHTIG: Stabile Auswahl mit MD5 statt random/hash()
        index = get_stable_hash_index(npc_name, len(selected_pool))
        chosen_voice = selected_pool[index]
        
        log_voice_assignment(npc_name, f"Berechnet ({method_name})", chosen_voice['name'])
        save_mapping_entry(npc_name, chosen_voice['id']) # Speichern für Zukunft
        return chosen_voice['id']
    
    return None
