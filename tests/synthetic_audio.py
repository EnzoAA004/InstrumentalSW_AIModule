from __future__ import annotations

import io
import math
import random
import struct
import wave


def synthetic_saxophone_phrase_wav() -> bytes:
    sample_rate = 16_000
    notes = (
        (440.0, 0.00, 0.45),
        (493.88, 0.60, 1.05),
        (523.25, 1.20, 1.65),
        (440.0, 1.80, 2.35),
    )
    duration_seconds = 2.55
    frame_count = int(sample_rate * duration_seconds)
    noise = random.Random(20260927)
    frames = bytearray()
    for index in range(frame_count):
        time_seconds = index / sample_rate
        sample = 0.0
        for frequency, onset, offset in notes:
            if not onset <= time_seconds < offset:
                continue
            note_time = time_seconds - onset
            attack = min(1.0, note_time / 0.035)
            release = min(1.0, (offset - time_seconds) / 0.055)
            envelope = attack * release
            vibrato = 1.0 + 0.0045 * math.sin(2.0 * math.pi * 5.4 * note_time)
            phase = 2.0 * math.pi * frequency * vibrato * note_time
            reed = (
                0.58 * math.sin(phase)
                + 0.25 * math.sin(2.0 * phase + 0.15)
                + 0.12 * math.sin(3.0 * phase + 0.35)
                + 0.05 * math.sin(4.0 * phase + 0.5)
            )
            breath = 0.015 * (noise.random() * 2.0 - 1.0)
            sample += envelope * (reed + breath)
        integer = max(-32768, min(32767, round(sample * 23000)))
        frames.extend(struct.pack("<h", integer))

    destination = io.BytesIO()
    with wave.open(destination, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return destination.getvalue()
