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
        
        # 1. GRÖSSERES FENSTER
        self.root.geometry("1000x900")
        
        # 2. GRÖSSERE SCHRIFTARTEN (Styles)
        style = ttk.Style()
        style.theme_use('clam') # Modernes Theme
        
        # Standard-Schrift für alles
        style.configure('.', font=('Segoe UI', 12))
        
        # Spezielle Anpassungen
        style.configure('TButton', font=('Segoe UI', 12, 'bold'), padding=10)
        style.configure('TLabel', font=('Segoe UI', 12))
        style.configure('TEntry', font=('Segoe UI', 12))
        style.configure('Treeview', font=('Segoe UI', 11), rowheight=30)
        style.configure('Treeview.Heading', font=('Segoe UI', 12, 'bold'))
        
        self.engine = VoiceEngine()
        self.running = False
        self.last_text = ""
        self.hotkey_hook = None
        
        self.var_autoplay = tk.BooleanVar(value=False)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_mapping = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main, text="  Hauptmenü  ")
        self.notebook.add(self.tab_settings, text="  Einstellungen  ")
        self.notebook.add(self.tab_mapping, text="  Stimmen  ")
        self.notebook.add(self.tab_logs, text="  Logs  ")

        self.setup_main_tab()
        self.setup_settings_tab()
        self.setup_mapping_tab()
        self.setup_logs_tab()

        self.load_settings_to_ui()
        self.register_hotkey()

    def setup_main_tab(self):
        frame = ttk.Frame(self.tab_main, padding=30)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="LOTRO Voice Companion", font=("Segoe UI", 24, "bold")).pack(pady=20)
        
        ttk.Button(frame, text="Reset: Suche auf ganzem Monitor", command=self.reset_area).pack(fill="x", pady=10)

        self.lbl_status = ttk.Label(frame, text="Status: OCR Inaktiv", foreground="red", font=("Segoe UI", 14, "bold"))
        self.lbl_status.pack(pady=20)

        # Steuerung
        control_frame = ttk.LabelFrame(frame, text=" Steuerung ", padding=20)
        control_frame.pack(fill="x", pady=10)

        self.btn_ocr = ttk.Button(control_frame, text="Start Text-Erkennung (OCR)", command=self.toggle_ocr)
        self.btn_ocr.pack(fill="x", pady=10)

        self.btn_play = ttk.Button(control_frame, text="🔊 Audio jetzt abspielen", command=self.trigger_audio_manual)
        self.btn_play.pack(fill="x", pady=10)
        
        chk = ttk.Checkbutton(control_frame, text="Automatisch abspielen bei neuem Text", variable=self.var_autoplay)
        chk.pack(anchor="w", pady=10)
        
        ttk.Button(frame, text="Debug: Erkanntes Bild zeigen", command=self.open_debug_image).pack(pady=10)

        ttk.Label(frame, text="Erkannter Text (Vorschau):", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5), anchor="w")
        self.txt_preview = tk.Text(frame, height=10, width=50, state="disabled", font=("Consolas", 11))
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=30)
        frame.pack(fill="both", expand=True)

        grid_opts = {'sticky': 'w', 'pady': 10}

        ttk.Label(frame, text="ElevenLabs API Key:").pack(**grid_opts)
        self.ent_api_key = ttk.Entry(frame, width=60, show="*")
        self.ent_api_key.pack(fill="x", pady=5)

        ttk.Label(frame, text="Monitor Auswahl:").pack(**grid_opts)
        self.cmb_monitor = ttk.Combobox(frame, values=["1", "2", "3", "4"], state="readonly", font=("Segoe UI", 12))
        self.cmb_monitor.pack(fill="x", pady=5)
        self.cmb_monitor.set("1")

        ttk.Label(frame, text="Verzögerung (Sekunden):").pack(**grid_opts)
        self.ent_delay = ttk.Entry(frame, width=60)
        self.ent_delay.pack(fill="x", pady=5)

        ttk.Label(frame, text="Hotkey:").pack(**grid_opts)
        self.ent_hotkey = ttk.Entry(frame, width=60)
        self.ent_hotkey.pack(fill="x", pady=5)

        ttk.Label(frame, text="Tesseract Pfad:").pack(**grid_opts)
        self.ent_tesseract = ttk.Entry(frame, width=60)
        self.ent_tesseract.pack(fill="x", pady=5)

        ttk.Label(frame, text="Script.log Pfad:").pack(**grid_opts)
        self.ent_logpath = ttk.Entry(frame, width=60)
        self.ent_logpath.pack(fill="x", pady=5)

        ttk.Button(frame, text="Speichern & Neustart Engine", command=self.save_settings).pack(pady=40, fill="x")

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Scrollbar Container
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(tree_frame, columns=("NPC", "VoiceID"), show="headings", yscrollcommand=scrollbar.set)
        self.tree.heading("NPC", text="NPC Name")
        self.tree.heading("VoiceID", text="Stimme")
        self.tree.column("NPC", width=300)
        self.tree.column("VoiceID", width=400)
        self.tree.pack(fill="both", expand=True)
        
        scrollbar.config(command=self.tree.yview)
        
        ttk.Button(frame, text="Liste aktualisieren", command=self.refresh_mapping).pack(pady=20, fill="x")

    def setup_logs_tab(self):
        self.log_widget = scrolledtext.ScrolledText(self.tab_logs, state='disabled', font=("Consolas", 10))
        self.log_widget.pack(fill="both", expand=True, padx=10, pady=10)

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
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.trigger_audio_manual))
            self.log(f"Hotkey aktiviert ({hk})")
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
            self.btn_ocr.config(text="STOP Text-Erkennung")
            self.lbl_status.config(text="Status: OCR LÄUFT", foreground="green")
            threading.Thread(target=self.ocr_loop, daemon=True).start()
            self.log("OCR gestartet.")
        else:
            self.running = False
            self.btn_ocr.config(text="START Text-Erkennung (OCR)")
            self.lbl_status.config(text="Status: OCR Inaktiv", foreground="red")
            self.log("OCR gestoppt.")

    def trigger_audio_manual(self):
        text = self.txt_preview.get("1.0", tk.END).strip()
        if not text:
            self.log("Kein Text vorhanden.")
            return
        self.log("Audio manuell gestartet...")
        threading.Thread(target=self.engine.generate_and_play, args=(text, "Unknown"), daemon=True).start()

    def ocr_loop(self):
        while self.running:
            try:
                txt = self.engine.run_ocr()
                if self.engine.is_new_text(txt, self.last_text):
                    self.log(f"Neu erkannt ({len(txt)} Zeichen)")
                    self.txt_preview.config(state="normal")
                    self.txt_preview.delete(1.0, tk.END)
                    self.txt_preview.insert(tk.END, txt)
                    self.txt_preview.config(state="disabled")
                    self.last_text = txt
                    
                    if self.var_autoplay.get():
                        self.log("Auto-Play aktiv...")
                        self.engine.generate_and_play(txt, "Unknown")
                time.sleep(1)
            except Exception as e:
                print(f"Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
