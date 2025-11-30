import requests
import random
import globalVariables
import json

def fetch_elevenlabs_voices():
    """
    Holt alle verfügbaren Stimmen aus deinem Account und sortiert sie nach Geschlecht.
    """
    # Versuche den Key aus den globalVariables zu holen, sonst Hardcode fallback (bitte anpassen)
    api_key = getattr(globalVariables, 'elevenlabs_api_key', None)
    
    # Fallback: Wenn der Key nicht in globalVariables ist, muss er hier eingetragen werden:
    if not api_key:
        # HIER DEINEN API KEY EINTRAGEN, FALLS ER NICHT AUTOMATISCH GELADEN WIRD
        api_key = "DEIN_ELEVENLABS_API_KEY_HIER" 

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
        
        # Geschlechtsbestimmung über Labels oder Namen
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
    Wählt die beste Stimme basierend auf Name und Geschlecht.
    """
    if not voice_pool:
        return None

    # 1. PRIORITÄT: Exakter Namens-Match
    all_known_voices = voice_pool["male"] + voice_pool["female"] + voice_pool["generic"]
    for voice in all_known_voices:
        if npc_name.lower() in voice['name'].lower():
            print(f"Match! {npc_name} -> {voice['name']}")
            return voice['id']

    # 2. PRIORITÄT: Geschlecht
    selected_pool = []
    if npc_gender and npc_gender.lower() == "male":
        selected_pool = voice_pool["male"]
    elif npc_gender and npc_gender.lower() == "female":
        selected_pool = voice_pool["female"]
    
    if not selected_pool:
        selected_pool = voice_pool["generic"]
    
    if not selected_pool and all_known_voices:
        selected_pool = all_known_voices

    if selected_pool:
        # Wählt zufällig aus dem Pool (damit es variiert) oder nimm hash(npc_name) für Konsistenz
        # Konsistenz ist besser: Immer gleiche Stimme für gleichen NPC
        index = hash(npc_name) % len(selected_pool)
        return selected_pool[index]['id']
    
    return None
