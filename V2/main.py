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
        self.root.geometry("600x650")
        
        self.engine = VoiceEngine()
        self.running = False
        self.last_text = ""
        self.hotkey_hook = None

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
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)
        
        # Reset Button aktiviert den Vollbild-Scan Modus (Auto-Find)
        ttk.Button(btn_frame, text="Reset: Suche auf ganzem Monitor", command=self.reset_area).pack(side="left", fill="x", expand=True, padx=2)

        self.lbl_status = ttk.Label(frame, text="Status: Bereit", foreground="green")
        self.lbl_status.pack(pady=10)

        self.btn_start = ttk.Button(frame, text="Start Überwachung", command=self.toggle_monitoring)
        self.btn_start.pack(pady=5, fill="x")
        
        # Debug Button öffnet das Bild, das der Bot sieht
        ttk.Button(frame, text="Zeige erkanntes Questfenster (Debug)", command=self.open_debug_image).pack(pady=5)

        ttk.Label(frame, text="Letzter Text:", font=("Helvetica", 10, "bold")).pack(pady=(20, 5), anchor="w")
        self.txt_preview = tk.Text(frame, height=8, width=50, state="disabled")
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ElevenLabs API Key:").pack(anchor="w")
        self.ent_api_key = ttk.Entry(frame, width=50, show="*")
        self.ent_api_key.pack(fill="x", pady=5)

        # Monitor Auswahl
        ttk.Label(frame, text="Monitor (1 = Haupt, 2 = Zweit...):").pack(anchor="w", pady=(10,0))
        self.cmb_monitor = ttk.Combobox(frame, values=["1", "2", "3", "4"], state="readonly")
        self.cmb_monitor.pack(fill="x", pady=5)
        self.cmb_monitor.set("1")

        # Delay
        ttk.Label(frame, text="Audio Verzögerung (Sekunden):").pack(anchor="w", pady=(10,0))
        self.ent_delay = ttk.Entry(frame, width=50)
        self.ent_delay.pack(fill="x", pady=5)

        # Hotkey
        ttk.Label(frame, text="Hotkey:").pack(anchor="w", pady=(10,0))
        self.ent_hotkey = ttk.Entry(frame, width=50)
        self.ent_hotkey.pack(fill="x", pady=5)

        ttk.Label(frame, text="Tesseract Pfad:").pack(anchor="w", pady=(10, 0))
        self.ent_tesseract = ttk.Entry(frame, width=50)
        self.ent_tesseract.pack(fill="x", pady=5)

        ttk.Label(frame, text="Script.log Pfad:").pack(anchor="w", pady=(10, 0))
        self.ent_logpath = ttk.Entry(frame, width=50)
        self.ent_logpath.pack(fill="x", pady=5)

        ttk.Button(frame, text="Speichern & Stimmen laden", command=self.save_settings).pack(pady=20)

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=10)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("NPC", "VoiceID"), show="headings")
        self.tree.heading("NPC", text="NPC")
        self.tree.heading("VoiceID", text="Stimme")
        self.tree.pack(fill="both", expand=True, side="left")
        ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview).pack(side="right", fill="y")
        ttk.Button(self.tab_mapping, text="Liste aktualisieren", command=self.refresh_mapping).pack(pady=5)

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
            messagebox.showerror("Fehler", "Delay und Monitor müssen Zahlen sein.")
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
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.toggle_monitoring))
            self.log(f"Hotkey aktiviert: {hk}")
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
        self.log("Modus: Vollbild-Suche (automatischer Crop)")

    def open_debug_image(self):
        path = os.path.join(os.getcwd(), "last_detection_debug.png")
        if os.path.exists(path):
            os.startfile(path)
        else:
            self.log("Noch kein Bild vorhanden. Starte erst die Überwachung.")

    def toggle_monitoring(self):
        if not self.running:
            self.running = True
            self.btn_start.config(text=f"STOP ({self.engine.config.get('hotkey')})")
            self.lbl_status.config(text="LÄUFT", foreground="green")
            threading.Thread(target=self.loop, daemon=True).start()
        else:
            self.running = False
            self.btn_start.config(text=f"START ({self.engine.config.get('hotkey')})")
            self.lbl_status.config(text="GESTOPPT", foreground="red")

    def loop(self):
        while self.running:
            try:
                txt = self.engine.run_ocr()
                if self.engine.is_new_text(txt, self.last_text):
                    self.log(f"Neu erkannt: {txt[:30]}...")
                    self.txt_preview.config(state="normal")
                    self.txt_preview.delete(1.0, tk.END)
                    self.txt_preview.insert(tk.END, txt)
                    self.txt_preview.config(state="disabled")
                    self.engine.generate_and_play(txt, "Unknown")
                    self.last_text = txt
                time.sleep(1)
            except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
