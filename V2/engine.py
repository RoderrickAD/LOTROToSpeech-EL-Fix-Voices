import pytesseract
from PIL import ImageGrab
import requests
import hashlib
import os
import time
import pygame
import re
from utils import load_config, load_mapping, save_mapping, log_message

class VoiceEngine:
    def __init__(self):
        self.config = load_config()
        self.voices = []
        pygame.mixer.init()
        
        # Tesseract Pfad setzen
        pytesseract.pytesseract.tesseract_cmd = self.config.get("tesseract_path", "")

    def fetch_voices(self):
        """ Lädt Stimmen von ElevenLabs """
        api_key = self.config.get("api_key")
        if not api_key:
            return []

        try:
            headers = {"xi-api-key": api_key}
            response = requests.get("[https://api.elevenlabs.io/v1/voices](https://api.elevenlabs.io/v1/voices)", headers=headers)
            if response.status_code == 200:
                self.voices = response.json()['voices']
                log_message(f"{len(self.voices)} Stimmen von ElevenLabs geladen.")
                return self.voices
        except Exception as e:
            log_message(f"Fehler beim Laden der Stimmen: {e}")
        return []

    def get_npc_from_log(self):
        """ Liest das LOTRO Plugin Log """
        log_path = self.config.get("lotro_log_path")
        if not os.path.exists(log_path):
            return "Unknown", "Unknown"
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # Simpler Gender Check im Namen (Erweiterbar)
                    gender = "Male" # Default
                    if "female" in last_line.lower() or "frau" in last_line.lower(): # Beispiel Logik
                        gender = "Female"
                    return last_line, gender
        except:
            pass
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        """ Wählt Stimme intelligent aus """
        mapping = load_mapping()
        
        # 1. Gespeichert?
        if npc_name in mapping:
            return mapping[npc_name], "Gedächtnis"
        
        # 2. Namens-Match
        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                voice_id = v['voice_id']
                # Speichern
                mapping[npc_name] = voice_id
                save_mapping(mapping)
                return voice_id, "Namens-Match"

        # 3. MD5 Hash Auswahl (Stabil)
        if not self.voices:
            return None, "Keine Stimmen verfügbar"
            
        # Filtern nach Geschlecht (wenn möglich)
        filtered_voices = [v for v in self.voices if npc_gender.lower() in v.get('labels', {}).get('gender', '').lower()]
        if not filtered_voices:
            filtered_voices = self.voices

        hash_obj = hashlib.md5(npc_name.encode('utf-8'))
        index = int(hash_obj.hexdigest(), 16) % len(filtered_voices)
        selected = filtered_voices[index]
        
        # Speichern
        mapping[npc_name] = selected['voice_id']
        save_mapping(mapping)
        
        return selected['voice_id'], "Berechnet (Stabil)"

    def generate_and_play(self, text, npc_name):
        """ Erzeugt TTS und spielt es ab """
        npc_name_clean, gender = self.get_npc_from_log()
        
        # Wenn wir keinen Namen haben, nutzen wir den übergebenen oder OCR Text
        final_name = npc_name_clean if npc_name_clean != "Unknown" else "Unbekannter NPC"
        
        voice_id, method = self.select_voice(final_name, gender)
        
        if not voice_id:
            log_message("Keine Voice ID gefunden (API Key fehlt?).")
            return

        log_message(f"Spreche als: {final_name} (Methode: {method})")

        # Generierung
        api_key = self.config.get("api_key")
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        
        try:
            response = requests.post(
                f"[https://api.elevenlabs.io/v1/text-to-speech/](https://api.elevenlabs.io/v1/text-to-speech/){voice_id}",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                filename = "temp_audio.mp3"
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                log_message(f"ElevenLabs Fehler: {response.text}")
        except Exception as e:
            log_message(f"TTS Fehler: {e}")

    def run_ocr(self):
        """ Macht Screenshot und liest Text """
        coords = self.config.get("ocr_coords")
        try:
            img = ImageGrab.grab(bbox=(coords[0], coords[1], coords[2], coords[3]))
            text = pytesseract.image_to_string(img, lang='eng+deu') # Sprache anpassbar
            clean_text = re.sub(r'\s+', ' ', text).strip()
            return clean_text
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
