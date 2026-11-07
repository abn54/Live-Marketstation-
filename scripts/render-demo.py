"""Assemble an edited 45-second narrated demo from genuine browser captures.

Prerequisites: macOS `say`, ffmpeg, ffprobe, and screenshot frames captured through
supported browser tools in /tmp/marketstation-demo-frames. No market data is drawn
or modified here. Pauses between recording segments are removed.
"""
from pathlib import Path
import json
import shutil
import subprocess

frames = Path('/tmp/marketstation-demo-frames')
staging = frames / 'selected'
staging.mkdir(exist_ok=True)
# Replace the first outage take with the verified final take.
indices = list(range(44)) + list(range(60, 106))
for out_index, source_index in enumerate(indices):
    shutil.copyfile(frames / f'frame-{source_index:04d}.png', staging / f'frame-{out_index:04d}.jpg')
segments = [
    (12, 'This is Marketstation with actual Yahoo Finance data. Quotes stream through the backend WebSocket. One minute candlesticks and their reported volume refresh separately. Source, age, and feed health stay visible.'),
    (5, 'The ledger shows persisted receipt identities, source and receipt times, and revisions.'),
    (5, 'Each observation commits to SQLite before the backend broadcasts it to the chart.'),
    (8, 'Disconnecting the real upstream feed marks both channels unavailable. Collection stops, observation age increases, and stored candles remain available.'),
    (5, 'Reconnecting restores actual Yahoo data without discarding any of the persistent records.'),
    (10, 'Recorded replay reads the SQLite receipt log. Playback and seeking preserve observation order and revisions. The recording is clearly labeled, and live collection continues independently.'),
]
run = lambda args: subprocess.run(args, check=True, capture_output=True)
for index, (duration, narration) in enumerate(segments):
    aiff = frames / f'narration-{index}.aiff'
    run(['say', '-v', 'Samantha', '-r', '215', '-o', str(aiff), narration])
    measured = float(run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(aiff)]).stdout)
    if measured > duration:
        raise RuntimeError(f'Narration segment {index} exceeds its scene ({measured}s > {duration}s)')
    run(['ffmpeg', '-y', '-v', 'error', '-i', str(aiff), '-af', 'apad', '-t', str(duration), '-ar', '48000', '-ac', '1', str(frames / f'narration-{index}.wav')])
concat = frames / 'audio-concat.txt'
concat.write_text(''.join(f"file '{frames / f'narration-{i}.wav'}'\n" for i in range(len(segments))))
run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c:a', 'pcm_s16le', str(frames / 'narration.wav')])
run(['ffmpeg', '-y', '-v', 'error', '-framerate', '2', '-i', str(staging / 'frame-%04d.jpg'), '-i', str(frames / 'narration.wav'), '-vf', 'scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2,setsar=1', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '24', '-c:a', 'aac', '-b:a', '96k', '-t', '45', '-movflags', '+faststart', 'evidence/part-4-1-demo.mp4'])
info = json.loads(run(['ffprobe', '-v', 'quiet', '-show_format', '-show_streams', '-of', 'json', 'evidence/part-4-1-demo.mp4']).stdout)
Path('evidence/video-metadata.json').write_text(json.dumps(info, indent=2) + '\n')
Path('evidence/demo-transcript.md').write_text('# Part 4.1 demo transcript\n\n45-second narrated, edited capture of the real running application. Browser screenshots were captured at two per second and encoded at 24 fps. No prices, charts, counters, or statuses were generated or replaced. Pauses between scenes were removed; the on-screen UTC clock therefore jumps between scenes. Narration uses the macOS Samantha voice.\n\n' + '\n\n'.join(f'**{sum(s[0] for s in segments[:i]):02d}–{sum(s[0] for s in segments[:i+1]):02d}s.** {text}' for i, (_, text) in enumerate(segments)) + '\n')
print(json.dumps({'duration': info['format']['duration'], 'bytes': info['format']['size'], 'frames': len(indices)}))
