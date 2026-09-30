"""Synthesize narration lines with Kokoro-82M (American English).

Usage:
  uv run --python 3.12 --with kokoro --with "misaki[en]" --with soundfile \
    python tts.py OUT_DIR VOICE "line one" ["line two" ...]
Writes OUT_DIR/<VOICE>-01.wav, -02.wav, ... at 24 kHz and prints each duration.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000


def main() -> None:
    out_dir, voice, *lines = sys.argv[1:]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pipeline = KPipeline(lang_code="a")
    for i, text in enumerate(lines, 1):
        chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=1.0)]
        audio = np.concatenate(chunks)
        path = out / f"{voice}-{i:02d}.wav"
        sf.write(path, audio, SAMPLE_RATE)
        print(f"{path.name}\t{len(audio) / SAMPLE_RATE:.2f}s\t{text}")


if __name__ == "__main__":
    main()
