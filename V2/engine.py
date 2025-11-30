import pytesseract
import requests
import hashlib
import os
import time
import pygame
import re
import difflib
import cv2
import numpy as np
import mss 
from utils import load_config, load_mapping, save_mapping, log_message

class VoiceEngine:
    def __init__(self):
        self.config = load_config()
        self.voices = []
        pygame.mixer.init()
        
        # Audio Cache Ordner erstellen
        self.cache_dir = os.path.join(os.getcwd(), "AudioCache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # Tesseract Pfad setzen
        tess_path = self.config.get("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = tess_path
        
        # WICHTIG: Wir initialisieren mss hier NICHT global,
        # sondern lokal in der Screenshot-Funktion, um Thread-Fehler zu vermeiden.

    def is_new_text(self, new_text, old_text):
        if not new_text or len(new_text) < 15: return False
        if not old_text: return True
        # Wenn Text zu > 85% gleich ist, ignorieren
        ratio = difflib.SequenceMatcher(None, new_text, old_text).ratio()
        return ratio <= 0.85

    def fetch_voices(self):
        api_key = self.config.get("api_key", "").strip()
        if not api_key: return []
        try:
            headers = {"xi-api-key": api_key}
            resp = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
            if resp.status_code == 200:
                self.voices = resp.json().get('voices', [])
                log_message(f"{len(self.voices)} Stimmen geladen.")
                return self.voices
        except: pass
        return []

    def get_npc_from_log(self):
        try:
            path = self.config.get("lotro_log_path", "")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    if lines:
                        last = lines[-1].strip()
                        gender = "Female" if any(x in last.lower() for x in ["female", "frau", "she"]) else "Male"
                        return last, gender
        except: pass
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        mapping = load_mapping()
        if npc_name in mapping:
            if not self.voices or mapping[npc_name] in [v['voice_id'] for v in self.voices]:
                return mapping[npc_name], "Gedächtnis"

        if not self.voices: return None, "Keine Stimmen"

        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                mapping[npc_name] = v['voice_id']
                save_mapping(mapping)
                return v['voice_id'], "Namens-Match"

        filtered = [v for v in self.voices if npc_gender.lower() in v.get('labels', {}).get('gender', '').lower()]
        if not filtered: filtered = self.voices
        
        idx = int(hashlib.md5(npc_name.encode('utf-8')).hexdigest(), 16) % len(filtered)
        vid = filtered[idx]['voice_id']
        mapping[npc_name] = vid
        save_mapping(mapping)
        return vid, "Berechnet"

    def generate_and_play(self, text, npc_name_fallback="Unknown"):
        delay = float(self.config.get("audio_delay", 0.5))
        if delay > 0: time.sleep(delay)

        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"quest_{text_hash}.mp3")

        if os.path.exists(cache_file):
            log_message("Spiele aus Cache...")
            self.play_audio_file(cache_file)
            return

        npc_log, gender = self.get_npc_from_log()
        name = npc_log if npc_log != "Unknown" else npc_name_fallback
        vid, method = self.select_voice(name, gender)
        
        if not vid: return

        log_message(f"Generiere neu: '{name}' ({method})")
        try:
            headers = {"xi-api-key": self.config.get("api_key", ""), "Content-Type": "application/json"}
            data = {"text": text, "model_id": "eleven_turbo_v2_5", "voice_settings": {"stability": 0.5}}
            resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", headers=headers, json=data)
            
            if resp.status_code == 200:
                with open(cache_file, "wb") as f: f.write(resp.content)
                self.play_audio_file(cache_file)
            else:
                log_message(f"API Fehler: {resp.text}")
        except Exception as e:
            log_message(f"TTS Fehler: {e}")

    def play_audio_file(self, filepath):
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
        except: pass

    def get_monitor_screenshot(self):
        """ Holt Bild vom gewählten Monitor (Thread-Safe Fix) """
        mon_idx = int(self.config.get("monitor_index", 1))
        try:
            # FIX: with mss.mss() erstellt eine neue Instanz pro Aufruf -> Thread Safe!
            with mss.mss() as sct:
                if mon_idx >= len(sct.monitors): mon_idx = 1
                monitor = sct.monitors[mon_idx]
                
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                return img
        except Exception as e:
            log_message(f"Screenshot Fehler: {e}")
            return None

    def auto_find_quest_text(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 10))
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours: return img

        valid_cnts = [c for c in contours if cv2.contourArea(c) > 5000]
        if not valid_cnts: return img

        largest = max(valid_cnts, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        
        pad = 15
        h_img, w_img = img.shape[:2]
        x1, y1 = max(0, x-pad), max(0, y-pad)
        x2, y2 = min(w_img, x+w+pad), min(h_img, y+h+pad)
        
        cropped = img[y1:y2, x1:x2]
        cv2.imwrite("last_detection_debug.png", cropped) 
        return cropped

    def run_ocr(self):
        try:
            img = self.get_monitor_screenshot()
            if img is None: return ""

            optimized_img = self.auto_find_quest_text(img)
            
            gray = cv2.cvtColor(optimized_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(thresh, config=config, lang='eng+deu')
            
            return re.sub(r'\s+', ' ', text).strip()
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
