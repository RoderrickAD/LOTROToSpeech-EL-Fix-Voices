# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# 1. Fügt das V3-Verzeichnis zum Suchpfad hinzu, damit PyInstaller die relativen Imports findet
#    Wir verwenden den Pfad, in dem die Spec-Datei liegt.
sys.path.append(os.path.join(os.path.dirname(__file__), 'V3'))

# Definiere den Haupt-Einstiegspunkt
block_cipher = None

# A. Analyse: Analysiere V3/main.py und alle abhängigen Dateien.
a = Analysis(
    # Einstiegspunkt
    ['V3/main.py'],
    pathex=['.'], # Starte die Suche im aktuellen Verzeichnis (Root)
    binaries=[],
    datas=[
        # Füge den gesamten "templates" Ordner hinzu (Quelle, Zielordner in der EXE)
        ('templates', 'templates'),
        
        # Manuelle Einbindung der Python-Module aus V3 (Sicherheit für relative Imports)
        ('V3/core.py', 'V3'),
        ('V3/ocr_service.py', 'V3'),
        ('V3/tts_service.py', 'V3'),
        ('V3/utils.py', 'V3'),
    ],
    # Hidden Imports für Bibliotheken, die PyInstaller oft vergisst
    hiddenimports=['cv2', 'numpy', 'pytesseract', 'mss', 'pygame'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

# B. Pyz (Zusammenfassung der Python-Module)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

# C. Exe (Erstellung der ausführbaren Datei)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LOTROVoiceCompanion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True # Zeigt die Konsole (für das Log-Fenster)
)
