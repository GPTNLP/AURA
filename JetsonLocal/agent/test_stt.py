import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import tempfile
import wave
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

INPUT_DEVICE = 4
DEVICE_SAMPLE_RATE = 48000   # most likely what the NanoMic wants
TARGET_SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 8

def save_wav(path, audio, sample_rate):
    audio_int16 = np.clip(audio.flatten(), -1.0, 1.0)
    audio_int16 = (audio_int16 * 32767).astype(np.int16)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

def resample_audio(audio, orig_sr, target_sr):
    if orig_sr == target_sr:
        return audio

    audio = audio.flatten()
    duration = len(audio) / orig_sr

    old_times = np.linspace(0, duration, num=len(audio), endpoint=False)
    new_length = int(duration * target_sr)
    new_times = np.linspace(0, duration, num=new_length, endpoint=False)

    resampled = np.interp(new_times, old_times, audio).astype(np.float32)
    return resampled.reshape(-1, 1)

def main():
    print(f"[INFO] Using input device {INPUT_DEVICE}")
    print("[INFO] Device info:")
    print(sd.query_devices(INPUT_DEVICE))
    print()

    print("[INFO] Loading Whisper model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")

    print(f"[INFO] Recording for {RECORD_SECONDS} seconds at {DEVICE_SAMPLE_RATE} Hz...")
    print("[INFO] Wait 1 second, then speak clearly.")

    audio = sd.rec(
        int(RECORD_SECONDS * DEVICE_SAMPLE_RATE),
        samplerate=DEVICE_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        device=INPUT_DEVICE
    )
    sd.wait()

    peak = float(np.max(np.abs(audio)))
    mean = float(np.mean(np.abs(audio)))
    print(f"[DEBUG] Peak level: {peak:.6f}")
    print(f"[DEBUG] Mean level: {mean:.6f}")

    audio_16k = resample_audio(audio, DEVICE_SAMPLE_RATE, TARGET_SAMPLE_RATE)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temp_path = tmp.name

    try:
        save_wav(temp_path, audio_16k, TARGET_SAMPLE_RATE)
        print(f"[INFO] Saved temp wav: {temp_path}")
        print("[INFO] Transcribing...\n")

        segments, info = model.transcribe(
            temp_path,
            language="en",
            task="transcribe",
            vad_filter=True,
            beam_size=5
        )

        final_text = []
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            final_text.append(segment.text)

        print("\n[FINAL RESULT]")
        result = " ".join(final_text).strip()
        print(result if result else "(no speech detected)")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    main()