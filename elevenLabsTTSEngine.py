import pygame
import os
import re
import globalVariables
from elevenlabs import save
from elevenlabs.client import ElevenLabs
import time
from tkinter import messagebox
import setVoiceByGender
import elevenlabs_manager  # NEU: Import für die Zuweisungs-Logik

def stop_audio():
    pygame.mixer.music.stop()
    pygame.mixer.music.unload()


def play_audio(audio):
    pygame.mixer.music.load(audio)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.music.unload()


def tts_engine(text, test=False):
    create_api_key_file()
    create_elevenlabs_model_file()

    if not os.path.exists(globalVariables.audio_path_string):
        os.makedirs(globalVariables.audio_path_string)

    words = text.split()

    # Create a simple filename from first few words
    if len(words) > 0:
        first_5_words = "".join(words[:5]).lower()
        first_5_words = re.sub(r'[^a-zA-Z0-9]', '', first_5_words)
    else:
        first_5_words = "unknown_audio"

    audio_file = globalVariables.audio_path_string + "/" + first_5_words + ".mp3"

    key = load_api_key()

    model = load_elevenlabs_model()

    if globalVariables.already_talked and not test:
        return

    if os.path.exists(audio_file):
        play_audio(audio_file)
    else:
        if text:
            if key:
                try:
                    client = ElevenLabs(
                        api_key=key,
                    )

                    # --- NEUE LOGIK START ---
                    voice = None
                    
                    # Versuche, eine dynamische Stimme zu finden, wenn wir nicht im Test-Modus sind
                    # und der Pool geladen wurde.
                    if hasattr(globalVariables, 'voice_pool') and globalVariables.voice_pool and not test:
                        # Hole NPC Infos sicherheitshalber mit getattr, falls sie leer sind
                        npc_name = getattr(globalVariables, 'npc_name', '')
                        npc_gender = getattr(globalVariables, 'npc_gender', '')
                        
                        print(f"Suche Stimme für NPC: '{npc_name}' ({npc_gender})")
                        
                        voice = elevenlabs_manager.get_voice_for_npc(
                            npc_name, 
                            npc_gender, 
                            globalVariables.voice_pool
                        )
                    
                    # Fallback: Wenn keine dynamische Stimme gefunden wurde (oder wir im Test sind),
                    # nutze die alte Standard-Logik
                    if not voice:
                        print("Nutze Standard-Stimme (Fallback).")
                        voice = setVoiceByGender.set_voice("elevenlabs")
                    else:
                        print(f"Dynamische Stimme angewendet: {voice}")
                    # --- NEUE LOGIK ENDE ---

                    if model:
                        set_model = model
                    else:
                        set_model = "eleven_turbo_v2_5"

                    audio = client.text_to_speech.convert(
                        voice_id=voice,
                        text=text,
                        model_id=set_model,
                        output_format="mp3_44100_128"
                    )

                    save(audio, audio_file)

                    play_audio(audio_file)

                except Exception as e:
                    messagebox.showerror("Error", str(e))
            else:
                messagebox.showerror("Error", "No API Key.")
                time.sleep(3)

    globalVariables.already_talked = True


def create_api_key_file():
    if not os.path.exists(globalVariables.config_path):
        os.makedirs(globalVariables.config_path)

    try:
        with open(globalVariables.config_path + r"/api_key.txt", "x") as file:
            pass
    except FileExistsError:
        pass


def load_api_key():
    key = ""

    try:
        with open(globalVariables.config_path + r"/api_key.txt", "r") as file:
            lines = file.readlines()

            if len(lines) > 0:
                key = lines[0].strip()

            return key
    except FileNotFoundError:
        return ""


def create_elevenlabs_model_file():
    if not os.path.exists(globalVariables.config_path):
        os.makedirs(globalVariables.config_path)

    try:
        with open(globalVariables.config_path + r"/elevenlabs_model.txt", "x") as file:
            pass
    except FileExistsError:
        pass


def load_elevenlabs_model():
    model = ""

    try:
        with open(globalVariables.config_path + r"/elevenlabs_model.txt", "r") as file:
            lines = file.readlines()

            if len(lines) > 0:
                model = lines[0].strip()

            return model
    except FileNotFoundError:
        return ""
