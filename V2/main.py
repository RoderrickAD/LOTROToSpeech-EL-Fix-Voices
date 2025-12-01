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
COLOR_ACCENT = "#782221"        # Dunkelrot (für Fehler/Wichtige Info)

FONT_UI = ("Georgia", 11)       
FONT_TITLE = ("Georgia", 22, "bold")
FONT_BOLD = ("Georgia", 11, "bold")
FONT_MONO = ("Consolas", 10)

class LotroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LOTRO Voice Companion 2.0")
        self.root.geometry("1000x850")
        self.root.configure(bg=COLOR_BG_MAIN)
        
        self.setup_styles()
        
        self.engine = VoiceEngine()
        self.running = False
        self.hotkey_hook = None
        self.old_log_content = "" 

        # Custom Notebook (Tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=15, pady=15)

        # Tabs erstellen
        self.tab_main = self.create_tab_frame(self.notebook)
        self.tab_settings = self.create_tab_frame(self.notebook)

        self.notebook.add(self.tab_main, text="  Scannen & Status  ")
        self.notebook.add(self.tab_settings, text="  Einstellungen  ")

        self.setup_main_tab()
        self.setup_settings_tab()

        self.load_settings_to_ui()
        self.register_hotkey()
        self.update_log_preview()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("TNotebook", background=COLOR_BG_MAIN, borderwidth=0)
        style.configure("TNotebook.Tab", 
                        background=COLOR_BTN_BG, 
                        foreground=COLOR_TEXT_SILVER, 
                        font=FONT_BOLD, 
                        padding=[15, 5])
        style.map("TNotebook.Tab", 
                  background=[("selected", COLOR_BG_FRAME)], 
                  foreground=[("selected", COLOR_TEXT_GOLD)])

        style.configure("TFrame", background=COLOR_BG_FRAME)
        style.configure("TLabel", background=COLOR_BG_FRAME, foreground=COLOR_TEXT_SILVER, font=FONT_UI)
        style.configure("Header.TLabel", foreground=COLOR_TEXT_GOLD, font=FONT_TITLE)
        style.configure("Check.TCheckbutton", background=COLOR_BG_FRAME, foreground=COLOR_TEXT_SILVER, font=FONT_UI)
        
        # NEU: Style für den Haupt-Status-Text (größer und zentriert)
        style.configure("Status.TLabel", 
                        background=COLOR_ENTRY_BG, 
                        foreground="#4caf50", 
                        font=("Georgia", 14, "bold"),
                        padding=[10, 10], 
                        anchor="center")
        
        # NEU: Style für den Log-Header
        style.configure("LogHeader.TLabel", foreground=COLOR_TEXT_GOLD, font=FONT_BOLD)

    def create_tab_frame(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        return frame

    def create_lotro_button(self, parent, text, command, bg_color=COLOR_BTN_BG):
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
        # Master Frame für 2 Spalten Layout
        master_content_frame = tk.Frame(self.tab_main, bg=COLOR_BG_FRAME)
        master_content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Linker Container (Text Vorschau) - Nimmt den meisten Platz
        left_frame = tk.Frame(master_content_frame, bg=COLOR_BG_FRAME, bd=2, relief="groove")
        left_frame.pack(side="left", fill="both", expand=True, padx=(5, 10), pady=5)
        
        # Rechter Container (Steuerung und Log) - Feste Breite
        right_frame = tk.Frame(master_content_frame, bg=COLOR_BG_FRAME, bd=2, relief="groove")
        right_frame.pack(side="right", fill="y", padx=(10, 5), pady=5, anchor="n") 
        right_frame.config(width=350)
        right_frame.pack_propagate(False) 
        
        # --- LINKER BEREICH: TEXT VORSCHAU ---
        
        ttk.Label(left_frame, text="Erkannter Quest-Text", style="Header.TLabel").pack(pady=(10, 5))
        
        # Ein Wrapper-Frame für das Text-Widget mit Padding
        text_wrapper = tk.Frame(left_frame, bg=COLOR_ENTRY_BG, bd=1, relief="flat")
        text_wrapper.pack(fill="both", expand=True, padx=15, pady=5)

        self.txt_preview = tk.Text(text_wrapper, height=35, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT_SILVER, 
                                   insertbackground="white", font=("Georgia", 12), relief="flat", padx=10, pady=10)
        self.txt_preview.pack(fill="both", expand=True)
        self.txt_preview.config(state="disabled")

        # --- RECHTER BEREICH: STEUERUNG & LOG ---

        # 1. Steuerung (Rechts Oben)
        control_frame = tk.Frame(right_frame, bg=COLOR_BG_FRAME, padx=10, pady=10)
        control_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(control_frame, text="Status & Steuerung", foreground=COLOR_TEXT_GOLD, font=FONT_BOLD).pack(pady=(10, 5))
        
        # Status Panel - Verwendung des neuen Styles
        self.lbl_status = ttk.Label(control_frame, text="Status: Bereit (Warte auf Taste...)", 
                                   style="Status.TLabel") 
        self.lbl_status.pack(fill="x", pady=10)

        # Action Button
        self.btn_action = self.create_lotro_button(control_frame, "🔊 HOTKEY-Scan Auslösen", self.run_once_manual)
        self.btn_action.pack(fill="x", pady=10, ipady=5)
        
        self.lbl_hotkey = ttk.Label(control_frame, text=f"Hotkey: {self.engine.config.get('hotkey', 'ctrl+alt+s')}", 
                                    foreground=COLOR_ACCENT)
        self.lbl_hotkey.pack(pady=(5, 10))

        # 2. Log Vorschau (Rechts Unten)
        log_container = tk.Frame(right_frame, bg=COLOR_BG_FRAME)
        log_container.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        ttk.Label(log_container, text="System-Log Vorschau:", style="LogHeader.TLabel").pack(anchor="w", pady=(10, 5))
        
        # Log-Widget
        self.log_widget = scrolledtext.ScrolledText(log_container, state='disabled', height=15, bg=COLOR_ENTRY_BG, fg="#a0a0a0", font=FONT_MONO, relief="flat")
        self.log_widget.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        # Haupt-Container für Padding
        container = tk.Frame(self.tab_settings, bg=COLOR_BG_FRAME)
        container.pack(fill="both", expand=True, padx=40, pady=20)
        
        # Scroll-Bereich
        canvas = tk.Canvas(container, bg=COLOR_BG_FRAME, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_BG_FRAME)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="top", fill="both", expand=True) 
        scrollbar.pack(side="right", fill="y")
        
        # Helferfunktion für Einträge im scrollable_frame
        def create_entry(parent_frame, label_text, show=None):
            ttk.Label(parent_frame, text=label_text).pack(anchor="w", pady=(10, 2))
            entry = tk.Entry(parent_frame, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT_SILVER, insertbackground="white", font=FONT_MONO, relief="flat", bd=5)
            if show: entry.config(show=show)
            entry.pack(fill="x", pady=2, ipady=3)
            return entry
        
        # Helferfunktion für Text-Feld im scrollable_frame (für die Whitelist)
        def create_text_field(parent_frame, label_text):
            ttk.Label(parent_frame, text=label_text).pack(anchor="w", pady=(10, 2))
            text_field = tk.Text(parent_frame, height=3, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT_SILVER, insertbackground="white", font=FONT_MONO, relief="flat", bd=5, padx=5, pady=5)
            text_field.pack(fill="x", pady=2)
            return text_field

        # Sektion 1: API & Audio
        api_frame = tk.LabelFrame(scrollable_frame, text="ElevenLabs API & Audio Konfiguration", bg=COLOR_BG_FRAME, fg=COLOR_TEXT_GOLD, font=FONT_BOLD, padx=15, pady=15)
        api_frame.pack(fill="x", pady=(10, 15), padx=5)

        self.ent_api_key = create_entry(api_frame, "ElevenLabs API Key:", show="*")
        self.ent_delay = create_entry(api_frame, "Verzögerung vor Audio-Wiedergabe (Sekunden):")
        self.ent_hotkey = create_entry(api_frame, "Globaler Hotkey (z.B. ctrl+alt+s):")
        
        # Sektion 2: OCR & Pfade
        ocr_frame = tk.LabelFrame(scrollable_frame, text="OCR & Pfad Konfiguration", bg=COLOR_BG_FRAME, fg=COLOR_TEXT_GOLD, font=FONT_BOLD, padx=15, pady=15)
        ocr_frame.pack(fill="x", pady=(15, 15), padx=5)

        self.ent_tesseract = create_entry(ocr_frame, "Pfad zu Tesseract.exe:")
        self.ent_logpath = create_entry(ocr_frame, "Pfad zur LOTRO Script.log:")
        
        ttk.Label(ocr_frame, text="Monitor Auswahl:").pack(anchor="w", pady=(10, 2))
        self.cmb_monitor = ttk.Combobox(ocr_frame, values=["1", "2", "3", "4"], state="readonly", font=FONT_UI)
        self.cmb_monitor.pack(fill="x", pady=2, ipady=3)
        self.cmb_monitor.set("1")

        # NEUE OCR-EINSTELLUNGEN
        ocr_advanced_frame = tk.LabelFrame(scrollable_frame, text="OCR Detail-Konfiguration (Nur für Experten)", bg=COLOR_BG_FRAME, fg=COLOR_TEXT_GOLD, font=FONT_BOLD, padx=15, pady=15)
        ocr_advanced_frame.pack(fill="x", pady=(15, 15), padx=5)
        
        self.ent_ocr_lang = create_entry(ocr_advanced_frame, "Tesseract Sprachen (z.B. deu+eng):")
        self.ent_ocr_psm = create_entry(ocr_advanced_frame, "Tesseract PSM Modus (Standard: 6):")
        self.txt_ocr_whitelist = create_text_field(ocr_advanced_frame, "Tesseract Whitelist (Erlaubte Zeichenkette):")

        # Debug Checkbox (außerhalb der LabelFrames)
        self.var_debug = tk.BooleanVar()
        ttk.Checkbutton(scrollable_frame, text="Debug-Bilder (Screenshots/Verarbeitung) speichern", 
                        variable=self.var_debug, style="Check.TCheckbutton").pack(anchor="w", pady=15, padx=5)
        
        # Button am unteren Rand (immer sichtbar, außerhalb des Scroll-Containers)
        self.btn_save = self.create_lotro_button(container, "💾 Einstellungen Speichern & Stimmen aktualisieren", self.save_settings)
        self.btn_save.pack(pady=(10, 0), fill="x")

    # --- FUNKTIONEN ---
    
    def log(self, msg):
        log_message(msg)
    
    def update_log_preview(self):
        """ Aktualisiert das Log-Widget, indem app.log gelesen wird. """
        try:
            with open("app.log", "r", encoding="utf-8") as f:
                current_content = f.read()
            
            if current_content != self.old_log_content:
                self.log_widget.config(state='normal')
                self.log_widget.delete(1.0, tk.END)
                self.log_widget.insert(tk.END, current_content)
                self.log_widget.see(tk.END)
                self.log_widget.config(state='disabled')
                self.old_log_content = current_content
                
        except FileNotFoundError:
            pass 
        except Exception as e:
            self.log_widget.config(state='normal')
            self.log_widget.insert(tk.END, f"\nFehler beim Lesen der Log-Datei: {e}")
            self.log_widget.config(state='disabled')

        self.root.after(1000, self.update_log_preview)


    def load_settings_to_ui(self):
        cfg = self.engine.config
        
        # Felder leeren
        fields = [self.ent_api_key, self.ent_tesseract, self.ent_logpath, self.ent_hotkey, self.ent_delay, self.ent_ocr_lang, self.ent_ocr_psm]
        for field in fields:
            field.delete(0, tk.END)
        self.txt_ocr_whitelist.delete(1.0, tk.END)

        # Werte einfügen
        self.ent_api_key.insert(0, cfg.get("api_key", ""))
        self.ent_tesseract.insert(0, cfg.get("tesseract_path", ""))
        self.ent_logpath.insert(0, cfg.get("lotro_log_path", ""))
        self.ent_hotkey.insert(0, cfg.get("hotkey", "ctrl+alt+s"))
        self.ent_delay.insert(0, str(cfg.get("audio_delay", 0.5)))
        self.cmb_monitor.set(str(cfg.get("monitor_index", 1)))
        self.var_debug.set(cfg.get("debug_mode", False))
        
        # NEUE OCR-WERTE
        self.ent_ocr_lang.insert(0, cfg.get("ocr_language", "deu+eng"))
        self.ent_ocr_psm.insert(0, str(cfg.get("ocr_psm", 6)))
        self.txt_ocr_whitelist.insert(1.0, cfg.get("ocr_whitelist", 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzäöüÄÖÜß0123456789.,?!:;\'"()[]-/'))
        
        self.lbl_hotkey.config(text=f"Hotkey: {cfg.get('hotkey', 'ctrl+alt+s')}")

    def save_settings(self):
        cfg = self.engine.config
        cfg["api_key"] = self.ent_api_key.get().strip()
        cfg["tesseract_path"] = self.ent_tesseract.get().strip()
        cfg["lotro_log_path"] = self.ent_logpath.get().strip()
        
        new_hotkey = self.ent_hotkey.get().strip()
        cfg["hotkey"] = new_hotkey
        self.lbl_hotkey.config(text=f"Hotkey: {new_hotkey}")

        # NEUE OCR-WERTE speichern
        cfg["ocr_language"] = self.ent_ocr_lang.get().strip()
        cfg["ocr_whitelist"] = self.txt_ocr_whitelist.get(1.0, tk.END).strip()

        try:
            cfg["audio_delay"] = float(self.ent_delay.get().strip())
            cfg["monitor_index"] = int(self.cmb_monitor.get())
            cfg["debug_mode"] = self.var_debug.get()
            cfg["ocr_psm"] = int(self.ent_ocr_psm.get().strip())
        except ValueError:
            messagebox.showerror("Fehler", "Zahlenformat (Verzögerung/Monitor/PSM) ist falsch.")
            return

        save_config(cfg)
        self.engine.config = cfg
        # Tesseract-Pfad in der Engine neu setzen, falls er geändert wurde
        self.engine.pytesseract.pytesseract.tesseract_cmd = cfg["tesseract_path"] 
        self.register_hotkey()
        
        # Starte Stimmen-Aktualisierung asynchron
        threading.Thread(target=self.engine.fetch_voices).start() 
        messagebox.showinfo("Gespeichert", "Einstellungen wurden übernommen und Stimmen werden aktualisiert.")

    def register_hotkey(self):
        hk = self.engine.config.get("hotkey", "ctrl+alt+s")
        if self.hotkey_hook:
            try: keyboard.remove_hotkey(self.hotkey_hook)
            except: pass
        try:
            # Hotkey startet den manuellen Scan
            self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.root.after(0, self.run_once_manual))
            self.log(f"Hotkey aktiviert ({hk})")
        except: self.log(f"Hotkey Fehler: Konnte '{hk}' nicht registrieren.")

    def run_once_manual(self):
        """ Scannt und liest vor (Einmalig) """
        self.lbl_status.config(text="Status: Scanne...", style="Status.TLabel", foreground=COLOR_TEXT_GOLD) 
        self.log("Manuelle Scan-Anforderung erhalten.")
        threading.Thread(target=self.process_pipeline, daemon=True).start()

    def process_pipeline(self):
        """ Führt die Pipeline (OCR -> TTS) im Hintergrund aus. """
        try:
            # 1. OCR Scan
            txt = self.engine.run_ocr()
            
            if not txt or len(txt) < 5:
                self.log("Kein Text gefunden (OCR-Ergebnis zu kurz oder leer).")
                self.root.after(0, lambda: self.lbl_status.config(text="Status: Kein Text gefunden", style="Status.TLabel", foreground=COLOR_ACCENT)) 
                self.root.after(0, lambda: self.update_text_preview("--- Kein verwertbarer Dialogtext gefunden ---"))
                return

            self.log(f"Erkannt: {txt[:70]}{'...' if len(txt) > 70 else ''}")
            
            # GUI Update (muss im Haupt-Thread erfolgen)
            self.root.after(0, lambda: self.update_text_preview(txt))
            
            # 2. Audio generieren
            self.root.after(0, lambda: self.lbl_status.config(text="Status: Generiere Audio...", style="Status.TLabel", foreground="#4facfe")) 
            self.engine.generate_and_play(txt, "Unknown")
            
            self.root.after(0, lambda: self.lbl_status.config(text="Status: Fertig (Bereit)", style="Status.TLabel", foreground="#4caf50"))
            
        except Exception as e:
            self.log(f"FEHLER in der Pipeline: {e}")
            self.root.after(0, lambda: self.lbl_status.config(text="Status: FEHLER", style="Status.TLabel", foreground=COLOR_ACCENT))

    def update_text_preview(self, txt):
        """ Aktualisiert das Text-Widget (muss im Haupt-Thread laufen) """
        self.txt_preview.config(state="normal")
        self.txt_preview.delete(1.0, tk.END)
        self.txt_preview.insert(tk.END, txt)
        self.txt_preview.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
