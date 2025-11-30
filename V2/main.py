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
        
        # 1. FIX: Fenstergröße fest und stabil
        self.root.geometry("1000x900")
        # Verhindert, dass das Fenster sich an den Inhalt anpasst (schrumpft)
        self.root.pack_propagate(False) 
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 11, 'bold'), padding=5)
        style.configure('TLabel', font=('Segoe UI', 11))
        style.configure('TEntry', font=('Segoe UI', 11))
        style.configure('Treeview', font=('Segoe UI', 10), rowheight=25)
        style.configure('Treeview.Heading', font=('Segoe UI', 11, 'bold'))
        
        self.engine = VoiceEngine()
        self.hotkey_hook = None
        
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
        # Frame, der seine Größe behält
        frame = ttk.Frame(self.tab_main, padding=30)
        frame.pack(fill="both", expand=True)
        frame.pack_propagate(False) 

        ttk.Label(frame, text="LOTRO Voice Companion", font=("Segoe UI", 24, "bold")).pack(pady=20)
        
        # Reset Button
        ttk.Button(frame, text="Reset: Suche auf ganzem Monitor", command=self.reset_area).pack(fill="x", pady=10)

        self.lbl_status = ttk.Label(frame, text="Status: Bereit (Warte auf Taste...)", foreground="green", font=("Segoe UI", 12, "bold"))
        self.lbl_status.pack(pady=20)

        # Großer Action Button
        btn_action = ttk.Button(frame, text="🎤 JETZT Scannen & Vorlesen", command=self.run_once_manual)
        btn_action.pack(fill="x", ipady=15, pady=10)
        
        ttk.Button(frame, text="Debug: Letztes Bild zeigen", command=self.open_debug_image).pack(pady=10)

        ttk.Label(frame, text="Erkannter Text:", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5), anchor="w")
        
        # Textfeld fixieren
        self.txt_preview = tk.Text(frame, height=15, width=50, state="disabled", font=("Consolas", 11))
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=30)
        frame.pack(fill="both", expand=True)

        # FIX: Hier benutzen wir jetzt 'anchor' statt 'sticky' für pack()
        lbl_opts = {'anchor': 'w', 'pady': (10, 2)} 

        ttk.Label(frame, text="ElevenLabs API Key:").pack(**lbl_opts)
        self.ent_api_key = ttk.Entry(frame, width=60, show="*")
        self.ent_api_key.pack(fill="x", pady=2)

        ttk.Label(frame, text="Monitor Auswahl:").pack(**lbl_opts)
        self.cmb_monitor = ttk.Combobox(frame, values=["1", "2", "3", "4"], state="readonly")
        self.cmb_monitor.pack(fill="x", pady=2)
        self.cmb_monitor.set("1")

        ttk.Label(frame, text="Verzögerung (Sekunden):").pack(**lbl_opts)
        self.ent_delay = ttk.Entry(frame, width=60)
        self.ent_delay.pack(fill="x", pady=2)

        ttk.Label(frame, text="Hotkey (löst Scan aus):").pack(**lbl_opts)
        self.ent_hotkey = ttk.Entry(frame, width=60)
        self.ent_hotkey.pack(fill="x", pady=2)

        ttk.Label(frame, text="Tesseract Pfad:").pack(**lbl_opts)
        self.ent_tesseract = ttk.Entry(frame, width=60)
        self.ent_tesseract.pack(fill="x", pady=2)

        ttk.Label(frame, text="Script.log Pfad:").pack(**lbl_opts)
        self.ent_logpath = ttk.Entry(frame, width=60)
        self.ent_logpath.pack(fill="x", pady=2)

        ttk.Button(frame, text="Speichern & Neustart", command=self.save_settings).pack(pady=30, fill="x")

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=20)
        frame.pack(fill="both", expand=True)
        
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(tree_frame, columns=("NPC", "VoiceID"), show="headings", yscrollcommand=scrollbar.set)
        self.tree.heading("NPC", text="NPC Name")
        self.tree.heading("VoiceID", text="Stimme")
        self.tree.column("NPC", width=250)
        self.tree.column("VoiceID", width=350)
        self.tree.pack(fill="both", expand=True)
        
        scrollbar.config(command=self.tree.yview)
        
        ttk.Button(frame, text="Liste aktualisieren", command=self.refresh_mapping).pack(pady=15, fill="x")

    def setup_logs_tab(self):
        self.log_widget = scrolledtext.ScrolledText(self.tab_logs, state='disabled', font=("Consolas", 9))
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
            # Hotkey triggert jetzt direkt den einmaligen Scan
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.run_once_manual))
            self.log(f"Hotkey aktiv ({hk}) -> Startet Scan & Audio")
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

    def run_once_manual(self):
        """ Die neue Hauptfunktion: Einmal Scannen -> Sprechen -> Fertig """
        self.lbl_status.config(text="Status: Scanne...", foreground="orange")
        self.log("Manueller Start...")
        
        # Thread starten, damit GUI nicht einfriert
        threading.Thread(target=self.process_pipeline, daemon=True).start()

    def process_pipeline(self):
        try:
            # 1. OCR Scan
            txt = self.engine.run_ocr()
            
            if not txt or len(txt) < 5:
                self.log("Kein Text gefunden.")
                # GUI Updates müssen im Main-Thread passieren (oder via config, meist ok bei Tkinter simple sets)
                self.lbl_status.config(text="Status: Kein Text", foreground="red")
                return

            self.log(f"Erkannt: {txt[:40]}...")
            
            # GUI Update
            self.txt_preview.config(state="normal")
            self.txt_preview.delete(1.0, tk.END)
            self.txt_preview.insert(tk.END, txt)
            self.txt_preview.config(state="disabled")
            
            # 2. Audio generieren
            self.lbl_status.config(text="Status: Generiere Audio...", foreground="blue")
            self.engine.generate_and_play(txt, "Unknown")
            
            self.lbl_status.config(text="Status: Fertig (Bereit)", foreground="green")
            
        except Exception as e:
            self.log(f"Fehler: {e}")
            self.lbl_status.config(text="Status: Fehler", foreground="red")

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
