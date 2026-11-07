"""Assemble the combined 52-second Vue/FastAPI demonstration/process video.

Requires macOS say, FFmpeg/FFprobe, and fresh supported-browser captures under
/tmp/marketstation-vue-demo. Screenshots are genuine UI data; only timing,
letterboxing/encoding and synthesized narration are added.
"""

from pathlib import Path
import json
import subprocess

frames = Path("/tmp/marketstation-vue-demo")
segments = [
    (
        10,
        "Vue and FastAPI power this dashboard. Actual Yahoo quotes and candlesticks update with volume, source times, data ages, and feed status.",
    ),
    (
        6,
        "The ledger preserves identities, source and receipt times, revisions, duplicate arrivals, and candle completeness.",
    ),
    (
        8,
        "Verification checks commit before broadcast. Newer duplicates advance the watermark, preventing older responses from overwriting current candles.",
    ),
    (
        8,
        "Disconnecting the real upstream feed marks both channels unavailable. Collection stops, observation age increases, and stored candles remain available.",
    ),
    (
        6,
        "Reconnecting resumes Yahoo collection. The dashboard waits for fresh messages; the database remains intact.",
    ),
    (
        14,
        "Recorded replay reads SQLite receipts in their original order. Here are playback, pause, seeking to the end, and restarting at a different speed. The recording is labeled, while live collection continues independently.",
    ),
]


def run(args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-3000:])
    return result


duration = sum(seconds for seconds, _ in segments)
if len(list(frames.glob("frame-*.jpg"))) != duration * 2:
    raise ValueError(
        "Expected 104 genuine half-second captures for this 52-second demo"
    )
for index, (seconds, narration) in enumerate(segments):
    aiff = frames / f"narration-{index}.aiff"
    run(["say", "-v", "Samantha", "-r", "215", "-o", str(aiff), narration])
    actual = float(
        run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(aiff),
            ]
        ).stdout
    )
    tempo = max(1.0, actual / (seconds - 0.15))
    if tempo > 1.25:
        raise ValueError(f"Shorten narration {index}: {actual:.2f}s > {seconds}s")
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(aiff),
            "-af",
            f"atempo={tempo:.5f},apad",
            "-t",
            str(seconds),
            "-ar",
            "48000",
            "-ac",
            "1",
            str(frames / f"narration-{index}.wav"),
        ]
    )
concat = frames / "audio-concat.txt"
concat.write_text(
    "".join(f"file '{frames/f'narration-{i}.wav'}'\n" for i in range(len(segments)))
)
run(
    [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-c:a",
        "pcm_s16le",
        str(frames / "narration.wav"),
    ]
)
run(
    [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-framerate",
        "2",
        "-i",
        str(frames / "frame-%04d.jpg"),
        "-i",
        str(frames / "narration.wav"),
        "-vf",
        "scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-t",
        str(duration),
        "-movflags",
        "+faststart",
        "evidence/part-4-1-demo.mp4",
    ]
)
run(["ffmpeg", "-v", "error", "-i", "evidence/part-4-1-demo.mp4", "-f", "null", "-"])
info = json.loads(
    run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            "evidence/part-4-1-demo.mp4",
        ]
    ).stdout
)
Path("evidence/video-metadata.json").write_text(json.dumps(info, indent=2) + "\n")
Path("evidence/demo-transcript.md").write_text(
    "# Combined Part 4.1 demonstration/process video\n\n52-second narrated edited capture of the actual **Vue 3 + FastAPI + SQLite** application. Browser captures are sampled at two per second and encoded at 24 fps. No source values, chart content, counters, or statuses are fabricated. Pauses between scenes are removed, so UTC time may jump. Narration is synthesized using macOS Samantha, not the student's voice. The 16–24 second scene identifies a verification/design decision; the report and curated log explain the revised approach and relevant generated code.\n\n"
    + "\n\n".join(
        f"**{sum(s[0] for s in segments[:i]):02d}–{sum(s[0] for s in segments[:i+1]):02d}s.** {text}"
        for i, (_, text) in enumerate(segments)
    )
    + "\n"
)
print(
    json.dumps(
        {
            "seconds": info["format"]["duration"],
            "bytes": info["format"]["size"],
            "requiredStack": "Vue/FastAPI/SQLite",
            "decodePassed": True,
        }
    )
)
