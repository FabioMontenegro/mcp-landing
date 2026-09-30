# Tutorial video renderer

Turns still screenshots into a short branded tutorial video with ffmpeg. Python 3.10+ (standard library only) and ffmpeg/ffprobe (tested with 9.0.1 full build: needs `drawtext`, `zoompan`, `xfade`, `geq`). Local only: nothing is uploaded.

## Run

```
python render-tutorial.py tutorial-1.json                 # youtube + short + poster
python render-tutorial.py tutorial-1.json --only poster   # or youtube / short, comma separated
python render-tutorial.py tutorial-1.json --keep-build    # keep intermediate clips in <output_dir>/.build
```

Outputs go to `output_dir` (`F:\Mis ideas\enable-abilities\Videos\out\`):

| File | Spec |
|---|---|
| `tutorial-1 - youtube.mp4` | 1920x1080, 30 fps, H.264 CRF 18, yuv420p, AAC 48 kHz stereo with the music bed (1 s fade in, 2.5 s fade out) |
| `tutorial-1 - short.mp4` | 1080x1920, <= `short.max_duration` (60 s): ROI crop scaled to full width over a blurred, darkened copy of the frame, big centered caption |
| `tutorial-1 - poster.jpg` | 1280x720 thumbnail (intro look + inset screenshot) |
| `tutorial-1 - credits.txt` | Music attribution (Pixabay) to paste in the video description |

## Config (`tutorial-1.json`)

Paths (`ffmpeg`, `ffprobe`, fonts, music, `output_dir`) are absolute; `shots_dir` is relative to the JSON. Brand colors, intro/outro copy, poster text and Short timings live in the same file.

## Add or change a shot

Put a 1920x1080 PNG in `shots/` and add an entry to `shots` (order = timeline order):

```json
{
  "file": "07-new.png",
  "caption": "Text of the lower-third pill",
  "roi": [x0, y0, x1, y1],
  "short_crop": [x, y, w, h],
  "duration": 5.8,
  "zoom": 1.2
}
```

- `roi`: region of interest in source pixels. The Ken Burns move (1.0 to `zoom`) pushes toward its center.
- The caption pill sits bottom-center; if it would overlap the zoomed ROI it moves to the top. The render log prints the chosen position and warns about any remaining overlap.
- `short_crop`: crop used in the vertical cut (defaults to `roi`). Keep it wide-short: it is scaled to 1080 px width. Optional `short_caption` overrides the text.
- `duration` (default 5.8 s) and `zoom` (default 1.2) fall back to `shot_defaults`. Total length = intro + shots + outro - 0.4 s per crossfade; the Short is checked against `short.max_duration`.

## Voiceover (optional)

Add `"voice": "path/to/line.wav"` to `intro`, to any shot and to `outro` (absolute, or relative to the JSON). Segments without `voice` behave as before; with no voice at all the render is music only.

- Segment length becomes `max(configured duration, voice.lead + voice length + voice.tail)` (0.35 s lead-in, 0.6 s tail, from the `voice` block in the JSON). The voice starts 0.35 s into its segment. With the crossfade the gap between two lines is at least 0.55 s; the script aborts if two lines would overlap.
- The lines are mixed into one track, loudness-normalized to `voice.lufs` (-16 LUFS), and the music is ducked `voice.duck_db` (10 dB) under speech with `voice.ramp` (0.3 s) ramps. The verse animation stretches with the intro. Output stays AAC 48 kHz stereo (mono voice upmixed).
- The Short uses the same lines (and therefore also runs about 47 s).

### Generate the narration (Kokoro TTS)

`tts.py` writes one WAV per line (24 kHz mono), in order:

```
uv run --python 3.12 --with kokoro --with "misaki[en]" --with soundfile python tts.py OUT_DIR af_heart "line 1" "line 2" ...
```

Then point each segment's `voice` at `OUT_DIR/af_heart-NN.wav` (01 = intro, 02.. = shots in order, last = outro).
