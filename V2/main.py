import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
import keyboard
from engine import VoiceEngine
from utils import save_config, log_message

class LotroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LOTRO Voice Companion 2.0")
        self.root.geometry("600x700") # Etwas höher für die neuen Buttons
        
        self.engine = VoiceEngine()
        self.running = False
        self.last_text = ""
        self.hotkey_hook = None
        
        # Variable für Auto-Play Checkbox
        self.var_autoplay = tk.BooleanVar(value=False)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both")

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_mapping = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main, text="Hauptmenü")
        self.notebook.add(self.tab_settings, text="Einstellungen")
        self.notebook.add(self.tab_mapping, text="Stimmen")
        self.notebook.add(self.tab_logs, text="Logs")

        self.setup_main_tab()
        self.setup_settings_tab()
        self.setup_mapping_tab()
        self.setup_logs_tab()

        self.load_settings_to_ui()
        self.register_hotkey()

    def setup_main_tab(self):
        frame = ttk.Frame(self.tab_main, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="LOTRO Voice Companion", font=("Helvetica", 16, "bold")).pack(pady=10)
        
        # Bereichs Reset
        ttk.Button(frame, text="Reset: Suche auf ganzem Monitor", command=self.reset_area).pack(fill="x", pady=5)

        # Status Label
        self.lbl_status = ttk.Label(frame, text="Status: OCR Inaktiv", foreground="red")
        self.lbl_status.pack(pady=10)

        # --- NEU: Getrennte Steuerung ---
        control_frame = ttk.LabelFrame(frame, text="Steuerung", padding=10)
        control_frame.pack(fill="x", pady=10)

        # 1. OCR Toggle Button
        self.btn_ocr = ttk.Button(control_frame, text="Start Text-Erkennung (OCR)", command=self.toggle_ocr)
        self.btn_ocr.pack(fill="x", pady=5)

        # 2. Audio Trigger Button
        self.btn_play = ttk.Button(control_frame, text="🔊 Audio jetzt abspielen/generieren", command=self.trigger_audio_manual)
        self.btn_play.pack(fill="x", pady=5)
        
        # 3. Auto-Play Checkbox
        ttk.Checkbutton(control_frame, text="Automatisch abspielen wenn neuer Text erkannt wird", variable=self.var_autoplay).pack(anchor="w", pady=5)
        
        # Debug Button
        ttk.Button(frame, text="Debug: Zeige erkanntes Bild", command=self.open_debug_image).pack(pady=5)

        ttk.Label(frame, text="Erkannter Text (Vorschau):", font=("Helvetica", 10, "bold")).pack(pady=(10, 5), anchor="w")
        self.txt_preview = tk.Text(frame, height=8, width=50, state="disabled")
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ElevenLabs API Key:").pack(anchor="w")
        self.ent_api_key = ttk.Entry(frame, width=50, show="*")
        self.ent_api_key.pack(fill="x", pady=5)

        ttk.Label(frame, text="Monitor (1 = Haupt, 2 = Zweit...):").pack(anchor="w", pady=(10,0))
        self.cmb_monitor = ttk.Combobox(frame, values=["1", "2", "3", "4"], state="readonly")
        self.cmb_monitor.pack(fill="x", pady=5)
        self.cmb_monitor.set("1")

        ttk.Label(frame, text="Audio Verzögerung (Sekunden):").pack(anchor="w", pady=(10,0))
        self.ent_delay = ttk.Entry(frame, width=50)
        self.ent_delay.pack(fill="x", pady=5)

        ttk.Label(frame, text="Hotkey (löst Audio aus):").pack(anchor="w", pady=(10,0))
        self.ent_hotkey = ttk.Entry(frame, width=50)
        self.ent_hotkey.pack(fill="x", pady=5)

        ttk.Label(frame, text="Tesseract Pfad:").pack(anchor="w", pady=(10, 0))
        self.ent_tesseract = ttk.Entry(frame, width=50)
        self.ent_tesseract.pack(fill="x", pady=5)

        ttk.Label(frame, text="Script.log Pfad:").pack(anchor="w", pady=(10, 0))
        self.ent_logpath = ttk.Entry(frame, width=50)
        self.ent_logpath.pack(fill="x", pady=5)

        ttk.Button(frame, text="Speichern", command=self.save_settings).pack(pady=20)

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=10)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("NPC", "VoiceID"), show="headings")
        self.tree.heading("NPC", text="NPC")
        self.tree.heading("VoiceID", text="Stimme")
        self.tree.pack(fill="both", expand=True, side="left")
        ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview).pack(side="right", fill="y")
        ttk.Button(self.tab_mapping, text="Refresh", command=self.refresh_mapping).pack(pady=5)

    def setup_logs_tab(self):
        self.log_widget = scrolledtext.ScrolledText(self.tab_logs, state='disabled')
        self.log_widget.pack(fill="both", expand=True)

    def log(self, msg):
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, msg + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state='disabled')

    def load_settings_to_ui(self):
        cfg = self.engine.config
        self.ent_api_key.insert(0, cfg.get("api_key", ""))
        self.ent_tesseract.insert(0, cfg.get("tesseract_path", ""))
        self.ent_logpath.insert(0, cfg.get("lotro_log_path", ""))
        self.ent_hotkey.insert(0, cfg.get("hotkey", "ctrl+alt+s"))
        self.ent_delay.insert(0, str(cfg.get("audio_delay", 0.5)))
        self.cmb_monitor.set(str(cfg.get("monitor_index", 1)))
        self.refresh_mapping()

    def save_settings(self):
        cfg = self.engine.config
        cfg["api_key"] = self.ent_api_key.get().strip()
        cfg["tesseract_path"] = self.ent_tesseract.get().strip()
        cfg["lotro_log_path"] = self.ent_logpath.get().strip()
        cfg["hotkey"] = self.ent_hotkey.get().strip()
        try:
            cfg["audio_delay"] = float(self.ent_delay.get().strip())
            cfg["monitor_index"] = int(self.cmb_monitor.get())
        except:
            messagebox.showerror("Fehler", "Zahlenformat falsch")
            return

        save_config(cfg)
        self.engine.config = cfg
        self.register_hotkey()
        threading.Thread(target=self.engine.fetch_voices).start()
        messagebox.showinfo("Info", "Gespeichert.")

    def register_hotkey(self):
        hk = self.engine.config.get("hotkey", "ctrl+alt+s")
        if self.hotkey_hook:
            try: keyboard.remove_hotkey(self.hotkey_hook)
            except: pass
        try:
            # Hotkey triggert jetzt die Audio-Wiedergabe (Manual Trigger)
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.trigger_audio_manual))
            self.log(f"Hotkey aktiviert ({hk}) -> Löst Audio aus")
        except: self.log("Hotkey Fehler")

    def refresh_mapping(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        from utils import load_mapping
        mp = load_mapping()
        vm = {v['voice_id']: v['name'] for v in self.engine.voices}
        for n, v in mp.items(): self.tree.insert("", "end", values=(n, vm.get(v, v)))

    def reset_area(self):
        cfg = self.engine.config
        cfg["ocr_coords"] = None
        save_config(cfg)
        self.log("Bereich Reset: Suche auf ganzem Monitor")

    def open_debug_image(self):
        path = os.path.join(os.getcwd(), "last_detection_debug.png")
        if os.path.exists(path):
            os.startfile(path)
        else:
            self.log("Kein Debug-Bild vorhanden.")

    def toggle_ocr(self):
        if not self.running:
            self.running = True
            self.btn_ocr.config(text="Stop Text-Erkennung")
            self.lbl_status.config(text="Status: OCR Läuft (Scannt...)", foreground="green")
            threading.Thread(target=self.ocr_loop, daemon=True).start()
            self.log("OCR gestartet.")
        else:
            self.running = False
            self.btn_ocr.config(text="Start Text-Erkennung (OCR)")
            self.lbl_status.config(text="Status: OCR Inaktiv", foreground="red")
            self.log("OCR gestoppt.")

    def trigger_audio_manual(self):
        """ Wird vom Button oder Hotkey aufgerufen """
        # Hole Text aus dem Vorschau-Fenster
        text = self.txt_preview.get("1.0", tk.END).strip()
        if not text:
            self.log("Kein Text zum Abspielen vorhanden.")
            return
        
        self.log("Audio manuell angefordert...")
        # Starte Generation im Hintergrund (damit GUI nicht einfriert)
        threading.Thread(target=self.engine.generate_and_play, args=(text, "Unknown"), daemon=True).start()

    def ocr_loop(self):
        while self.running:
            try:
                # 1. Scannen
                txt = self.engine.run_ocr()
                
                # 2. Prüfen ob neu
                if self.engine.is_new_text(txt, self.last_text):
                    self.log(f"Neuer Text erkannt ({len(txt)} Zeichen)")
                    
                    # GUI Update (Thread-safe-ish)
                    self.txt_preview.config(state="normal")
                    self.txt_preview.delete(1.0, tk.END)
                    self.txt_preview.insert(tk.END, txt)
                    self.txt_preview.config(state="disabled")
                    
                    self.last_text = txt
                    
                    # 3. Auto-Play (nur wenn Checkbox aktiv)
                    if self.var_autoplay.get():
                        self.log("Auto-Play aktiv: Generiere Audio...")
                        self.engine.generate_and_play(txt, "Unknown")
                
                time.sleep(1)
            except Exception as e:
                print(f"Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
