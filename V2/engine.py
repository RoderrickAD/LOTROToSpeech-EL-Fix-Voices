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
        
        try:
            pygame.mixer.init()
        except Exception as e:
            log_message(f"Audio Init Fehler: {e}")
        
        self.cache_dir = os.path.join(os.getcwd(), "AudioCache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        tess_path = self.config.get("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = tess_path

    def is_new_text(self, new_text, old_text):
        if not new_text or len(new_text) < 15: return False
        if not old_text: return True
        # Niedrigere Ratio bedeutet, dass der Text als "neu" betrachtet wird (weniger als 85% Übereinstimmung)
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
                        # Vereinfachte Geschlechtsbestimmung
                        gender = "Female" if any(x in last.lower() for x in ["female", "frau", "she"]) else "Male"
                        return last, gender
        except: pass
        return "Unknown", "Unknown"

    def select_voice(self, npc_name, npc_gender):
        if not self.voices:
            log_message("Keine Stimmen im Speicher. Versuche Laden...")
            self.fetch_voices()
            if not self.voices: 
                # NOTFALL-Stimme, wenn keine API-Stimmen geladen werden konnten
                return "21m00Tcm4TlvDq8ikWAM", "NOTFALL (Rachel)" 

        mapping = load_mapping()
        if npc_name in mapping:
            return mapping[npc_name], "Gedächtnis"

        # 1. Match über Namen in ElevenLabs Stimmen
        for v in self.voices:
            if npc_name.lower() in v['name'].lower():
                mapping[npc_name] = v['voice_id']
                save_mapping(mapping)
                return v['voice_id'], "Namens-Match"

        # 2. Match über Geschlecht-Label, dann Hash-Auswahl
        filtered = [v for v in self.voices if npc_gender.lower() in v.get('labels', {}).get('gender', '').lower()]
        if not filtered: filtered = self.voices # Fallback auf alle Stimmen
        
        # Deterministische Auswahl mittels Hash
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
        
        if method == "NOTFALL (Rachel)": 
            log_message(f"WARNUNG: Notfall-Stimme verwendet. API Key prüfen!")

        if not vid: 
            log_message("ABBRUCH: Konnte keine Stimme zuweisen.")
            return

        log_message(f"Generiere neu: '{name}' ({method})")
        try:
            # ElevenLabs API-Call
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
            # Sicherstellen, dass der Mixer neu initialisiert wird, falls er beendet wurde
            pygame.mixer.quit()
            pygame.mixer.init()
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            log_message(f"Fehler beim Abspielen: {e}")

    def get_monitor_screenshot(self):
        mon_idx = int(self.config.get("monitor_index", 1))
        try:
            with mss.mss() as sct:
                # Prüfen, ob der Index gültig ist, andernfalls den ersten/Hauptmonitor verwenden (Index 1)
                if mon_idx >= len(sct.monitors): mon_idx = 1
                monitor = sct.monitors[mon_idx]
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                # mss gibt BGRA aus, konvertieren zu BGR für OpenCV
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            log_message(f"Screenshot Fehler: {e}")
            return None

    def crop_to_content(self, img):
        """Trimmt schwarze/leere Ränder um das gefundene Textbild."""
        # Konvertiere zu Graustufen und wende Rauschunterdrückung an
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.medianBlur(gray, 5) 
        
        # Finde nicht-schwarze Pixel
        coords = cv2.findNonZero(denoised)
        if coords is not None:
            # Berechne die Bounding Box
            x, y, w, h = cv2.boundingRect(coords)
            
            # Füge etwas Padding hinzu
            pad = 5
            h_img, w_img = img.shape[:2]
            
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(w_img - x, w + 2*pad)
            h = min(h_img - y, h + 2*pad)
            
            return img[y:y+h, x:x+w]
        
        return img # Rückgabe des Originalbildes, wenn kein Inhalt gefunden wurde

    def auto_find_quest_text(self, img):
        # *** ANPASSUNG: Verwende das gesamte Bild (ROI = img) ***
        roi = img
        # Die vorherigen Margin-Berechnungen und die roi-Definition wurden entfernt,
        # um den gesamten Bildschirm/Screenshot zu berücksichtigen.
        
        if roi.shape[0] < 50 or roi.shape[1] < 50: return img

        # 1. Weiß-Maske (gegen Gelb, um weiße Dialogfelder zu finden)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # Helle Farben (weiß bis hellgrau)
        lower_white = np.array([0, 0, 160]) 
        upper_white = np.array([180, 50, 255]) 
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 2. Verschmelzen (Dilatieren, um Textblöcke zu verbinden)
        # Kernelgröße: Horizontal lang, vertikal kurz, um Textzeilen zu verbinden.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        dilated = cv2.dilate(mask, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        candidates = []
        roi_w = roi.shape[1]
        mid_x = roi_w / 2
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < 5000: continue # Ignoriere sehr kleine Konturen (Rauschen)
            
            # Bevorzuge Konturen im linken/zentralen Bereich, da LotRO Dialoge dort sind
            center_x = x + (w / 2)
            # Begrenze die Suche auf die linke Hälfte/Mitte des Bildes (ca. 60% von links)
            if center_x < (mid_x + roi_w * 0.1): 
                candidates.append((cnt, area))
        
        if not candidates and contours:
            # Fallback: Wenn kein Kandidat die Center-Bedingung erfüllt, nimm die größte Kontur überhaupt
            best_cnt = max(contours, key=cv2.contourArea)
        elif candidates:
            # Nimm den größten gültigen Kandidaten
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_cnt = candidates[0][0]
        else:
            return roi # Rückgabe des gesamten Bildes, wenn keine Kontur gefunden wurde

        # Schneide das Bild auf die beste Kontur zu
        rx, ry, rw, rh = cv2.boundingRect(best_cnt)
        pad = 5
        rx1 = max(0, rx - pad)
        ry1 = max(0, ry - pad)
        rx2 = min(roi.shape[1], rx + rw + pad)
        ry2 = min(roi.shape[0], ry + rh + pad)
        
        cropped_roi = roi[ry1:ry2, rx1:rx2]
        cropped_mask = mask[ry1:ry2, rx1:rx2]
        
        # 3. Maskieren: Wende die Weiß-Maske auf das zugeschnittene Bild an, um nur den weißen Textblock zu isolieren
        masked_image = cv2.bitwise_and(cropped_roi, cropped_roi, mask=cropped_mask)
        
        # 4. Auto-Trim (Schwarze Ränder weg)
        final_image = self.crop_to_content(masked_image)
        
        # Debug
        cv2.imwrite("last_detection_debug.png", final_image)
        
        return final_image

    def run_ocr(self):
        try:
            img = self.get_monitor_screenshot()
            if img is None: return ""

            optimized_img = self.auto_find_quest_text(img)
            
            gray = cv2.cvtColor(optimized_img, cv2.COLOR_BGR2GRAY)
            
            # Konfiguration für bessere deutsche OCR
            config = r'--oem 3 --psm 6 -l deu+eng' 
            
            raw_text = pytesseract.image_to_string(gray, config=config)
            
            # Post-Processing: Entferne unnötige Zeilen (die nicht in Anführungszeichen stehen)
            lines = raw_text.split('\n')
            
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped: continue
                
                # *** FILTER ANPASSUNG: Nur Sätze mit Anführungszeichen oder Satzzeichen ***
                # Nur Sätze werden genommen, die:
                # 1. Mit Anführungszeichen (") oder Apostroph (') beginnen oder enden.
                # ODER
                # 2. Mit einem Satzendezeichen (., !, ?) enden.
                # UND länger als 20 Zeichen sind (um Rauschen zu ignorieren).
                is_dialog_start_end = stripped.startswith(('"', "'")) or stripped.endswith(('"', "'"))
                is_dialog_end_punc = stripped.endswith((".", "!", "?"))
                
                if (is_dialog_start_end or is_dialog_end_punc) or len(stripped) > 20:
                    cleaned_lines.append(stripped)

            # Zusammenfügen und Leerzeichen normalisieren
            clean_output = ' '.join(cleaned_lines)
            clean_output = re.sub(r'\s+', ' ', clean_output).strip()
            
            # FIX 2: Entferne bekannte Müll-Fragmente, die nicht Dialog sind
            clean_output = re.sub(r'oo|Oo|oO|Solo|solo|NYZ B|„Aa 1', '', clean_output)
            clean_output = re.sub(r'‘', "'", clean_output)
            
            # Speichern für Debugging
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
