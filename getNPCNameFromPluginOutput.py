import os
from pathlib import Path
import getNPCGender

# Der Pfad zur Log-Datei des LOTRO Plugins. 
# WICHTIG: Du musst das Plugin im Spiel installiert haben!
file_path = str(Path.home() / 'Documents') + r"/The Lord of the Rings Online/Script.log"

def get_npc_gender_by_name():
    if os.path.exists(file_path):
        try:
            # 'utf-8' mit 'ignore' verhindert Abstürze bei seltsamen Zeichen
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()

                if lines:
                    # Die letzte Zeile enthält den aktuellen NPC
                    last_line = lines[-1].strip()
                    
                    # Hole das Geschlecht basierend auf dem Namen (via Datenbank/Logik)
                    gender = getNPCGender.return_npc_gender(last_line)
                    
                    return str(gender), str(last_line)
                else:
                    # Datei ist leer
                    return "Unknown", "Unknown"
                    
        except Exception as e:
            print(f"Fehler beim Lesen der Script.log: {e}")
            return "Unknown", "Unknown"
    else:
        print(f"WARNUNG: Script.log nicht gefunden unter: {file_path}")
        print("Hast du das LOTRO Plugin installiert und aktiviert?")
        return "Unknown", "Unknown"
