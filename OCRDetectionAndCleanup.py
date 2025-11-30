import globalVariables
import isQuestWindowOpen
import pytesseract
from PIL import ImageGrab
import lookForTesseract
import cleanText
import getNPCNameFromPluginOutput  # WICHTIG: Das hier fehlte oder wurde nicht genutzt

def ocr_detection_and_cleaup():
    start_x = globalVariables.start_x
    start_y = globalVariables.start_y
    end_x = globalVariables.end_x
    end_y = globalVariables.end_y

    if end_x < start_x:
        start_x, end_x = end_x, start_x
    if end_y < start_y:
        start_y, end_y = end_y, start_y

    if isQuestWindowOpen.is_image_on_screen():
        try:
            screenshot = ImageGrab.grab(bbox=(start_x, start_y, end_x, end_y))

            globalVariables.tesseract_language = lookForTesseract.load_tesseract_lang()

            if not globalVariables.tesseract_language:
                globalVariables.tesseract_language = "eng"

            text = pytesseract.image_to_string(screenshot, lang=globalVariables.tesseract_language)
            
            # Text bereinigen
            cleaned_text = cleanText.clear(text)
            
            # Wenn kein Text da ist, brich ab
            if not cleaned_text or len(cleaned_text.strip()) < 2:
                return False

            globalVariables.text_ocr = cleaned_text
            
            # --- NEU: NPC Namen und Geschlecht holen ---
            # Wir lesen jetzt das Plugin-Log aus, um zu wissen, WER spricht.
            gender, name = getNPCNameFromPluginOutput.get_npc_gender_by_name()
            
            # Speichere es in den globalen Variablen, damit ElevenLabs es findet
            globalVariables.npc_gender = gender
            globalVariables.npc_name = name
            
            print(f"OCR erfolgreich. Erkannt: '{name}' ({gender})")
            # -------------------------------------------

            return True
            
        except Exception as e:
            print(f"Fehler in OCR Cleanup: {e}")
            return False

    return False
