#!/usr/bin/env python3
"""render-tutorial.py -- still screenshots -> short branded tutorial video (ffmpeg).

Python 3.10, standard library only. Drives ffmpeg/ffprobe via subprocess argv lists.
Local only: nothing is uploaded, no site is touched.

Reads a config JSON (see tutorial-1.json) and renders into `output_dir`:

  <name> - youtube.mp4   1920x1080, 30 fps, H.264 CRF 18, yuv420p, AAC 48 kHz stereo (music bed)
                         intro card, one Ken Burns shot per screenshot with a lower-third caption pill,
                         crossfades, outro card with fade to black
  <name> - short.mp4     1080x1920, <= 45 s: per shot the region of interest scaled to full width over a
                         blurred/darkened copy of the same frame, big centered caption
  <name> - poster.jpg    1280x720 thumbnail (intro card look + inset of one screenshot)
  <name> - credits.txt   music attribution

Usage:
  python render-tutorial.py tutorial-1.json [--only youtube,short,poster] [--keep-build]

See README.md for the config / shot format.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1920, 1080          # YouTube frame
SW, SH = 1080, 1920        # Short frame
ZOOM_SCALE = 4             # screenshots are upscaled x4 before zoompan so the motion stays smooth
# RGB -> limited-range BT.709 YUV, so the colours match the bt709 tags written on the output
TO_YUV = "scale=out_color_matrix=bt709:out_range=tv"


# --------------------------------------------------------------------------- helpers
def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def ff_path(p: Path | str) -> str:
    """Escape a filesystem path for use inside a single-quoted ffmpeg filter option."""
    s = str(p).replace("\\", "/")
    return s.replace(":", "\\:").replace("'", "\\\\\\'")


def fnum(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def even(x: float) -> int:
    return int(round(x / 2.0)) * 2


def hexc(c: str) -> str:
    return "0x" + c.lstrip("#")


def first_existing(candidates) -> Path:
    for c in ([candidates] if isinstance(candidates, str) else candidates):
        if Path(c).exists():
            return Path(c)
    raise SystemExit(f"font not found, tried: {candidates}")


class Renderer:
    def __init__(self, cfg: dict, cfg_dir: Path, keep_build: bool):
        self.cfg = cfg
        self.cfg_dir = cfg_dir
        self.keep_build = keep_build
        self.ffmpeg, self.ffprobe = cfg["ffmpeg"], cfg["ffprobe"]
        self.fps = int(cfg["fps"])
        self.name = cfg["name"]
        self.out_dir = Path(cfg["output_dir"])
        self.build = self.out_dir / ".build" / self.name
        self.shots_dir = (cfg_dir / cfg["shots_dir"]).resolve()
        b = cfg["brand"]
        self.c = {k: hexc(v) for k, v in b.items()}
        self.f = {k: first_existing(v) for k, v in cfg["fonts"].items()}
        self._n = 0
        self.shots = [deep_merge(cfg["shot_defaults"], s) for s in cfg["shots"]]
        for s in self.shots:
            s["path"] = self.shots_dir / s["file"]
            if not s["path"].exists():
                raise SystemExit(f"screenshot not found: {s['path']}")

    # ---- infrastructure
    def run(self, args, capture=False) -> bytes:
        args = [str(a) for a in args]
        res = subprocess.run(args, capture_output=True)
        if res.returncode != 0:
            sys.stderr.write("\n[ffmpeg failed]\n" + " ".join(args) + "\n" + res.stderr.decode("utf-8", "replace") + "\n")
            raise SystemExit(1)
        return res.stdout if capture else b""

    def probe(self, path: Path) -> dict:
        out = self.run([self.ffprobe, "-v", "error", "-show_entries",
                        "format=duration,size:stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels",
                        "-of", "json", path], capture=True)
        return json.loads(out)

    def textfile(self, text: str) -> Path:
        self._n += 1
        p = self.build / f"text_{self._n:03d}.txt"
        p.write_text(text, encoding="utf-8")
        return p

    def enc_mid(self) -> list[str]:
        """Intermediate clips: near-lossless, identical timing/colour tags so xfade can join them."""
        return ["-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(self.fps),
                "-video_track_timescale", "90000", "-an"]

    def enc_final(self) -> list[str]:
        return ["-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", str(self.cfg["crf"]),
                "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
                "-color_trc", "bt709", "-r", str(self.fps), "-movflags", "+faststart"]

    # ---- text measurement (ink bounding box) using ffmpeg itself
    def measure(self, font: Path, size: int, textfile: Path, canvas=(2400, 220), margin=40):
        cw, ch = canvas
        vf = (f"drawtext=fontfile='{ff_path(font)}':textfile='{ff_path(textfile)}':fontsize={size}"
              f":fontcolor=white:x={margin}:y={margin}")
        raw = self.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={cw}x{ch}:r=1:d=1",
                        "-vf", vf, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture=True)
        x1 = 0
        for y in range(ch):
            row = raw[y * cw:(y + 1) * cw]
            x1 = max(x1, len(row.rstrip(b"\x00")))
        return max(x1 - margin, 1)

    # ---- caption pill: rounded surface box + accent stripe + text, as an RGBA PNG
    def make_pill(self, text: str, out_png: Path, fontsize: int, max_width: int) -> tuple[int, int]:
        acc_w, gap, pad_x, radius, opacity = 8, 22, 32, 18, 0.94
        font = self.f["caption"]
        tf = self.textfile(text)
        text_x = acc_w + gap + pad_x
        while True:
            tw = self.measure(font, fontsize, tf)
            pw = even(text_x + tw + pad_x)
            if pw <= max_width or fontsize <= 28:
                break
            fontsize -= 2
        ph = even(fontsize * 1.85)
        r = min(radius, ph // 2 - 1)
        a = int(round(255 * opacity))
        outside = f"gt(pow(max(max({r}-X,X-{pw - 1 - r}),0),2)+pow(max(max({r}-Y,Y-{ph - 1 - r}),0),2),{r * r})"
        graph = (f"color=c={self.c['surface']}:s={pw}x{ph}:r=1:d=1,format=gbrap,"
                 f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if({outside},0,{a})'[pill];"
                 f"color=c={self.c['accent']}:s={acc_w}x{ph}:r=1:d=1,format=gbrap[bar];"
                 f"[pill][bar]overlay=x=0:y=0:format=auto,format=gbrap,"
                 f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if({outside},0,alpha(X,Y))'[pill2];"
                 f"[pill2]drawtext=fontfile='{ff_path(font)}':textfile='{ff_path(tf)}':fontsize={fontsize}"
                 f":fontcolor={self.c['text']}:x={text_x}:y=(h-th)/2-{fontsize * 0.04:.1f},format=rgba[out]")
        self.run([self.ffmpeg, "-v", "error", "-y", "-filter_complex", graph, "-map", "[out]", "-frames:v", "1", out_png])
        return pw, ph

    # ---- brand background with a subtle dot grid
    def dotgrid(self, w: int, h: int, pitch: int = 44, dot: int = 3) -> Path:
        out = self.build / f"bg_{w}x{h}.png"
        if out.exists():
            return out
        bg, dc = self.cfg["brand"]["bg"].lstrip("#"), self.cfg["brand"]["dots"].lstrip("#")
        bgr, bgg, bgb = (int(bg[i:i + 2], 16) for i in (0, 2, 4))
        dr, dg, db = (int(dc[i:i + 2], 16) for i in (0, 2, 4))
        d = f"lt(mod(X+{pitch // 2},{pitch}),{dot})*lt(mod(Y+{pitch // 2},{pitch}),{dot})"
        vf = (f"format=gbrp,geq=r='if({d},{dr},{bgr})':g='if({d},{dg},{bgg})':b='if({d},{db},{bgb})',format=rgb24")
        self.run([self.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={self.c['bg']}:s={w}x{h}:r=1:d=1",
                  "-vf", vf, "-frames:v", "1", out])
        return out

    @staticmethod
    def drawtext(prev: str, nxt: str, ln: dict, tf: Path) -> str:
        x = ln.get("x", "(w-tw)/2")
        return (f"[{prev}]drawtext=fontfile='{ff_path(ln['font'])}':textfile='{ff_path(tf)}':fontsize={ln['size']}"
                f":fontcolor={ln['color']}:x={x}:y={ln['y']}"
                f":alpha='clip((t-{fnum(ln.get('delay', 0.0))})/{fnum(ln.get('fade', 0.5))},0,1)'[{nxt}]")

    # ---- a card (intro / outro): dot-grid background + timed text lines + accent bar
    def card(self, out: Path, w: int, h: int, dur: float, lines: list[dict], fade_out: float = 0.0):
        bg = self.dotgrid(w, h)
        graph, prev = [], "0:v"
        for i, ln in enumerate(lines):
            graph.append(self.drawtext(prev, f"l{i}", ln, self.textfile(ln["text"])))
            prev = f"l{i}"
        bar = 10
        graph.append(f"[{prev}]drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color={self.c['accent']}:t=fill[bar]")
        tail = f"fade=t=out:st={fnum(dur - fade_out)}:d={fnum(fade_out)}," if fade_out > 0 else ""
        graph.append(f"[bar]{tail}{TO_YUV},format=yuv420p[out]")
        self.run([self.ffmpeg, "-v", "error", "-y", "-loop", "1", "-framerate", self.fps, "-t", fnum(dur), "-i", bg,
                  "-filter_complex", ";".join(graph), "-map", "[out]", "-frames:v", round(dur * self.fps),
                  *self.enc_mid(), out])

    def L(self, text, font, size, color, y, delay=0.0, fade=0.5, x=None) -> dict:
        d = {"text": text, "font": self.f[font], "size": size, "color": self.c[color], "y": y, "delay": delay, "fade": fade}
        if x is not None:
            d["x"] = x
        return d

    def intro_card(self, out: Path, dur: float, w=W, h=H, vertical=False):
        i = self.cfg["intro"]
        base = self.cfg["short"]["intro_duration"] if vertical else i["duration"]
        kk = max(dur / base, 1.0)     # verse timing follows the (possibly longer) segment
        if vertical:
            head = ["One plugin", "to rule", "them all"]   # stacked headline for the narrow frame
            y = 700
            ls = [self.L("⚡", "symbol", 96, "accent", y - 190, 0.0),
                  self.L(i["label"], "mono", 36, "accent", y, 0.0)]
            for k, t in enumerate(head):
                ls.append(self.L(t, "heading", 128, "text", y + 70 + k * 140, 0.15 + k * 0.1))
            vy = y + 70 + 3 * 140 + 60
            for k, t in enumerate(i["verse"]):
                ls.append(self.L(t, "body", 40, "muted", vy + k * 62, (1.0 + k * 0.4) * kk, 0.4))
        else:
            ls = [self.L("⚡", "symbol", 72, "accent", 200, 0.0),
                  self.L(i["label"], "mono", 34, "accent", 300, 0.0),
                  self.L(i["headline"], "heading", 116, "text", 366, 0.15),
                  ]
            for k, t in enumerate(i["verse"]):
                ls.append(self.L(t, "body", 36, "muted", 590 + k * 58, (1.1 + k * 0.6) * kk, 0.5))
        self.card(out, w, h, dur, ls)

    def outro_card(self, out: Path, dur: float, vertical=False):
        o = self.cfg["outro"]
        if vertical:
            w, h = SW, SH
            ls = [self.L("⚡", "symbol", 110, "accent", 660, 0.0),
                  self.L(o["title"], "heading", 68, "text", 830, 0.2),
                  ]
            for k, t in enumerate(textwrap.wrap(o["tagline"], 22)):
                ls.append(self.L(t, "body", 44, "muted", 960 + k * 64, 0.6))
            self.card(out, w, h, dur, ls, fade_out=0.8)
        else:
            ls = [self.L("⚡", "symbol", 96, "accent", 300, 0.0),
                  self.L(o["title"], "heading", 104, "text", 430, 0.2),
                  self.L(o["tagline"], "body", 46, "muted", 580, 0.7),
                  ]
            self.card(out, W, H, dur, ls, fade_out=o["fade_out"])

    # ---- ROI geometry for the Ken Burns move
    @staticmethod
    def view_at(z: float, cx: float, cy: float):
        vw, vh = W / z, H / z
        vx = min(max(cx - vw / 2, 0), W - vw)
        vy = min(max(cy - vh / 2, 0), H - vh)
        return vx, vy

    def roi_out_box(self, s: dict):
        x0, y0, x1, y1 = s["roi"]
        rcx, rcy = (x0 + x1) / 2, (y0 + y1) / 2
        boxes = []
        for p in (0, 0.25, 0.5, 0.75, 1):
            z = 1 + (s["zoom"] - 1) * p
            vx, vy = self.view_at(z, W / 2 + (rcx - W / 2) * p, H / 2 + (rcy - H / 2) * p)
            boxes.append(((x0 - vx) * z, (y0 - vy) * z, (x1 - vx) * z, (y1 - vy) * z))
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

    @staticmethod
    def overlap(a, b) -> float:
        w = min(a[2], b[2]) - max(a[0], b[0])
        h = min(a[3], b[3]) - max(a[1], b[1])
        return max(w, 0) * max(h, 0)

    # ---- one screenshot shot (YouTube frame)
    def shot_clip(self, s: dict, idx: int, out: Path, dur: float):
        margin, fs = 72, 46
        n = round(dur * self.fps)
        m = n - 1
        z = float(s["zoom"])
        x0, y0, x1, y1 = s["roi"]
        rcx, rcy = (x0 + x1) / 2, (y0 + y1) / 2
        pill = self.build / f"pill_{idx:02d}.png"
        pw, ph = self.make_pill(s["caption"], pill, fs, W - 2 * margin)
        px = (W - pw) // 2
        box = self.roi_out_box(s)
        pad = 20
        roi_box = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
        bottom = (px, H - margin - ph, px + pw, H - margin)
        top = (px, margin, px + pw, margin + ph)
        ob, ot = self.overlap(bottom, roi_box), self.overlap(top, roi_box)
        if ob == 0:
            py, where = bottom[1], "bottom"
        elif ot < ob:
            py, where = top[1], "top"
        else:
            py, where = bottom[1], "bottom"
        note = "" if min(ob, ot) == 0 else f"  ! caption overlaps ROI by {min(ob, ot):.0f}px^2"
        print(f"    shot {idx} {s['file']}: zoom {z} -> ROI centre ({rcx:.0f},{rcy:.0f}), ROI out {tuple(int(v) for v in box)}, "
              f"pill {where}{note}")
        ze = f"(1+({fnum(z)}-1)*on/{m})"
        xe = f"clip(({W / 2}+({fnum(rcx)}-{W / 2})*on/{m})*{ZOOM_SCALE}-iw/{ze}/2,0,iw-iw/{ze})"
        ye = f"clip(({H / 2}+({fnum(rcy)}-{H / 2})*on/{m})*{ZOOM_SCALE}-ih/{ze}/2,0,ih-ih/{ze})"
        graph = (f"[0:v]scale={W * ZOOM_SCALE}:{H * ZOOM_SCALE}:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv444p,"
                 f"zoompan=z='{ze}':x='{xe}':y='{ye}':d={n}:s={W}x{H}:fps={self.fps}[base];"
                 f"[1:v]format=rgba,fade=t=in:st=0.7:d=0.4:alpha=1,{TO_YUV},format=yuva444p[cap];"
                 f"[base][cap]overlay=x={px}:y={py}:format=yuv444,{TO_YUV},format=yuv420p[out]")
        self.run([self.ffmpeg, "-v", "error", "-y", "-i", s["path"],
                  "-loop", "1", "-framerate", self.fps, "-t", fnum(dur), "-i", pill,
                  "-filter_complex", graph, "-map", "[out]", "-frames:v", n, *self.enc_mid(), out])

    # ---- one screenshot shot (vertical Short)
    def short_clip(self, s: dict, idx: int, out: Path, dur: float):
        n = round(dur * self.fps)
        m = n - 1
        cx, cy, cw, ch = s.get("short_crop") or (s["roi"][0], s["roi"][1], s["roi"][2] - s["roi"][0], s["roi"][3] - s["roi"][1])
        # the slow push-in ends exactly on the requested crop: start from a slightly larger one
        zk = 1.05
        ew, eh = min(cw * zk, W), min(ch * zk, H)
        ex = min(max(cx - (ew - cw) / 2, 0), W - ew)
        ey = min(max(cy - (eh - ch) / 2, 0), H - eh)
        cx, cy, cw, ch = int(ex), int(ey), even(ew), even(eh)
        fh = even(SW * ch / cw)
        panel_cy = 1120
        fy = panel_cy - fh // 2
        cap_lines = textwrap.wrap(s.get("short_caption") or s["caption"], 24)
        size, lh, cap_cy = 76, 96, 470
        top = cap_cy - len(cap_lines) * lh / 2
        print(f"    short {idx} {s['file']}: crop {cw}x{ch}@({cx},{cy}) -> panel {SW}x{fh} at y={fy}, caption {len(cap_lines)} lines")
        graph = [f"[0:v]crop={W}:{H - 48}:0:48,scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
                 f"scale={SW}:{SH}:flags=bicubic,eq=brightness=-0.3:saturation=0.6,"
                 f"drawbox=x=0:y=0:w=iw:h=ih:color={self.c['bg']}@0.8:t=fill,format=yuv444p[bg]",
                 f"[1:v]crop={cw}:{ch}:{cx}:{cy},scale={SW * 2}:-2:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv444p,"
                 f"zoompan=z='1+({zk}-1)*on/{m}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s={SW}x{fh}:fps={self.fps}[fg]",
                 f"[bg][fg]overlay=x=0:y={fy}:format=yuv444[c0]",
                 f"[c0]drawbox=x=0:y={fy - 3}:w={SW}:h=3:color={self.c['accent']}@0.9:t=fill,"
                 f"drawbox=x=0:y={fy + fh}:w={SW}:h=3:color={self.c['accent']}@0.9:t=fill[c1]"]
        prev = "c1"
        extra = [self.L(self.cfg["intro"]["label"], "mono", 34, "accent", 150, 0.0, 0.3)]
        extra.append(self.L(self.cfg["outro"]["title"], "mono", 36, "muted", 1640, 0.0, 0.3))
        for k, t in enumerate(cap_lines):
            extra.append(self.L(t, "heading", size, "text", f"{top + k * lh:.0f}", 0.15 + k * 0.08, 0.4))
        for k, ln in enumerate(extra):
            graph.append(self.drawtext(prev, f"t{k}", ln, self.textfile(ln["text"])))
            prev = f"t{k}"
        graph.append(f"[{prev}]{TO_YUV},format=yuv420p[out]")
        self.run([self.ffmpeg, "-v", "error", "-y", "-loop", "1", "-framerate", self.fps, "-t", fnum(dur), "-i", s["path"],
                  "-i", s["path"], "-filter_complex", ";".join(graph), "-map", "[out]", "-frames:v", n,
                  *self.enc_mid(), out])

    # ---- join clips with crossfades + music bed
    def music_filter(self, mp: Path, total: float, src: str, label: str = "a", duck: str | None = None) -> str:
        mu = self.cfg["music"]
        dur = float(json.loads(self.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", mp],
                                        capture=True))["format"]["duration"])
        size = int(dur * 48000) + 48000
        fi, fo = float(mu["fade_in"]), float(mu["fade_out"])
        return (f"[{src}]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"aloop=loop=-1:size={size},atrim=end={fnum(total)},asetpts=PTS-STARTPTS,"
                f"volume={fnum(float(mu['volume_db']))}dB,afade=t=in:st=0:d={fnum(fi)},"
                f"afade=t=out:st={fnum(max(0.0, total - fo))}:d={fnum(fo)}"
                + (f",volume='{duck}':eval=frame" if duck else "") + f"[{label}]")

    # ---- narration
    def voice_file(self, v):
        if not v:
            return None
        p = Path(v)
        p = p if p.is_absolute() else (self.cfg_dir / p)
        if not p.exists():
            raise SystemExit(f"voice file not found: {p}")
        return p

    def wav_dur(self, p: Path) -> float:
        return float(json.loads(self.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", p],
                                         capture=True))["format"]["duration"])

    def seg_dur(self, base: float, voice) -> float:
        """Segment length: the configured one, or lead-in + voice + tail when the voice needs more. Frame-aligned."""
        vp = self.voice_file(voice)
        d = float(base)
        if vp:
            vc = self.cfg["voice"]
            d = max(d, vc["lead"] + self.wav_dur(vp) + vc["tail"])
        return -(-round(d * self.fps * 1000) // 1000) / self.fps

    def integrated_lufs(self, p: Path) -> float:
        res = subprocess.run([self.ffmpeg, "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=none",
                              "-f", "null", "-"], capture_output=True)
        txt = res.stderr.decode("utf-8", "replace")
        return float(txt.rsplit("I:", 1)[1].split("LUFS")[0])

    def voice_track(self, voices: list, starts: list, total: float, out: Path) -> list:
        """Mix the narration lines at their start times into one 48 kHz stereo WAV normalised to the target LUFS.
        Returns the (start, end) speaking intervals."""
        vc = self.cfg["voice"]
        args, graph, spans, k = [self.ffmpeg, "-v", "error", "-y"], [], [], 0
        for v, st in zip(voices, starts):
            vp = self.voice_file(v)
            if not vp:
                continue
            t0 = st + vc["lead"]
            args += ["-i", vp]
            graph.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={int(round(t0 * 1000))}:all=1[v{k}]")
            spans.append((t0, t0 + self.wav_dur(vp)))
            k += 1
        mix = "".join(f"[v{i}]" for i in range(k))
        graph.append(f"{mix}amix=inputs={k}:normalize=0:dropout_transition=0,apad,atrim=end={fnum(total)}[o]")
        raw = self.build / "voice_raw.wav"
        self.run(args + ["-filter_complex", ";".join(graph), "-map", "[o]", "-c:a", "pcm_s16le", raw])
        gain = float(vc["lufs"]) - self.integrated_lufs(raw)
        self.run([self.ffmpeg, "-v", "error", "-y", "-i", raw, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.9:level=disabled",
                  "-c:a", "pcm_s16le", out])
        print(f"  voice: {k} lines, gain {gain:+.1f} dB -> {self.integrated_lufs(out):.1f} LUFS")
        return spans

    def join(self, clips: list[Path], xf: float, out: Path, voices: list | None = None):
        lens = [round(float(self.probe(c)["format"]["duration"]) * self.fps) / self.fps for c in clips]
        args = [self.ffmpeg, "-v", "error", "-y"]
        for c in clips:
            args += ["-i", c]
        graph, prev, acc = [], "0:v", lens[0]
        starts = [0.0]
        for i in range(1, len(clips)):
            starts.append(acc - xf)
            graph.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={fnum(xf)}:offset={fnum(acc - xf)}[x{i}]")
            prev, acc = f"x{i}", acc + lens[i] - xf
        graph.append(f"[{prev}]format=yuv420p[v]")
        mp = Path(self.cfg["music"]["path"]) if self.cfg["music"].get("path") else None
        has_voice = bool(voices) and any(voices)
        if has_voice:
            vc = self.cfg["voice"]
            vwav = self.build / f"voice_{out.stem.split(' - ')[-1]}.wav"
            spans = self.voice_track(voices, starts, acc, vwav)
            for a_, b_ in zip(spans, spans[1:]):
                if b_[0] <= a_[1]:
                    raise SystemExit(f"voice lines overlap: {a_} / {b_}")
            print("  voice spans: " + ", ".join(f"{a_:.2f}-{b_:.2f}" for a_, b_ in spans))
            r = float(vc["ramp"])
            g = 10 ** (-float(vc["duck_db"]) / 20)
            env = [f"clip(min((t-{fnum(a_ - r)})/{r},({fnum(b_ + r)}-t)/{r}),0,1)" for a_, b_ in spans]
            d = env[0]
            for e in env[1:]:
                d = f"max({d},{e})"
            duck = f"1-(1-{g:.4f})*{d}"
        if mp and mp.exists():
            args += ["-i", mp]
            if has_voice:
                args += ["-i", vwav]
                graph.append(self.music_filter(mp, acc, f"{len(clips)}:a", "m", duck))
                graph.append(f"[m][{len(clips) + 1}:a]amix=inputs=2:normalize=0:duration=first,"
                             f"alimiter=limit=0.95:level=disabled[a]")
            else:
                graph.append(self.music_filter(mp, acc, f"{len(clips)}:a"))
            audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
        else:
            print("  ! no music track found, rendering with silence")
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            audio = ["-map", f"{len(clips)}:a", "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-t", fnum(acc)]
        self.run(args + ["-filter_complex", ";".join(graph), "-map", "[v]", *audio, *self.enc_final(), out])
        return acc

    # ---- deliverables
    def timeline(self, vertical: bool):
        """Per-segment durations and voices: intro, shots, outro."""
        sc, i, o = self.cfg["short"], self.cfg["intro"], self.cfg["outro"]
        segs = [(sc["intro_duration"] if vertical else i["duration"], i.get("voice"))]
        segs += [(sc["shot_duration"] if vertical else s["duration"], s.get("voice")) for s in self.shots]
        segs += [(sc["outro_duration"] if vertical else o["duration"], o.get("voice"))]
        return [self.seg_dur(d, v) for d, v in segs], [v for _, v in segs]

    def render_youtube(self) -> Path:
        durs, voices = self.timeline(False)
        parts = []
        p = self.build / "yt_intro.mp4"
        self.intro_card(p, durs[0])
        parts.append(p)
        for i, s in enumerate(self.shots, start=1):
            p = self.build / f"yt_shot_{i:02d}.mp4"
            self.shot_clip(s, i, p, durs[i])
            parts.append(p)
        p = self.build / "yt_outro.mp4"
        self.outro_card(p, durs[-1])
        parts.append(p)
        out = self.out_dir / f"{self.name} - youtube.mp4"
        total = self.join(parts, float(self.cfg["crossfade"]), out, voices)
        print(f"  segments {[round(d, 2) for d in durs]}  timeline {total:.2f}s")
        return out

    def render_short(self) -> Path:
        sc = self.cfg["short"]
        durs, voices = self.timeline(True)
        parts = []
        p = self.build / "sh_intro.mp4"
        self.intro_card(p, durs[0], SW, SH, vertical=True)
        parts.append(p)
        for i, s in enumerate(self.shots, start=1):
            p = self.build / f"sh_shot_{i:02d}.mp4"
            self.short_clip(s, i, p, durs[i])
            parts.append(p)
        p = self.build / "sh_outro.mp4"
        self.outro_card(p, durs[-1], vertical=True)
        parts.append(p)
        out = self.out_dir / f"{self.name} - short.mp4"
        total = self.join(parts, float(sc["crossfade"]), out, voices)
        print(f"  segments {[round(d, 2) for d in durs]}  timeline {total:.2f}s")
        if total > sc["max_duration"]:
            raise SystemExit(f"short is {total:.1f}s, over the {sc['max_duration']}s limit")
        return out

    def render_poster(self) -> Path:
        pc, pw, ph = self.cfg["poster"], 1280, 720
        bg = self.dotgrid(pw, ph, pitch=30, dot=2)
        inset = self.shots_dir / pc["inset"]
        iw = 540
        ls = [self.L("⚡", "symbol", 46, "accent", 70, -1.0, 0.001, x="72"),
              self.L(self.cfg["intro"]["label"], "mono", 30, "accent", 78, -1.0, 0.001, x="132")]
        for k, t in enumerate(pc["headline"]):
            ls.append(self.L(t, "heading", 96, "text", 140 + k * 108, -1.0, 0.001, x="72"))
        ls.append(self.L(pc["url"], "mono", 32, "muted", 604, -1.0, 0.001, x="72"))
        graph, prev = [], "bg"
        graph.append("[0:v]null[bg]")
        for i, ln in enumerate(ls):
            graph.append(self.drawtext(prev, f"l{i}", ln, self.textfile(ln["text"])))
            prev = f"l{i}"
        ix, iy = pw - 72 - iw - 8, 350
        graph.append(f"[1:v]scale={iw}:-2:flags=lanczos,pad=iw+8:ih+8:4:4:color={self.c['accent']}[ins]")
        graph.append(f"[{prev}][ins]overlay=x={ix}:y={iy}[c]")
        graph.append(f"[c]drawbox=x=0:y=ih-10:w=iw:h=10:color={self.c['accent']}:t=fill[out]")
        out = self.out_dir / f"{self.name} - poster.jpg"
        self.run([self.ffmpeg, "-v", "error", "-y", "-i", bg, "-i", inset, "-filter_complex", ";".join(graph),
                  "-map", "[out]", "-frames:v", "1", "-q:v", "2", out])
        return out

    def render(self, only: set[str]):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.build.mkdir(parents=True, exist_ok=True)
        outs = []
        if "youtube" in only:
            print("[youtube]")
            outs.append(self.render_youtube())
        if "short" in only:
            print("[short]")
            outs.append(self.render_short())
        if "poster" in only:
            print("[poster]")
            outs.append(self.render_poster())
        att = self.cfg["music"].get("attribution")
        if att:
            (self.out_dir / f"{self.name} - credits.txt").write_text(att + "\n", encoding="utf-8")
            print(f"  music credit: {att}")
        for o in outs:
            info = self.probe(o)
            v = next((x for x in info["streams"] if x["codec_type"] == "video"), {})
            a = next((x for x in info["streams"] if x["codec_type"] == "audio"), None)
            audio = f", audio {a.get('codec_name')} {a.get('sample_rate')} Hz {a.get('channels')}ch" if a else ""
            print(f"  -> {o.name}: {v.get('width')}x{v.get('height')} {v.get('avg_frame_rate', '')} "
                  f"{float(info['format'].get('duration', 0)):.2f}s {int(info['format']['size']) / 1e6:.1f} MB{audio}")
        if not self.keep_build:
            shutil.rmtree(self.build, ignore_errors=True)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--only", default="youtube,short,poster", help="comma list: youtube,short,poster")
    ap.add_argument("--keep-build", action="store_true", help="keep intermediate clips in <output_dir>/.build")
    a = ap.parse_args()
    cfg_path = Path(a.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for k in ("name", "output_dir", "shots", "ffmpeg", "ffprobe"):
        if k not in cfg:
            raise SystemExit(f"config missing '{k}'")
    Renderer(cfg, cfg_path.parent, a.keep_build).render({x.strip() for x in a.only.split(",")})


if __name__ == "__main__":
    main()
