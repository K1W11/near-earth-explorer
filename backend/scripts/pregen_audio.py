"""Pre-generate narration for hero objects so the demo works offline.

Usage (from backend/):  python -m scripts.pregen_audio
Edit HERO_STORIES, or swap in M1's story generator once it exists.
"""
from audio import audio_url, narrate

HERO_STORIES = {
    "iss": "Hello from Near Earth Explorer. Right now, the International Space Station is racing "
           "around Earth at about 28,000 kilometres an hour. Look up: it is brighter than almost any star.",
}

if __name__ == "__main__":
    for name, text in HERO_STORIES.items():
        print(f"{name}: {audio_url(narrate(text))}")
