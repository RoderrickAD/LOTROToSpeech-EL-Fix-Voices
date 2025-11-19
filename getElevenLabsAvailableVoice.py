from elevenlabs.client import ElevenLabs
import globalVariables


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


def get_elevenlabs_default_voice():
    try:
        client = ElevenLabs(api_key=load_api_key())

        voices_response = client.voices.get_all(show_legacy=False)
        all_voices = voices_response.voices

        for voice in all_voices:
            if voice.labels and voice.labels.get("gender", "").lower() == "male":
                return voice.voice_id

        for voice in all_voices:
            if voice.labels and voice.labels.get("gender", "").lower() == "female":
                return voice.voice_id

        return all_voices[0].voice_id if all_voices else None

    except Exception:
        return None
