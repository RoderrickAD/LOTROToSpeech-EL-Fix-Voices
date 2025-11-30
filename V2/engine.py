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
import threading
import shutil
from requests.exceptions import RequestException
import mss 
import mss.tools 
from utils import load_config, load_mapping, save_mapping, log_message

# Konstante für die maximale Cache-Größe in Bytes (ca. 1 GB)
MAX_CACHE_SIZE_BYTES = 1024 * 1024 * 1024 

class VoiceEngine:
    def __init__(self):
        self.config = load_config()
        self.voices = []
        
        try:
            pygame.mixer.init()
        except Exception as e:
            log_message(f"Audio Init Fehler: {e}")
        
        self.cache_dir = os.path.join(os.getcwd(), "AudioCache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        self._clean_cache() 
        
        tess_path = self.config.get("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = tess_path

        # Lade Templates für Template Matching
        self.templates = self._load_templates()
        
    def _load_templates(self):
        """Lädt die Template-Bilder aus dem 'templates'-Ordner."""
        template_dir = os.path.join(os.getcwd(), "templates")
        templates = {}
        template_names = {
            "top_left": "top_left.png",
            "top_right": "top_right.png",
            "bottom_right": "bottom_right.png",
            "bottom_left": "bottom_left.png"
        }

        for key, filename in template_names.items():
            filepath = os.path.join(template_dir, filename)
            if os.path.exists(filepath):
                templates[key] = cv2.imread(filepath, cv2.IMREAD_COLOR) 
                if templates[key] is None:
                    log_message(f"WARNUNG: Konnte Template '{filepath}' nicht laden.")
            else:
                log_message(f"FEHLER: Template '{filepath}' nicht gefunden.")
                return None 

        if len(templates) == len(template_names):
            log_message(f"{len(templates)} Templates erfolgreich geladen.")
            return templates
        else:
            log_message("FEHLER: Nicht alle Templates konnten geladen werden. Template Matching deaktiviert.")
            return None

    def _clean_cache(self):
        """Löscht die ältesten Dateien, wenn der Cache die MAX_CACHE_SIZE überschreitet."""
        total_size = 0
        file_details = []
        
        for root, _, files in os.walk(self.cache_dir):
            for name in files:
                filepath = os.path.join(root, name)
                if os.path.exists(filepath):
                    stat = os.stat(filepath)
                    total_size += stat.st_size
                    file_details.append((filepath, stat.st_mtime))

        if total_size > MAX_CACHE_SIZE_BYTES:
            log_message(f"Cache-Größe ({total_size // (1024*1024)} MB) überschreitet Limit. Bereinige...")
            file_details.sort(key=lambda x: x[1])

            for filepath, _ in file_details:
                if total_size <= MAX_CACHE_SIZE_BYTES:
                    break
                
                try:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    total_size -= size
                    log_message(f"Gelöscht: {filepath}")
                except Exception as e:
                    log_message(f"Fehler beim Löschen von {filepath}: {e}")

    def is_new_text(self, new_text, old_text):
        if not new_text or len(new_text) < 15: return False
        if not old_text: return True
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
            else:
                log_message(f"API Fehler beim Laden der Stimmen: {resp.text}")
        except RequestException as e:
            log_message(f"Netzwerkfehler beim Laden der Stimmen: {e}")
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
        if not self.voices:
            log_message("Keine Stimmen im Speicher. Versuche Laden...")
            self.fetch_voices()
            if not self.voices: 
                return "21m00Tcm4TlvDq8ikWAM", "NOTFALL (Rachel)" 

        mapping = load_mapping()
        if npc_name in mapping:
            return mapping[npc_name], "Gedächtnis"

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
            threading.Thread(target=self._play_audio_thread, args=(cache_file,)).start()
            return

        npc_log, gender = self.get_npc_from_log()
        name = npc_log if npc_log != "Unknown" else npc_name_fallback
        
        vid, method = self.select_voice(name, gender)
        
        if method == "NOTFALL (Rachel)": 
            log_message(f"WARNUNG: Notfall-Stimme verwendet. API Key prüfen!")

        if not vid: 
            log_message("ABBRUCH: Konnte keine Stimme zuweisen.")
            return

        log_message(f"Generiere neu: '{name}' ({method})")
        try:
            voice_settings = self.config.get("voice_settings", {"stability": 0.5, "similarity_boost": 0.75})
            
            headers = {"xi-api-key": self.config.get("api_key", ""), "Content-Type": "application/json"}
            data = {"text": text, "model_id": "eleven_turbo_v2_5", "voice_settings": voice_settings}
            
            resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", headers=headers, json=data)
            
            if resp.status_code == 200:
                with open(cache_file, "wb") as f: f.write(resp.content)
                threading.Thread(target=self._play_audio_thread, args=(cache_file,)).start()
            else:
                error_detail = resp.json().get('detail', 'Keine Details verfügbar.') if 'application/json' in resp.headers.get('Content-Type', '') else resp.text
                log_message(f"API Fehler ({resp.status_code}): {error_detail}")
        except RequestException as e:
            log_message(f"Netzwerkfehler bei TTS-Generierung: {e}")
        except Exception as e:
            log_message(f"TTS Fehler: {e}")
            
    def _play_audio_thread(self, filepath):
        """Spielt die Audiodatei im Hintergrund ab."""
        try:
            if not pygame.mixer.get_init():
                 pygame.mixer.init()
                 
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            pygame.mixer.music.unload()
            pygame.mixer.quit()

        except Exception as e:
            log_message(f"Fehler beim Abspielen: {e}")

    def play_audio_file(self, filepath):
        """Öffentliche Schnittstelle für die Wiedergabe, startet den Thread."""
        threading.Thread(target=self._play_audio_thread, args=(filepath,)).start()
        
    def get_monitor_screenshot(self):
        mon_idx = int(self.config.get("monitor_index", 1))
        try:
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

    def crop_to_content(self, img):
        """Trimmt schwarze/leere Ränder um das gefundene Textbild."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.medianBlur(gray, 5) 
        
        coords = cv2.findNonZero(denoised)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            
            pad = 5
            h_img, w_img = img.shape[:2]
            
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(w_img - x, w + 2*pad)
            h = min(h_img - y, h + 2*pad)
            
            return img[y:y+h, x:x+w]
        
        return img

    def auto_find_quest_text(self, img):
        if self.templates is None:
            log_message("Template Matching nicht verfügbar, Templates fehlen. Fallback auf frühere Methode.")
            return self._fallback_auto_find_quest_text(img)

        gray_screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        found_positions = {}
        threshold = 0.80 # Auf 80% für mehr Toleranz

        for key, template_img in self.templates.items():
            if template_img is None: continue
            
            gray_template = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
            
            res = cv2.matchTemplate(gray_screenshot, gray_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                found_positions[key] = max_loc 
            else:
                log_message(f"WARNUNG: Template '{key}' wurde nicht mit ausreichender Genauigkeit ({max_val:.2f}) gefunden. Fallback.")
                return self._fallback_auto_find_quest_text(img) 

        if len(found_positions) < 4:
            log_message("WARNUNG: Nicht alle vier Ecken-Templates gefunden. Fallback.")
            return self._fallback_auto_find_quest_text(img)

        # Ermittle die Koordinaten des Dialogfensters (Bounding Box)
        final_x1 = min(found_positions["top_left"][0], found_positions["bottom_left"][0])
        final_y1 = min(found_positions["top_left"][1], found_positions["top_right"][1])
        final_x2 = max(found_positions["top_right"][0] + self.templates["top_right"].shape[1], 
                       found_positions["bottom_right"][0] + self.templates["bottom_right"].shape[1])
        final_y2 = max(found_positions["bottom_left"][1] + self.templates["bottom_left"].shape[0], 
                       found_positions["bottom_right"][1] + self.templates["bottom_right"].shape[0])
        
        # Padding
        padding = 10
        final_x1 = max(0, final_x1 - padding)
        final_y1 = max(0, final_y1 - padding)
        final_x2 = min(img.shape[1], final_x2 + padding)
        final_y2 = min(img.shape[0], final_y2 + padding)

        dialog_region = img[final_y1:final_y2, final_x1:final_x2]
        
        if dialog_region.shape[0] < 50 or dialog_region.shape[1] < 50:
            log_message("WARNUNG: Gefundener Dialogbereich ist zu klein. Fallback.")
            return self._fallback_auto_find_quest_text(img)
        
        log_message(f"Dialograhmen mittels Template Matching gefunden: ({final_x1}, {final_y1}) bis ({final_x2}, {final_y2})")

        # BILDVERARBEITUNG FÜR OPTIMIERTE OCR
        final_image_gray = cv2.cvtColor(dialog_region, cv2.COLOR_BGR2GRAY)
        
        # 1. Kontrastverbesserung (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(final_image_gray)
        
        # 2. Rauschunterdrückung
        denoised = cv2.medianBlur(contrasted, 3) 
        
        # 3. Adaptive Binarisierung: Invertiert das Bild und wendet lokal optimierten Schwellenwert an
        inverted = cv2.bitwise_not(denoised)
        optimized_img = cv2.adaptiveThreshold(inverted, 255, 
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                              cv2.THRESH_BINARY, 11, 2)
        
        cv2.imwrite("last_detection_debug.png", optimized_img)
        
        return optimized_img # Rückgabe des binarisierten Bildes

    def _fallback_auto_find_quest_text(self, img):
        """Die ursprüngliche Methode zur Erkennung des Quest-Textes, als Fallback."""
        log_message("Führe Fallback-Text-Erkennung aus.")
        h_img, w_img = img.shape[:2]
        
        if h_img < 50 or w_img < 50: return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Grobe Vor-Eingrenzung (prozentual)
        crop_top = int(h_img * 0.12)  
        crop_bottom = int(h_img * 0.12)
        crop_left = int(w_img * 0.18) 
        crop_right = int(w_img * 0.05)

        if (crop_top >= h_img - crop_bottom) or (crop_left >= w_img - crop_right):
            potential_dialog_area = img
        else:
            potential_dialog_area = img[crop_top:h_img-crop_bottom, crop_left:w_img-crop_right]

        if potential_dialog_area.shape[0] < 50 or potential_dialog_area.shape[1] < 50:
            potential_dialog_area = img

        hsv = cv2.cvtColor(potential_dialog_area, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 160]) 
        upper_white = np.array([180, 50, 255]) 
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        dilated = cv2.dilate(mask, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return cv2.cvtColor(potential_dialog_area, cv2.COLOR_BGR2GRAY)
        
        valid_contours = [c for c in contours if cv2.contourArea(c) > 5000]
        if not valid_contours:
            return cv2.cvtColor(potential_dialog_area, cv2.COLOR_BGR2GRAY)
            
        best_cnt = max(valid_contours, key=cv2.contourArea)

        rx, ry, rw, rh = cv2.boundingRect(best_cnt)
        pad = 5
        rx1 = max(0, rx - pad)
        ry1 = max(0, ry - pad)
        rx2 = min(potential_dialog_area.shape[1], rx + rw + pad)
        ry2 = min(potential_dialog_area.shape[0], ry + rh + pad)
        
        cropped_roi = potential_dialog_area[ry1:ry2, rx1:rx2]
        cropped_mask = mask[ry1:ry2, rx1:rx2]
        
        masked_image = cv2.bitwise_and(cropped_roi, cropped_roi, mask=cropped_mask)
        
        final_image = self.crop_to_content(masked_image)
        
        cv2.imwrite("last_detection_debug_fallback.png", final_image)
        
        return cv2.cvtColor(final_image, cv2.COLOR_BGR2GRAY) # Graustufe zurückgeben

    def run_ocr(self):
        try:
            img = self.get_monitor_screenshot()
            if img is None: 
                return ""

            # optimized_img ist ein binarisiertes oder Graustufenbild
            optimized_img = self.auto_find_quest_text(img)
            
            config = r'--oem 3 --psm 6 -l deu+eng' 
            
            raw_text = pytesseract.image_to_string(optimized_img, config=config)
            
            lines = raw_text.split('\n')
            
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped: continue
                
                is_dialog_start_end = stripped.startswith(('"', "'")) or stripped.endswith(('"', "'"))
                is_dialog_end_punc = stripped.endswith((".", "!", "?"))
                
                if (is_dialog_start_end or is_dialog_end_punc) or len(stripped) > 20:
                    cleaned_lines.append(stripped)

            clean_output = ' '.join(cleaned_lines)
            clean_output = re.sub(r'\s+', ' ', clean_output).strip()
            
            clean_output = re.sub(r'oo|Oo|oO|Solo|solo|NYZ B|„Aa 1', '', clean_output)
            clean_output = re.sub(r'‘', "'", clean_output)
            
            if len(clean_output) < 10:
                return ""
            
            try:
                with open("last_recognized_text.txt", "w", encoding="utf-8") as f:
                    f.write("--- RAW TESSERACT OUTPUT ---\n")
                    f.write(raw_text)
                    f.write("\n\n--- FILTERED OUTPUT (SEND TO AI) ---\n")
                    f.write(clean_output)
            except: pass
            
            return clean_output
        except Exception as e:
            log_message(f"OCR Fehler: {e}")
            return ""
