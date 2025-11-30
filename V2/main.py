import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import keyboard  # WICHTIG: Muss installiert sein (pip install keyboard)
from engine import VoiceEngine
from utils import save_config, log_message

class LotroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LOTRO Voice Companion 2.0")
        self.root.geometry("600x550")
        
        self.engine = VoiceEngine()
        self.running = False
        self.last_text = ""
        
        # Hotkey Hook speichern, damit wir ihn updaten können
        self.hotkey_hook = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both")

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_mapping = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main, text="Steuerung")
        self.notebook.add(self.tab_settings, text="Einstellungen")
        self.notebook.add(self.tab_mapping, text="Stimmen-Mapping")
        self.notebook.add(self.tab_logs, text="Logs")

        self.setup_main_tab()
        self.setup_settings_tab()
        self.setup_mapping_tab()
        self.setup_logs_tab()

        self.load_settings_to_ui()
        
        # Hotkey initial registrieren
        self.register_hotkey()

    def setup_main_tab(self):
        frame = ttk.Frame(self.tab_main, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="LOTRO Voice Companion", font=("Helvetica", 16, "bold")).pack(pady=10)
        
        self.btn_area = ttk.Button(frame, text="OCR Bereich auswählen", command=self.select_area)
        self.btn_area.pack(pady=5, fill="x")

        self.lbl_status = ttk.Label(frame, text="Status: Bereit (Gestoppt)", foreground="red")
        self.lbl_status.pack(pady=10)

        self.btn_start = ttk.Button(frame, text="Start Überwachung", command=self.toggle_monitoring)
        self.btn_start.pack(pady=5, fill="x")

        ttk.Label(frame, text="Letzter erkannter Text:", font=("Helvetica", 10, "bold")).pack(pady=(20, 5), anchor="w")
        self.txt_preview = tk.Text(frame, height=8, width=50, state="disabled")
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ElevenLabs API Key:").pack(anchor="w")
        self.ent_api_key = ttk.Entry(frame, width=50, show="*")
        self.ent_api_key.pack(fill="x", pady=5)

        ttk.Label(frame, text="Hotkey (z.B. ctrl+alt+s):").pack(anchor="w", pady=(10,0))
        self.ent_hotkey = ttk.Entry(frame, width=50)
        self.ent_hotkey.pack(fill="x", pady=5)

        ttk.Label(frame, text="Pfad zu Tesseract.exe:").pack(anchor="w", pady=(10, 0))
        self.ent_tesseract = ttk.Entry(frame, width=50)
        self.ent_tesseract.pack(fill="x", pady=5)

        ttk.Label(frame, text="Pfad zur Script.log (Plugin):").pack(anchor="w", pady=(10, 0))
        self.ent_logpath = ttk.Entry(frame, width=50)
        self.ent_logpath.pack(fill="x", pady=5)

        ttk.Button(frame, text="Speichern & Anwenden", command=self.save_settings).pack(pady=20)

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=10)
        frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(frame, columns=("NPC", "VoiceID"), show="headings")
        self.tree.heading("NPC", text="NPC Name")
        self.tree.heading("VoiceID", text="Zugewiesene Stimme")
        self.tree.pack(fill="both", expand=True, side="left")
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        ttk.Button(self.tab_mapping, text="Liste aktualisieren", command=self.refresh_mapping).pack(pady=5)

    def setup_logs_tab(self):
        self.log_widget = scrolledtext.ScrolledText(self.tab_logs, state='disabled')
        self.log_widget.pack(fill="both", expand=True)

    def log(self, message):
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, message + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state='disabled')

    def load_settings_to_ui(self):
        cfg = self.engine.config
        self.ent_api_key.insert(0, cfg.get("api_key", ""))
        self.ent_tesseract.insert(0, cfg.get("tesseract_path", ""))
        self.ent_logpath.insert(0, cfg.get("lotro_log_path", ""))
        self.ent_hotkey.insert(0, cfg.get("hotkey", "ctrl+alt+s"))
        self.refresh_mapping()

    def save_settings(self):
        cfg = self.engine.config
        cfg["api_key"] = self.ent_api_key.get().strip()
        cfg["tesseract_path"] = self.ent_tesseract.get().strip()
        cfg["lotro_log_path"] = self.ent_logpath.get().strip()
        cfg["hotkey"] = self.ent_hotkey.get().strip()
        save_config(cfg)
        
        self.engine.config = cfg
        self.register_hotkey() # Hotkey neu setzen
        threading.Thread(target=self.engine.fetch_voices).start()
        messagebox.showinfo("Info", "Einstellungen gespeichert.")

    def register_hotkey(self):
        """ Setzt den Hotkey global neu """
        hotkey_str = self.engine.config.get("hotkey", "ctrl+alt+s")
        
        # Alten Hotkey entfernen falls vorhanden
        if self.hotkey_hook:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
            except:
                pass
        
        try:
            # Registriere Toggle Funktion
            self.hotkey_hook = keyboard.add_hotkey(hotkey_str, self.toggle_monitoring_safe)
            self.log(f"Hotkey aktiviert: {hotkey_str}")
        except Exception as e:
            self.log(f"Fehler beim Hotkey setzen: {e}")

    def refresh_mapping(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        from utils import load_mapping
        mapping = load_mapping()
        voice_map = {v['voice_id']: v['name'] for v in self.engine.voices}
        
        for npc, vid in mapping.items():
            readable_voice = voice_map.get(vid, vid)
            self.tree.insert("", "end", values=(npc, readable_voice))

    def select_area(self):
        self.root.iconify()
        top = tk.Toplevel(self.root)
        top.attributes('-fullscreen', True)
        top.attributes('-alpha', 0.3)
        top.configure(background='grey')
        
        self.start_x = None
        self.start_y = None
        
        canvas = tk.Canvas(top, cursor="cross", bg="grey")
        canvas.pack(fill="both", expand=True)

        def on_press(event):
            self.start_x = event.x
            self.start_y = event.y

        def on_drag(event):
            canvas.delete("sel_rect")
            canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline="red", width=2, tags="sel_rect")

        def on_release(event):
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            cfg = self.engine.config
            cfg["ocr_coords"] = [x1, y1, x2, y2]
            save_config(cfg)
            top.destroy()
            self.root.deiconify()
            self.log(f"Bereich gespeichert: {x1},{y1} bis {x2},{y2}")

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

    def toggle_monitoring_safe(self):
        """ Wrapper für Hotkey (der aus einem anderen Thread kommt) """
        self.root.after(0, self.toggle_monitoring)

    def toggle_monitoring(self):
        if not self.running:
            self.running = True
            self.btn_start.config(text=f"Stop Überwachung ({self.engine.config.get('hotkey')})")
            self.lbl_status.config(text="Status: LÄUFT", foreground="green")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
            self.log("Überwachung gestartet.")
        else:
            self.running = False
            self.btn_start.config(text=f"Start Überwachung ({self.engine.config.get('hotkey')})")
            self.lbl_status.config(text="Status: GESTOPPT", foreground="red")
            self.log("Überwachung gestoppt.")

    def monitor_loop(self):
        while self.running:
            try:
                text = self.engine.run_ocr()
                
                # Hier nutzen wir jetzt die intelligente Prüfung
                if self.engine.is_new_text(text, self.last_text):
                    
                    self.log(f"Neuer Text erkannt ({len(text)} Zeichen)...")
                    
                    self.txt_preview.config(state="normal")
                    self.txt_preview.delete(1.0, tk.END)
                    self.txt_preview.insert(tk.END, text)
                    self.txt_preview.config(state="disabled")
                    
                    self.engine.generate_and_play(text, "Unknown")
                    
                    self.root.after(100, self.refresh_mapping)
                    self.last_text = text
                
                time.sleep(1) # Prüfe jede Sekunde
            except Exception as e:
                print(f"Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
