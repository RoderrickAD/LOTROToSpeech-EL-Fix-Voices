import pytesseract
from PIL import ImageGrab
import requests
import hashlib
import os
import time
import pygame
import re
import difflib # WICHTIG: Für den intelligenten Text-Vergleich
from utils import load_config, load_mapping, save_mapping, log_message

class VoiceEngine:
    def __init__(self):
        self.config = load_config()
        self.voices = []
        pygame.mixer.init()
        
        # Tesseract Pfad setzen (mit Fallback)
        tess_path = self.config.get("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = tess_path

    def is_new_text(self, new_text, old_text):
        """ 
        Prüft intelligent, ob der Text wirklich neu ist.
        Ignoriert kleine OCR-Fehler (z.B. fehlendes Komma).
        """
        # Ignoriere sehr kurze Texte (oft UI Müll oder Zahlen)
        if not new_text or len(new_text) < 15: 
            return False
            
        if not old_text:
            return True
            
        # Berechne Ähnlichkeit (0.0 bis 1.0)
        # Wenn der Text zu mehr als 85% identisch ist, behandeln wir ihn als "schon vorgelesen"
        ratio = difflib.SequenceMatcher(None, new_text, old_text).ratio()
        
        if ratio > 0.85:
            return False
            
        return True

    def fetch_voices(self):
        """ Lädt die Stimmen von ElevenLabs """
        api_key = self.config.get("api_key", "").strip()
        
        if not api_key:
            log_message("Kein API Key konfiguriert.")
            return []

        # WICHTIG: Saubere URL ohne Formatierungszeichen
        url = "https://api.elevenlabs.io/v1/voices"
        
        try:
            headers = {"xi-api-key": api_key}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.voices = data.get('voices', [])
                log_message(f"{len(self.voices)} Stimmen geladen.")
                return self.voices
            else:
                log_message(f"API Fehler beim Laden der Stimmen: {response.text}")
        except Exception as e:
            log_message(f"Verbindungsfehler: {e}")
        
        return []

    def get_npc_from_log(self):
        """ Versucht den NPC Namen aus der Script.log zu lesen """
        log_path = self.config.get("lotro_log_path", "")
        if not os.path.exists(log_path):
            return "Unknown", "Unknown"
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    gender = "Male"
                    lower = last_line.lower()
                    # Einfache Gender-Erkennung im Namen (kann erweitert werden)
                    if "female" in lower or "frau" in lower or "she" in lower:
                        gender = "Female"
                    return last_line, gender
        except:
            pass
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        """ Wählt die passendste Stimme aus """
        mapping = load_mapping()
        
        # 1. Gedächtnis prüfen
        if npc_name in mapping:
            saved_id = mapping[npc_name]
            # Validierung: Prüfen ob Stimme existiert (nur wenn wir online sind)
            if self.voices:
                valid_ids = [v['voice_id'] for v in self.voices]
                if saved_id in valid_ids:
                    return saved_id, "Gedächtnis"
            else:
                 return saved_id, "Gedächtnis (Offline)"

        if not self.voices:
            return None, "Fehler: Keine Stimmen geladen"

        # 2. Namens-Match (NPC Name ist Teil des Stimmennamens)
        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                vid = v['voice_id']
                mapping[npc_name] = vid
                save_mapping(mapping)
                return vid, "Namens-Match"

        # 3. Hash Auswahl (Stabil & nach Geschlecht)
        filtered = []
        target_gender = npc_gender.lower()
        
        for v in self.voices:
            # Labels sicher prüfen
            labels = v.get('labels') or {}
            g = labels.get('gender', '').lower()
            
            if target_gender == "female" and "female" in g: 
                filtered.append(v)
            elif target_gender == "male" and "male" in g and "female" not in g: 
                filtered.append(v)
        
        # Fallback auf alle Stimmen, wenn Filter leer
        if not filtered: 
            filtered = self.voices

        # MD5 Hash für stabile Auswahl
        hash_obj = hashlib.md5(npc_name.encode('utf-8'))
        idx = int(hash_obj.hexdigest(), 16) % len(filtered)
        selected = filtered[idx]
        
        # Speichern
        mapping[npc_name] = selected['voice_id']
        save_mapping(mapping)
        return selected['voice_id'], "Berechnet"

    def generate_and_play(self, text, npc_name_fallback="Unknown"):
        """ Holt Audio von ElevenLabs und spielt es ab """
        npc_log, gender = self.get_npc_from_log()
        
        # Bevorzuge den Namen aus dem Log, sonst Fallback
        final_name = npc_log if npc_log != "Unknown" else npc_name_fallback
        
        voice_id, method = self.select_voice(final_name, gender)
        
        if not voice_id:
            log_message("Keine Stimme gefunden (API Key oder Verbindung prüfen).")
            return

        log_message(f"Spreche: '{final_name}' ({method})")

        api_key = self.config.get("api_key", "").strip()
        
        try:
            headers = {
                "xi-api-key": api_key, 
                "Content-Type": "application/json"
            }
            data = {
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            
            # API Request
            tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            resp = requests.post(tts_url, headers=headers, json=data)
            
            if resp.status_code == 200:
                # Temporäre Datei
                filename = os.path.join(os.getcwd(), "temp_audio.mp3")
                with open(filename, "wb") as f:
                    f.write(resp.content)
                
                # Abspielen mit Pygame
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                log_message(f"TTS Fehler: {resp.text}")
        except Exception as e:
            log_message(f"Audio Fehler: {e}")

    def run_ocr(self):
        """ Screenshot machen und Text erkennen """
        coords = self.config.get("ocr_coords", [0, 0, 100, 100])
        try:
            bbox = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
            
            # Sicherheitscheck: Ist der Bereich groß genug?
            if bbox[2] - bbox[0] < 10 or bbox[3] - bbox[1] < 10: 
                return ""

            img = ImageGrab.grab(bbox=bbox)
            text = pytesseract.image_to_string(img, lang='eng+deu')
            
            # Bereinigung: Neue Zeilen weg, doppelte Leerzeichen weg
            clean = re.sub(r'\s+', ' ', text).strip()
            
            # Filter: Ignoriere Texte, die wie reiner UI-Müll aussehen
            # (z.B. nur Zahlen oder extrem kurz < 10 Zeichen)
            if len(clean) < 10: 
                return ""
                
            return clean
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
