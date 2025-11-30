import pytesseract
from PIL import ImageGrab
import requests
import hashlib
import os
import time
import pygame
import re
import difflib
import cv2
import numpy as np
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

    def is_new_text(self, new_text, old_text):
        if not new_text or len(new_text) < 15: 
            return False
        if not old_text:
            return True
        ratio = difflib.SequenceMatcher(None, new_text, old_text).ratio()
        if ratio > 0.85:
            return False
        return True

    def fetch_voices(self):
        api_key = self.config.get("api_key", "").strip()
        if not api_key:
            log_message("Kein API Key konfiguriert.")
            return []

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
                log_message(f"API Fehler: {response.text}")
        except Exception as e:
            log_message(f"Verbindungsfehler: {e}")
        return []

    def get_npc_from_log(self):
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
                    if "female" in lower or "frau" in lower or "she" in lower:
                        gender = "Female"
                    return last_line, gender
        except:
            pass
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        mapping = load_mapping()
        if npc_name in mapping:
            saved_id = mapping[npc_name]
            if self.voices:
                valid_ids = [v['voice_id'] for v in self.voices]
                if saved_id in valid_ids:
                    return saved_id, "Gedächtnis"
            else:
                 return saved_id, "Gedächtnis (Offline)"

        if not self.voices:
            return None, "Fehler: Keine Stimmen"

        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                vid = v['voice_id']
                mapping[npc_name] = vid
                save_mapping(mapping)
                return vid, "Namens-Match"

        filtered = []
        target_gender = npc_gender.lower()
        for v in self.voices:
            labels = v.get('labels') or {}
            g = labels.get('gender', '').lower()
            if target_gender == "female" and "female" in g: filtered.append(v)
            elif target_gender == "male" and "male" in g and "female" not in g: filtered.append(v)
        
        if not filtered: filtered = self.voices

        hash_obj = hashlib.md5(npc_name.encode('utf-8'))
        idx = int(hash_obj.hexdigest(), 16) % len(filtered)
        selected = filtered[idx]
        mapping[npc_name] = selected['voice_id']
        save_mapping(mapping)
        return selected['voice_id'], "Berechnet"

    def generate_and_play(self, text, npc_name_fallback="Unknown"):
        # 1. CACHE CHECK
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        cache_filename = os.path.join(self.cache_dir, f"quest_{text_hash}.mp3")

        if os.path.exists(cache_filename):
            log_message("Spiele Audio aus Cache (Kostenlos!)")
            try:
                pygame.mixer.music.load(cache_filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
                return 
            except Exception as e:
                log_message(f"Cache Fehler: {e}")

        # 2. NEU GENERIEREN
        npc_log, gender = self.get_npc_from_log()
        final_name = npc_log if npc_log != "Unknown" else npc_name_fallback
        voice_id, method = self.select_voice(final_name, gender)
        
        if not voice_id:
            log_message("Keine Stimme gefunden.")
            return

        log_message(f"Generiere neu: '{final_name}' ({method})")
        api_key = self.config.get("api_key", "").strip()
        
        try:
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            data = {
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers=headers, json=data)
            
            if resp.status_code == 200:
                # Speichern im Cache
                with open(cache_filename, "wb") as f:
                    f.write(resp.content)
                
                log_message(f"Audio gespeichert: {cache_filename}")
                
                pygame.mixer.music.load(cache_filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                log_message(f"TTS Fehler: {resp.text}")
        except Exception as e:
            log_message(f"Audio Fehler: {e}")

    def auto_crop_text_area(self, img_cv):
        """ Findet den größten Textblock automatisch """
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Text verdicken
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 8)) 
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours: return img_cv

        largest_cnt = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_cnt)
        
        # Filter für winzige Flecken
        if w * h < 2000: return img_cv

        # Zuschneiden mit Rand
        pad = 10
        h_img, w_img, _ = img_cv.shape
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w_img, x + w + pad)
        y2 = min(h_img, y + h + pad)
        
        return img_cv[y1:y2, x1:x2]

    def run_ocr(self):
        coords = self.config.get("ocr_coords", [0, 0, 100, 100])
        try:
            bbox = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
            if bbox[2] - bbox[0] < 10 or bbox[3] - bbox[1] < 10: 
                return ""

            img_pil = ImageGrab.grab(bbox=bbox)
            img_np = np.array(img_pil)
            
            # Auto-Crop anwenden
            optimized_img = self.auto_crop_text_area(img_np)
            
            # OCR auf das zugeschnittene Bild
            gray = cv2.cvtColor(optimized_img, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(thresh, config=custom_config, lang='eng+deu')
            
            clean = re.sub(r'\s+', ' ', text).strip()
            
            if len(clean) < 15: 
                return ""
                
            return clean
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
