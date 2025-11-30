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
        tess_path = self.config.get("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = tess_path

    def fetch_voices(self):
        """ Lädt Stimmen von ElevenLabs """
        api_key = self.config.get("api_key", "").strip() # .strip() entfernt versehentliche Leerzeichen
        
        if not api_key:
            log_message("Kein API Key in den Einstellungen gefunden.")
            return []

        # WICHTIG: Hier muss die URL absolut sauber stehen, ohne Klammern []
        url = "https://api.elevenlabs.io/v1/voices"
        
        try:
            headers = {"xi-api-key": api_key}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.voices = data.get('voices', [])
                log_message(f"{len(self.voices)} Stimmen erfolgreich geladen.")
                return self.voices
            else:
                log_message(f"Fehler beim Laden der Stimmen (Code {response.status_code}): {response.text}")
        except Exception as e:
            log_message(f"Kritischer Verbindungsfehler: {e}")
        
        return []

    def get_npc_from_log(self):
        """ Liest das LOTRO Plugin Log """
        log_path = self.config.get("lotro_log_path", "")
        if not os.path.exists(log_path):
            return "Unknown", "Unknown"
        
        try:
            # 'utf-8' mit 'ignore' verhindert Abstürze bei Sonderzeichen
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # Simpler Gender Check im Namen
                    gender = "Male"
                    lower_line = last_line.lower()
                    if "female" in lower_line or "frau" in lower_line or "she" in lower_line:
                        gender = "Female"
                    return last_line, gender
        except Exception as e:
            # Fehler hier nicht loggen, um Spam zu vermeiden, nur leise abfangen
            pass
            
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        """ Wählt Stimme intelligent aus """
        mapping = load_mapping()
        
        # 1. Gespeichert?
        if npc_name in mapping:
            # Prüfen ob die gespeicherte Stimme noch existiert (Validierung)
            saved_id = mapping[npc_name]
            # Wenn wir Stimmen geladen haben, prüfen wir, ob die ID noch gültig ist
            if self.voices:
                valid_ids = [v['voice_id'] for v in self.voices]
                if saved_id in valid_ids:
                    return saved_id, "Gedächtnis"
            else:
                # Wenn Offline/Fehler, vertrauen wir dem Gedächtnis einfach
                return saved_id, "Gedächtnis (Offline)"
        
        # Falls keine Stimmen geladen wurden (wegen API Fehler), abbrechen
        if not self.voices:
            return None, "Keine Stimmen verfügbar (API Fehler?)"

        # 2. Namens-Match
        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                voice_id = v['voice_id']
                mapping[npc_name] = voice_id
                save_mapping(mapping)
                return voice_id, "Namens-Match"

        # 3. MD5 Hash Auswahl (Stabil)
        # Filtern nach Geschlecht (wenn möglich)
        filtered_voices = []
        target_gender = npc_gender.lower()
        
        for v in self.voices:
            # Labels sicherheitshalber prüfen
            labels = v.get('labels') or {}
            v_gender = labels.get('gender', '').lower()
            
            if target_gender == "female" and "female" in v_gender:
                filtered_voices.append(v)
            elif target_gender == "male" and "male" in v_gender and "female" not in v_gender:
                filtered_voices.append(v)
        
        # Fallback: Wenn Filter leer ist (oder Gender unbekannt), nimm alle
        if not filtered_voices:
            filtered_voices = self.voices

        # Konsistente Auswahl per Hash
        hash_obj = hashlib.md5(npc_name.encode('utf-8'))
        index = int(hash_obj.hexdigest(), 16) % len(filtered_voices)
        selected = filtered_voices[index]
        
        # Speichern
        mapping[npc_name] = selected['voice_id']
        save_mapping(mapping)
        
        return selected['voice_id'], "Berechnet (Stabil)"

    def generate_and_play(self, text, npc_name_fallback="Unknown"):
        """ Erzeugt TTS und spielt es ab """
        npc_name_log, gender = self.get_npc_from_log()
        
        # Wir bevorzugen den Namen aus dem Log, falls vorhanden
        if npc_name_log and npc_name_log != "Unknown":
            final_name = npc_name_log
        else:
            final_name = npc_name_fallback
        
        voice_id, method = self.select_voice(final_name, gender)
        
        if not voice_id:
            log_message("Abbruch: Keine Voice ID ermittelt (API Key prüfen oder Stimmen nicht geladen).")
            return

        log_message(f"Spreche als: '{final_name}' (Stimme via {method})")

        api_key = self.config.get("api_key", "").strip()
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Sprachmodell Einstellungen
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        try:
            response = requests.post(tts_url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Temporäre Datei sicher speichern
                filename = os.path.join(os.getcwd(), "temp_audio.mp3")
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                # Abspielen
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
                
                # Optional: Datei danach löschen oder behalten (hier: behalten wir sie kurz)
            else:
                log_message(f"ElevenLabs TTS Fehler: {response.text}")
        except Exception as e:
            log_message(f"Audio Fehler: {e}")

    def run_ocr(self):
        """ Macht Screenshot und liest Text """
        coords = self.config.get("ocr_coords", [0, 0, 100, 100])
        try:
            # Sicherstellen, dass Koordinaten Integer sind
            bbox = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
            
            # Prüfen ob Bereich groß genug ist
            if bbox[2] - bbox[0] < 10 or bbox[3] - bbox[1] < 10:
                return ""

            img = ImageGrab.grab(bbox=bbox)
            text = pytesseract.image_to_string(img, lang='eng+deu') 
            
            # Bereinigung: Zeilenumbrüche zu Leerzeichen
            clean_text = re.sub(r'\s+', ' ', text).strip()
            return clean_text
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
