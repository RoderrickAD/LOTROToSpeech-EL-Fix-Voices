import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
import keyboard
from engine import VoiceEngine
from utils import save_config, log_message

# --- LOTRO FARBPALETTE ---
COLOR_BG_MAIN = "#191b1e"       # Sehr dunkles Grau (Hintergrund)
COLOR_BG_FRAME = "#25282d"      # Etwas helleres Grau (Container)
COLOR_TEXT_GOLD = "#d4af37"     # LOTRO Gold (Titel/Wichtige Infos)
COLOR_TEXT_SILVER = "#c0c0c0"   # Silber (Normaler Text)
COLOR_BTN_BG = "#3d424b"        # Button Hintergrund
COLOR_BTN_FG = "#e6e6e6"        # Button Text
COLOR_ENTRY_BG = "#0f0f0f"      # Eingabefelder Schwarz
COLOR_ACCENT = "#782221"        # Dunkelrot (für Fehler)

FONT_UI = ("Georgia", 11)       # Serif-Schrift für Fantasy-Look
FONT_TITLE = ("Georgia", 22, "bold")
FONT_BOLD = ("Georgia", 11, "bold")
FONT_MONO = ("Consolas", 10)

class LotroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LOTRO Voice Companion 2.0")
        self.root.geometry("1000x850")
        self.root.configure(bg=COLOR_BG_MAIN)
        
        # Styles konfigurieren
        self.setup_styles()
        
        self.engine = VoiceEngine()
        self.running = False
        self.hotkey_hook = None

        # Custom Notebook (Tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=15, pady=15)

        # Tabs erstellen
        self.tab_main = self.create_tab_frame(self.notebook)
        self.tab_settings = self.create_tab_frame(self.notebook)
        self.tab_mapping = self.create_tab_frame(self.notebook)
        self.tab_logs = self.create_tab_frame(self.notebook)

        self.notebook.add(self.tab_main, text="  Abenteuer  ")
        self.notebook.add(self.tab_settings, text="  Einstellungen  ")
        self.notebook.add(self.tab_mapping, text="  Stimmen-Buch  ")
        self.notebook.add(self.tab_logs, text="  System-Log  ")

        self.setup_main_tab()
        self.setup_settings_tab()
        self.setup_mapping_tab()
        self.setup_logs_tab()

        self.load_settings_to_ui()
        self.register_hotkey()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Notebook (Tabs) Style
        style.configure("TNotebook", background=COLOR_BG_MAIN, borderwidth=0)
        style.configure("TNotebook.Tab", 
                        background=COLOR_BTN_BG, 
                        foreground=COLOR_TEXT_SILVER, 
                        font=FONT_BOLD, 
                        padding=[15, 5])
        style.map("TNotebook.Tab", 
                  background=[("selected", COLOR_BG_FRAME)], 
                  foreground=[("selected", COLOR_TEXT_GOLD)])

        # Frame Style
        style.configure("TFrame", background=COLOR_BG_FRAME)
        
        # Label Style
        style.configure("TLabel", background=COLOR_BG_FRAME, foreground=COLOR_TEXT_SILVER, font=FONT_UI)
        style.configure("Header.TLabel", foreground=COLOR_TEXT_GOLD, font=FONT_TITLE)
        
        # Treeview (Listen)
        style.configure("Treeview", 
                        background=COLOR_ENTRY_BG, 
                        foreground=COLOR_TEXT_SILVER, 
                        fieldbackground=COLOR_ENTRY_BG,
                        font=FONT_UI,
                        rowheight=28)
        style.configure("Treeview.Heading", background=COLOR_BTN_BG, foreground=COLOR_TEXT_GOLD, font=FONT_BOLD)
        style.map("Treeview", background=[("selected", "#3a4a5e")])

    def create_tab_frame(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        return frame

    def create_lotro_button(self, parent, text, command, bg_color=COLOR_BTN_BG):
        """ Erstellt einen Button im LOTRO-Stil (tk.Button für bessere Farben) """
        btn = tk.Button(parent, 
                        text=text, 
                        command=command,
                        bg=bg_color,
                        fg=COLOR_TEXT_GOLD,
                        font=FONT_BOLD,
                        activebackground=COLOR_TEXT_GOLD,
                        activeforeground=COLOR_BG_MAIN,
                        relief="ridge",
                        bd=3,
                        padx=20,
                        pady=10,
                        cursor="hand2")
        return btn

    def setup_main_tab(self):
        # Container mit Padding
        container = tk.Frame(self.tab_main, bg=COLOR_BG_FRAME)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Titel
        ttk.Label(container, text="LOTRO Voice Companion", style="Header.TLabel").pack(pady=(0, 20))

        # Status Panel
        status_frame = tk.Frame(container, bg=COLOR_ENTRY_BG, bd=2, relief="sunken")
        status_frame.pack(fill="x", pady=10, padx=5)
        
        self.lbl_status = tk.Label(status_frame, text="Status: Bereit (Warte auf Taste...)", 
                                   bg=COLOR_ENTRY_BG, fg="#4caf50", font=FONT_BOLD, pady=10)
        self.lbl_status.pack()

        # Action Button (Der Einzige, den man braucht)
        self.btn_action = self.create_lotro_button(container, "🔊 JETZT Scannen & Vorlesen", self.run_once_manual)
        self.btn_action.pack(fill="x", pady=20, ipady=5)

        # Text Vorschau
        ttk.Label(container, text="Erkannter Quest-Text:", foreground=COLOR_TEXT_GOLD).pack(anchor="w", pady=(10, 5))
        
        self.txt_preview = tk.Text(container, height=15, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT_SILVER, 
                                   insertbackground="white", font=("Georgia", 12), relief="flat", padx=10, pady=10)
        self.txt_preview.pack(fill="both", expand=True)
        self.txt_preview.config(state="disabled")

    def setup_settings_tab(self):
        container = tk.Frame(self.tab_settings, bg=COLOR_BG_FRAME)
        container.pack(fill="both", expand=True, padx=40, pady=20)

        def create_entry(label_text, show=None):
            ttk.Label(container, text=label_text).pack(anchor="w", pady=(10, 2))
            entry = tk.Entry(container, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT_SILVER, insertbackground="white", font=FONT_MONO, relief="flat", bd=5)
            if show: entry.config(show=show)
            entry.pack(fill="x", pady=2, ipady=3)
            return entry

        self.ent_api_key = create_entry("ElevenLabs API Key:", show="*")
        
        ttk.Label(container, text="Monitor Auswahl:").pack(anchor="w", pady=(10, 2))
        self.cmb_monitor = ttk.Combobox(container, values=["1", "2", "3", "4"], state="readonly", font=FONT_UI)
        self.cmb_monitor.pack(fill="x", pady=2, ipady=3)
        self.cmb_monitor.set("1")

        self.ent_delay = create_entry("Verzögerung (Sekunden):")
        self.ent_hotkey = create_entry("Hotkey (Startet Scan):")
        self.ent_tesseract = create_entry("Pfad zu Tesseract.exe:")
        self.ent_logpath = create_entry("Pfad zur Script.log:")

        self.create_lotro_button(container, "💾 Einstellungen Speichern", self.save_settings).pack(pady=30, fill="x")

    def setup_mapping_tab(self):
        container = tk.Frame(self.tab_mapping, bg=COLOR_BG_FRAME)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tree = ttk.Treeview(container, columns=("NPC", "VoiceID"), show="headings")
        self.tree.heading("NPC", text="NPC Name")
        self.tree.heading("VoiceID", text="Zugewiesene Stimme")
        self.tree.column("NPC", width=250)
        self.tree.column("VoiceID", width=350)
        
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        btn_refresh = self.create_lotro_button(self.tab_mapping, "🔄 Liste aktualisieren", self.refresh_mapping)
        btn_refresh.pack(side="bottom", fill="x", padx=20, pady=10)

    def setup_logs_tab(self):
        container = tk.Frame(self.tab_logs, bg=COLOR_BG_FRAME)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.log_widget = scrolledtext.ScrolledText(container, state='disabled', bg=COLOR_ENTRY_BG, fg="#a0a0a0", font=FONT_MONO)
        self.log_widget.pack(fill="both", expand=True)

    # --- FUNKTIONEN ---

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
        messagebox.showinfo("Gespeichert", "Einstellungen wurden übernommen.")

    def register_hotkey(self):
        hk = self.engine.config.get("hotkey", "ctrl+alt+s")
        if self.hotkey_hook:
            try: keyboard.remove_hotkey(self.hotkey_hook)
            except: pass
        try:
            # Hotkey startet den manuellen Scan
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.run_once_manual))
            self.log(f"Hotkey aktiviert ({hk})")
        except: self.log("Hotkey Fehler")

    def refresh_mapping(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        from utils import load_mapping
        mp = load_mapping()
        vm = {v['voice_id']: v['name'] for v in self.engine.voices}
        for n, v in mp.items(): self.tree.insert("", "end", values=(n, vm.get(v, v)))

    def run_once_manual(self):
        """ Scannt und liest vor (Einmalig) """
        self.lbl_status.config(text="Status: Scanne...", fg=COLOR_TEXT_GOLD)
        self.log("Manueller Start...")
        threading.Thread(target=self.process_pipeline, daemon=True).start()

    def process_pipeline(self):
        try:
            # 1. OCR Scan
            txt = self.engine.run_ocr()
            
            if not txt or len(txt) < 5:
                self.log("Kein Text gefunden.")
                self.lbl_status.config(text="Status: Kein Text gefunden", fg=COLOR_ACCENT)
                return

            self.log(f"Erkannt: {txt[:40]}...")
            
            # GUI Update
            self.txt_preview.config(state="normal")
            self.txt_preview.delete(1.0, tk.END)
            self.txt_preview.insert(tk.END, txt)
            self.txt_preview.config(state="disabled")
            
            # 2. Audio generieren
            self.lbl_status.config(text="Status: Generiere Audio...", fg="#4facfe")
            self.engine.generate_and_play(txt, "Unknown")
            
            self.lbl_status.config(text="Status: Fertig (Bereit)", fg="#4caf50")
            
        except Exception as e:
            self.log(f"Fehler: {e}")
            self.lbl_status.config(text="Status: Fehler", fg=COLOR_ACCENT)

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
