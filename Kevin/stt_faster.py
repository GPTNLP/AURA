import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from pynput import keyboard
import tempfile
import wave
from datetime import datetime
import os
import re

BAD_WORDS = ["badword1", "badword2", "fuck", "shit", "bitch"]

def censor_text(text):
    def repl(m):
        return "█" * len(m.group(0))
    pattern = r"(?i)\b(" + "|".join(map(re.escape, BAD_WORDS)) + r")\b"
    return re.sub(pattern, repl, text)

def contains_bad_language(text):
    pattern = r"(?i)\b(" + "|".join(map(re.escape, BAD_WORDS)) + r")\b"
    return re.search(pattern, text) is not None


class SpeechToText:
    def __init__(self, model_size="small", sample_rate=16000):
        """
        Initialize faster-whisper STT
        """
        print(f"Loading faster-whisper model '{model_size}'... This may take a moment.")
        # ✅ optimized for Intel Mac CPU (quantized int8)
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("✅ Model loaded successfully!")

        self.fs = sample_rate
        self.is_recording = False
        self.recording = None
        self.stream = None

    def start_recording(self):
        if self.is_recording:
            print("⚠️ Already recording...")
            return
        print("\n🎤 Recording started... (Press SPACE again to stop)")
        self.is_recording = True
        self.recording = []
        self.stream = sd.InputStream(samplerate=self.fs, channels=1, dtype="float32",
                                     callback=self._callback)
        self.stream.start()

    def _callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.recording.append(indata.copy())

    def stop_recording(self):
        if not self.is_recording:
            print("⚠️ Not currently recording...")
            return None

        print("⏹️ Recording stopped. Processing...")
        self.is_recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.recording:
            print("⚠️ No audio captured.")
            return None

        audio = np.concatenate(self.recording, axis=0)

        # Save to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            temp_filename = tmp_file.name
        with wave.open(temp_filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.fs)
            wf.writeframes((audio * 32767).astype(np.int16).tobytes())

        # --- Transcribe + Translate ---
        print("🔄 Transcribing (and translating) with faster-whisper...")
        segments, info = self.model.transcribe(temp_filename, task="translate", language=None)

        text = " ".join([seg.text for seg in segments]).strip()
        detected_lang = info.language or "unknown"

        os.unlink(temp_filename)

        print(f"🌐 Detected language: {detected_lang.upper()}")
        print(f"📝 Translated → English: {text}")

        return text


def main():
    print("=" * 60)
    print("🤖 SPEECH TO TEXT + AUTO-TRANSLATION (faster-whisper)")
    print("=" * 60)
    print("\nInstructions:")
    print("  • Press SPACE to start/stop recording")
    print("  • Press ESC to exit the program\n")

    model_size = input("Choose model size (tiny, base, small, medium, large) [default=small]: ").strip() or "small"
    stt = SpeechToText(model_size=model_size)

    print("\n✅ System ready! Press SPACE to start recording...\n")
    print("-" * 60)

    def on_press(key):
        nonlocal stt
        try:
            if key == keyboard.Key.space:
                if not stt.is_recording:
                    stt.start_recording()
                else:
                    text = stt.stop_recording()
                    if text:
                        censored_text = censor_text(text)
                        bad = contains_bad_language(text)

                        print("\n" + "=" * 60)
                        print("📝 FINAL OUTPUT (in English):")
                        print(f"   '{censored_text}'")
                        print("=" * 60)

                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_path = os.path.expanduser("~/Desktop/capstone/transcriptions.log")
                        os.makedirs(os.path.dirname(log_path), exist_ok=True)
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"[{timestamp}] {censored_text}\n")

                        if bad:
                            print("⚠️ Inappropriate language detected. Skipping processing.")
                            print("\n✅ Ready for next recording (SPACE to start)...")
                            return

                        print("\n✅ Ready for next recording (SPACE to start)...")

            elif key == keyboard.Key.esc:
                print("\n👋 Exiting program...")
                return False
        except AttributeError:
            if key == keyboard.Key.esc:
                print("\n\n👋 Exiting program...")
                return False

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
