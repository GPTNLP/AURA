import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import time
import wave
import tempfile
from datetime import datetime

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


BAD_WORD_PATTERNS = [
    r"fuck\w*",
    r"shit\w*",
    r"bitch\w*",
    r"ass",
    r"asshole\w*",
]

WAKE_PHRASES = [
    "hey aura",
    "hi aura",
    "okay aura",
    "ok aura",
    "yo aura",
]

COMMAND_MAP = {
    "forward": ["forward", "go forward", "move forward"],
    "backward": ["backward", "go backward", "move backward", "go back", "move back"],
    "left": ["left", "turn left", "go left", "move left"],
    "right": ["right", "turn right", "go right", "move right"],
    "stop": ["stop", "halt", "pause"],
}


def censor_text(text: str) -> str:
    for pattern in BAD_WORD_PATTERNS:
        text = re.sub(
            rf"(?i)\b({pattern})\b",
            lambda m: "█" * len(m.group(0)),
            text
        )
    return text


def contains_bad_language(text: str) -> bool:
    for pattern in BAD_WORD_PATTERNS:
        if re.search(rf"(?i)\b({pattern})\b", text):
            return True
    return False


def detect_command(text: str):
    text = text.lower()
    for command, phrases in COMMAND_MAP.items():
        for phrase in phrases:
            if phrase in text:
                return command
    return None


def contains_wake_phrase(text: str) -> bool:
    text = text.lower()
    for phrase in WAKE_PHRASES:
        if phrase in text:
            return True
    return False


class SpeechToText:
    def __init__(
        self,
        model_size: str = "base",
        input_device: int = 4,
        device_sample_rate: int = 48000,
        target_sample_rate: int = 16000,
        channels: int = 1,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        task: str = "transcribe",
        log_path: str = "~/SDP/AURA/JetsonLocal/storage/transcriptions.log",
        silence_threshold: float = 0.015,
    ):
        print(f"[STT] Loading faster-whisper model '{model_size}'...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("[STT] Model loaded successfully!")

        self.input_device = input_device
        self.device_sample_rate = device_sample_rate
        self.target_sample_rate = target_sample_rate
        self.channels = channels
        self.language = language
        self.task = task
        self.log_path = os.path.expanduser(log_path)
        self.silence_threshold = silence_threshold

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        if orig_sr == target_sr:
            return audio

        audio = audio.flatten()
        duration = len(audio) / orig_sr

        old_times = np.linspace(0, duration, num=len(audio), endpoint=False)
        new_length = int(duration * target_sr)
        new_times = np.linspace(0, duration, num=new_length, endpoint=False)

        resampled = np.interp(new_times, old_times, audio).astype(np.float32)
        return resampled.reshape(-1, 1)

    def _save_wav(self, path: str, audio: np.ndarray, sample_rate: int) -> None:
        audio = np.clip(audio.flatten(), -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())

    def _transcribe_audio_array(self, audio: np.ndarray) -> str:
        if audio is None or len(audio) == 0:
            return ""

        audio_16k = self._resample_audio(audio, self.device_sample_rate, self.target_sample_rate)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            temp_filename = tmp_file.name

        try:
            self._save_wav(temp_filename, audio_16k, self.target_sample_rate)

            segments, info = self.model.transcribe(
                temp_filename,
                task=self.task,
                language=self.language,
                vad_filter=True,
                beam_size=5,
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text

        finally:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def record_fixed(self, seconds: float) -> np.ndarray:
        audio = sd.rec(
            int(seconds * self.device_sample_rate),
            samplerate=self.device_sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.input_device,
        )
        sd.wait()
        return audio

    def listen_for_wake_word(self, chunk_seconds: float = 2.0) -> bool:
        audio = self.record_fixed(chunk_seconds)

        peak = float(np.max(np.abs(audio)))
        mean = float(np.mean(np.abs(audio)))

        if peak < self.silence_threshold:
            return False

        text = self._transcribe_audio_array(audio)
        if not text:
            return False

        print(f"[WAKE CHECK] {text}")

        if contains_wake_phrase(text):
            print("[WAKE] Wake phrase detected.")
            return True

        return False

    def listen_for_command(self, timeout_seconds: float = 10.0, min_speech_seconds: float = 0.8):
        print("[COMMAND] Listening for command...")

        start_time = time.time()
        collected = []
        speech_started = False
        silence_after_speech = 0.0
        chunk_seconds = 0.5

        while time.time() - start_time < timeout_seconds:
            audio = self.record_fixed(chunk_seconds)
            collected.append(audio)

            level = float(np.mean(np.abs(audio)))

            if level > self.silence_threshold:
                speech_started = True
                silence_after_speech = 0.0
            else:
                if speech_started:
                    silence_after_speech += chunk_seconds

            elapsed = time.time() - start_time

            if speech_started and elapsed >= min_speech_seconds and silence_after_speech >= 1.2:
                break

        full_audio = np.concatenate(collected, axis=0) if collected else np.array([], dtype=np.float32)
        peak = float(np.max(np.abs(full_audio))) if len(full_audio) else 0.0
        mean = float(np.mean(np.abs(full_audio))) if len(full_audio) else 0.0

        print(f"[COMMAND] Peak level: {peak:.6f}")
        print(f"[COMMAND] Mean level: {mean:.6f}")

        if not speech_started:
            print("[COMMAND] No speech detected before timeout.")
            return ""

        text = self._transcribe_audio_array(full_audio)
        return text

    def log_transcript(self, text: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")


def main():
    stt = SpeechToText(
        model_size="base",
        input_device=4,
        device_sample_rate=48000,
        target_sample_rate=16000,
        channels=1,
        device="cpu",
        compute_type="int8",
        language="en",
        task="transcribe",
        silence_threshold=0.015,
    )

    print("[STT] Device info:")
    print(sd.query_devices(stt.input_device))
    print()
    print("=" * 60)
    print(" AURA WAKE WORD MODE")
    print("=" * 60)
    print("Say 'Hey AURA' to wake it up.")
    print("After that, it will listen for a command.")
    print("If nothing is heard for 10 seconds, it goes back to wake mode.")
    print("Press Ctrl+C to exit.")
    print("-" * 60)

    try:
        while True:
            woke = stt.listen_for_wake_word(chunk_seconds=2.0)
            if not woke:
                continue

            print("[AURA] Yes? Listening...")
            command_text = stt.listen_for_command(timeout_seconds=10.0)

            if not command_text:
                print("[AURA] No command heard. Returning to wake mode.")
                print("-" * 60)
                continue

            censored_text = censor_text(command_text)
            bad = contains_bad_language(command_text)
            detected_command = detect_command(command_text)

            print("\n" + "=" * 60)
            print(" COMMAND TRANSCRIPT:")
            print(f" '{censored_text}'")
            print(f" COMMAND DETECTED: {detected_command if detected_command else 'None'}")
            print("=" * 60)

            stt.log_transcript(censored_text)

            if bad:
                print("[STT] Inappropriate language detected.")

            print("[AURA] Returning to wake mode.")
            print("-" * 60)

    except KeyboardInterrupt:
        print("\n[STT] Exiting cleanly.")


if __name__ == "__main__":
    main()