import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import tempfile
import wave
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 8
INPUT_DEVICE = 4   # NanoMic: USB Audio

def save_wav(path, audio):
    audio_int16 = (audio.flatten() * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

def main():
    print("[INFO] Using input device 4: NanoMic USB Audio")
    print("[INFO] Loading Whisper model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")

    print(f"[INFO] Recording for {RECORD_SECONDS} seconds...")
    print("[INFO] Wait about 1 second, then speak clearly.")

    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        device=INPUT_DEVICE
    )
    sd.wait()

    peak = float(np.max(np.abs(audio)))
    mean = float(np.mean(np.abs(audio)))
    print(f"[DEBUG] Peak level: {peak:.6f}")
    print(f"[DEBUG] Mean level: {mean:.6f}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temp_path = tmp.name

    try:
        save_wav(temp_path, audio)
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