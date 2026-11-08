"""Warm the narration cache for hero objects so the demo works offline.

Runs the same path as a live click (real facts -> Gemini story -> ElevenLabs mp3),
so the cached audio is exactly what the app would produce on demand.

Usage (from backend/):  python -m scripts.pregen_audio
Run it on the machine that will serve the demo; audio_cache/ is created there.

HERO_SATELLITES names must match the CelesTrak catalog names exactly
(story.py matches on the full name, so "ISS" alone will not find "ISS (ZARYA)").
"""
import asyncio
import sys

from audio import AudioError, audio_url, narrate
from data_pipeline import fetch_asteroids
from story import fallback_story, get_story

HERO_SATELLITES = [
    "ISS (ZARYA)",
    "HST",
    "CSS (TIANHE)",
]


async def hero_targets() -> list[tuple[str, str]]:
    targets = [(name, "satellite") for name in HERO_SATELLITES]
    try:
        asteroids = await fetch_asteroids()
        if asteroids:  # sorted by miss distance, so [0] is this week's closest
            targets.append((asteroids[0]["name"], "asteroid"))
    except Exception as error:  # still warm the satellites if NASA is down
        print(f"skipping closest asteroid: {error}")
    return targets


async def main() -> int:
    failures = 0
    for name, kind in await hero_targets():
        story = await get_story(name, kind)
        if story == fallback_story(name):
            print(f"WARNING {name}: no facts/Gemini story, narrating the generic fallback")
            failures += 1
        try:
            print(f"{name}: {audio_url(narrate(story))}\n  {story}\n")
        except AudioError as error:
            print(f"{name}: {error} (copy .env.example to .env and fill in ELEVENLABS_API_KEY)")
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
