import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from engine import VoiceEngine
from utils import save_config, load_config, load_mapping, log_message

class LotroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LOTRO Voice Companion 2.0")
        self.root.geometry("600x500")
        
        self.engine = VoiceEngine()
        self.running = False
        self.selection_rect = None

        # --- Tabs erstellen ---
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

        # Laden der Config in die GUI
        self.load_settings_to_ui()

    def setup_main_tab(self):
        frame = ttk.Frame(self.tab_main, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="LOTRO Voice Companion", font=("Helvetica", 16, "bold")).pack(pady=10)
        
        self.btn_area = ttk.Button(frame, text="OCR Bereich auswählen", command=self.select_area)
        self.btn_area.pack(pady=5, fill="x")

        self.lbl_status = ttk.Label(frame, text="Status: Bereit", foreground="green")
        self.lbl_status.pack(pady=10)

        self.btn_start = ttk.Button(frame, text="Start Überwachung", command=self.toggle_monitoring)
        self.btn_start.pack(pady=5, fill="x")

        ttk.Label(frame, text="Letzter erkannter Text:", font=("Helvetica", 10, "bold")).pack(pady=(20, 5), anchor="w")
        self.txt_preview = tk.Text(frame, height=5, width=50, state="disabled")
        self.txt_preview.pack(fill="both", expand=True)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ElevenLabs API Key:").pack(anchor="w")
        self.ent_api_key = ttk.Entry(frame, width=50, show="*")
        self.ent_api_key.pack(fill="x", pady=5)

        ttk.Label(frame, text="Pfad zu Tesseract.exe:").pack(anchor="w", pady=(10, 0))
        self.ent_tesseract = ttk.Entry(frame, width=50)
        self.ent_tesseract.pack(fill="x", pady=5)

        ttk.Label(frame, text="Pfad zur Script.log (Plugin):").pack(anchor="w", pady=(10, 0))
        self.ent_logpath = ttk.Entry(frame, width=50)
        self.ent_logpath.pack(fill="x", pady=5)

        ttk.Button(frame, text="Speichern & Stimmen laden", command=self.save_settings).pack(pady=20)

    def setup_mapping_tab(self):
        frame = ttk.Frame(self.tab_mapping, padding=10)
        frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(frame, columns=("NPC", "VoiceID"), show="headings")
        self.tree.heading("NPC", text="NPC Name")
        self.tree.heading("VoiceID", text="Zugewiesene Stimme")
        self.tree.pack(fill="both", expand=True, side="left")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        ttk.Button(self.tab_mapping, text="Liste aktualisieren", command=self.refresh_mapping).pack(pady=5)

    def setup_logs_tab(self):
        self.log_widget = scrolledtext.ScrolledText(self.tab_logs, state='disabled')
        self.log_widget.pack(fill="both", expand=True)

    def log(self, message):
        """ Thread-sicheres Logging in GUI """
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, message + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state='disabled')

    def load_settings_to_ui(self):
        cfg = self.engine.config
        self.ent_api_key.insert(0, cfg.get("api_key", ""))
        self.ent_tesseract.insert(0, cfg.get("tesseract_path", ""))
        self.ent_logpath.insert(0, cfg.get("lotro_log_path", ""))
        self.refresh_mapping()

    def save_settings(self):
        cfg = self.engine.config
        cfg["api_key"] = self.ent_api_key.get().strip()
        cfg["tesseract_path"] = self.ent_tesseract.get().strip()
        cfg["lotro_log_path"] = self.ent_logpath.get().strip()
        save_config(cfg)
        
        # Reload Engine Config
        self.engine.config = cfg
        # Stimmen neu laden
        threading.Thread(target=self.engine.fetch_voices).start()
        messagebox.showinfo("Info", "Einstellungen gespeichert.")

    def refresh_mapping(self):
        # Tabelle leeren
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        mapping = load_mapping()
        # Versuche Namen für IDs zu finden
        voice_map = {v['voice_id']: v['name'] for v in self.engine.voices}
        
        for npc, vid in mapping.items():
            readable_voice = voice_map.get(vid, vid) # Name oder ID falls Name unbekannt
            self.tree.insert("", "end", values=(npc, readable_voice))

    def select_area(self):
        self.root.iconify() # Fenster minimieren
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
            
            # Speichern
            cfg = self.engine.config
            cfg["ocr_coords"] = [x1, y1, x2, y2]
            save_config(cfg)
            
            top.destroy()
            self.root.deiconify()
            self.log(f"Bereich gespeichert: {x1},{y1} bis {x2},{y2}")

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

    def toggle_monitoring(self):
        if not self.running:
            self.running = True
            self.btn_start.config(text="Stop Überwachung")
            self.lbl_status.config(text="Status: Läuft...", foreground="red")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            self.running = False
            self.btn_start.config(text="Start Überwachung")
            self.lbl_status.config(text="Status: Bereit", foreground="green")

    def monitor_loop(self):
        last_text = ""
        while self.running:
            text = self.engine.run_ocr()
            
            if text and len(text) > 5 and text != last_text:
                self.log(f"Text erkannt: {text[:30]}...")
                
                # GUI Update (Thread sicher machen wäre besser, aber für einfaches Beispiel ok)
                self.txt_preview.config(state="normal")
                self.txt_preview.delete(1.0, tk.END)
                self.txt_preview.insert(tk.END, text)
                self.txt_preview.config(state="disabled")
                
                # Audio generieren
                self.engine.generate_and_play(text, "Unknown") # Name wird intern aus Log geholt
                
                # Update Mapping Tabelle falls was neues dazu kam
                self.root.after(100, self.refresh_mapping)
                
                last_text = text
            
            time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = LotroApp(root)
    root.mainloop()
