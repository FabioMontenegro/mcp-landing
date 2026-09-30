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
| `tutorial-1 - short.mp4` | 1080x1920, <= 45 s: ROI crop scaled to full width over a blurred, darkened copy of the frame, big centered caption |
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
