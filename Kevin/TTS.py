"""
Robot Text-to-Speech (TTS) System
A comprehensive TTS solution with multiple engine options
"""

import os
import time
import queue
import threading
import logging
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass
import json

# TTS Libraries
import pyttsx3
from gtts import gTTS
import pygame
import asyncio
import edge_tts
from pydub import AudioSegment
from pydub.playback import play
import tempfile
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TTSEngine(Enum):
    """Available TTS engines"""
    PYTTSX3 = "pyttsx3"  # Offline
    GTTS = "gtts"        # Online (Google)
    EDGE_TTS = "edge"    # Online (Microsoft)


@dataclass
class TTSConfig:
    """TTS Configuration"""
    engine: TTSEngine = TTSEngine.PYTTSX3
    voice_id: Optional[str] = None
    rate: int = 150  # Words per minute
    volume: float = 1.0  # 0.0 to 1.0
    pitch: int = 50  # 0 to 100
    language: str = "en"
    cache_enabled: bool = True
    cache_dir: str = "./tts_cache"
    output_device: Optional[str] = None


class TTSCache:
    """Cache system for TTS audio files"""
    
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        if enabled:
            os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, config: Dict[str, Any]) -> str:
        """Generate unique cache key"""
        cache_string = f"{text}_{json.dumps(config, sort_keys=True)}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def get_cache_path(self, cache_key: str) -> str:
        """Get cache file path"""
        return os.path.join(self.cache_dir, f"{cache_key}.mp3")
    
    def exists(self, cache_key: str) -> bool:
        """Check if cache exists"""
        if not self.enabled:
            return False
        return os.path.exists(self.get_cache_path(cache_key))
    
    def save(self, cache_key: str, audio_path: str):
        """Save audio to cache"""
        if self.enabled:
            cache_path = self.get_cache_path(cache_key)
            if audio_path != cache_path:
                os.rename(audio_path, cache_path)
            return cache_path
        return audio_path


class RobotTTS:
    """Main TTS System for Robot"""
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize TTS System
        
        Args:
            config: TTS configuration
        """
        self.config = config or TTSConfig()
        self.cache = TTSCache(self.config.cache_dir, self.config.cache_enabled)
        self.is_running = True

        # Offline engine: pyttsx3 (no pygame, no worker thread)
        if self.config.engine == TTSEngine.PYTTSX3:
            self._init_pyttsx3()
            self.tts_queue = None
            self.worker_thread = None
            logger.info("TTS System initialized with pyttsx3 engine")
            return

        # Online engines: use pygame + worker thread
        pygame.mixer.init()
        self._init_engine()  # EDGE_TTS etc.

        # Queue for TTS requests
        self.tts_queue = queue.PriorityQueue()
        
        # Start TTS worker thread
        self.worker_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.worker_thread.start()
        
        logger.info(f"TTS System initialized with {self.config.engine.value} engine")
    
    def _init_engine(self):
        """Initialize the selected TTS engine"""
        if self.config.engine == TTSEngine.PYTTSX3:
            self._init_pyttsx3()
        elif self.config.engine == TTSEngine.EDGE_TTS:
            self._init_edge_tts()
        # GTTS doesn't need initialization
    
    def _init_pyttsx3(self):
        """Initialize pyttsx3 engine"""
        try:
            self.pyttsx3_engine = pyttsx3.init()

            voices = self.pyttsx3_engine.getProperty('voices')

            # If voice_id is provided, try to match by id or name (string)
            if self.config.voice_id:
                for v in voices:
                    # match either full id or the name
                    if v.id == self.config.voice_id or v.name == self.config.voice_id:
                        self.pyttsx3_engine.setProperty('voice', v.id)
                        break

            # Configure properties
            self.pyttsx3_engine.setProperty('rate', self.config.rate)
            self.pyttsx3_engine.setProperty('volume', self.config.volume)

            logger.info("pyttsx3 engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3: {e}")
            raise
    
    def _init_edge_tts(self):
        """Initialize edge-tts settings"""
        # Edge TTS voices
        self.edge_voices = {
            'en-US-male': 'en-US-GuyNeural',
            'en-US-female': 'en-US-JennyNeural',
            'en-GB-male': 'en-GB-RyanNeural',
            'en-GB-female': 'en-GB-SoniaNeural',
        }
        
        # Select voice
        self.edge_voice = self.config.voice_id or 'en-US-JennyNeural'
        if self.edge_voice not in self.edge_voices.values():
            self.edge_voice = self.edge_voices.get(self.config.voice_id, 'en-US-JennyNeural')
    
    def speak(self, text: str, callback: Optional[Callable] = None, priority: int = 5):
        """
        Speak text.
        - For pyttsx3 (offline), speak immediately with a fresh engine each time.
        - For other engines (gTTS, EDGE_TTS), enqueue for background playback.
        """
        if self.config.engine == TTSEngine.PYTTSX3:
            logger.info(f"Speaking immediately (pyttsx3): '{text[:50]}...'")
            try:
                # Create a fresh engine each call to avoid state issues
                engine = pyttsx3.init()

                # Apply config
                voices = engine.getProperty('voices')
                if self.config.voice_id:
                    for v in voices:
                        if v.id == self.config.voice_id or v.name == self.config.voice_id:
                            engine.setProperty('voice', v.id)
                            break

                engine.setProperty('rate', self.config.rate)
                engine.setProperty('volume', self.config.volume)

                # Speak
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                logger.error(f"pyttsx3 direct speak failed: {e}")
            if callback:
                callback()
        else:
            # Online engines still use the queue + worker
            self.tts_queue.put((priority, time.time(), text, callback))
            logger.info(f"Added to TTS queue: '{text[:50]}...'")


    def speak_now(self, text: str):
        """
        Speak text immediately (blocking)
        
        Args:
            text: Text to speak
        """
        try:
            audio_file = self._generate_audio(text)
            if audio_file:
                self._play_audio(audio_file)
                # Clean up temp file if not cached
                if not self.config.cache_enabled and os.path.exists(audio_file):
                    os.remove(audio_file)
        except Exception as e:
            logger.error(f"Error in speak_now: {e}")
    
    def _tts_worker(self):
        """Worker thread for processing TTS queue"""
        while self.is_running:
            try:
                # Get item from queue (wait up to 1 second)
                priority, timestamp, text, callback = self.tts_queue.get(timeout=1)
                
                logger.info(f"Processing TTS: '{text[:50]}...'")
                
                # Generate and play audio
                audio_file = self._generate_audio(text)
                if audio_file:
                    self._play_audio(audio_file)
                    
                    # Clean up temp file if not cached
                    if not self.config.cache_enabled and os.path.exists(audio_file):
                        os.remove(audio_file)
                
                # Execute callback if provided
                if callback:
                    callback()
                
                self.tts_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in TTS worker: {e}")
    
    def _generate_audio(self, text: str) -> Optional[str]:
        # 1) Offline engine: pyttsx3 → speak directly, no file
        if self.config.engine == TTSEngine.PYTTSX3:
            try:
                self.pyttsx3_engine.say(text)
                self.pyttsx3_engine.runAndWait()
            except Exception as e:
                logger.error(f"pyttsx3 direct speak failed: {e}")
            # Nothing for pygame to play
            return None

        # 2) Engines that use files (gTTS, EDGE_TTS) → use cache
        cache_config = {
            'engine': self.config.engine.value,
            'voice': self.config.voice_id,
            'rate': self.config.rate,
            'language': self.config.language
        }
        cache_key = self.cache.get_cache_key(text, cache_config)

        if self.cache.exists(cache_key):
            logger.info("Using cached audio")
            return self.cache.get_cache_path(cache_key)

        # Generate new audio
        try:
            if self.config.engine == TTSEngine.GTTS:
                return self._generate_gtts(text, cache_key)
            elif self.config.engine == TTSEngine.EDGE_TTS:
                return self._generate_edge_tts(text, cache_key)
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}")
            return None

    
    def _generate_gtts(self, text: str, cache_key: str) -> str:
        """Generate audio using gTTS"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        tts = gTTS(text=text, lang=self.config.language, slow=False)
        tts.save(temp_path)
        
        return self.cache.save(cache_key, temp_path)
    
    def _generate_edge_tts(self, text: str, cache_key: str) -> str:
        """Generate audio using edge-tts"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Run async edge-tts in sync context
        asyncio.run(self._edge_tts_async(text, temp_path))
        
        return self.cache.save(cache_key, temp_path)
    
    async def _edge_tts_async(self, text: str, output_path: str):
        """Async helper for edge-tts"""
        communicate = edge_tts.Communicate(text, self.edge_voice)
        await communicate.save(output_path)
    
    def _play_audio(self, audio_path: str):
        """
        Play audio file
        
        Args:
            audio_path: Path to audio file
        """
        try:
            # Using pygame for playback
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            logger.info("Audio playback completed")
            
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    def set_voice(self, voice_id: str):
        """Change TTS voice"""
        self.config.voice_id = voice_id
        if self.config.engine == TTSEngine.PYTTSX3:
            self._init_pyttsx3()
        elif self.config.engine == TTSEngine.EDGE_TTS:
            self.edge_voice = voice_id
    
    def set_rate(self, rate: int):
        """Change speech rate"""
        self.config.rate = rate
        if self.config.engine == TTSEngine.PYTTSX3:
            self.pyttsx3_engine.setProperty('rate', rate)
    
    def set_volume(self, volume: float):
        """Change volume (0.0 to 1.0)"""
        self.config.volume = max(0.0, min(1.0, volume))
        if self.config.engine == TTSEngine.PYTTSX3:
            self.pyttsx3_engine.setProperty('volume', self.config.volume)
        pygame.mixer.music.set_volume(self.config.volume)
    
    def list_voices(self) -> list:
        """Get available voices for current engine"""
        if self.config.engine == TTSEngine.PYTTSX3:
            return [voice.id for voice in self.pyttsx3_engine.getProperty('voices')]
        elif self.config.engine == TTSEngine.EDGE_TTS:
            return list(self.edge_voices.values())
        else:
            return []
    
    def pause(self):
        """Pause current speech"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
    
    def resume(self):
        """Resume paused speech"""
        pygame.mixer.music.unpause()
    
    def stop(self):
        """Stop current speech and clear queue"""
        # For pyttsx3 we don't use pygame or a queue, so nothing to stop
        if self.config.engine == TTSEngine.PYTTSX3 or self.tts_queue is None:
            return

        # For online engines that use pygame + queue
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

        # Clear the queue
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break
    
    def shutdown(self):
        """Shutdown TTS system"""
        self.is_running = False
        self.stop()

        # Join worker thread if it exists (online engines)
        if hasattr(self, 'worker_thread') and self.worker_thread is not None:
            self.worker_thread.join(timeout=2)

        # Only quit pygame if we actually used it
        if self.config.engine != TTSEngine.PYTTSX3 and pygame.mixer.get_init():
            pygame.mixer.quit()

        logger.info("TTS System shut down")


class RobotAssistant:
    
    def __init__(self, tts_config: Optional[TTSConfig] = None):
        """Initialize Robot Assistant"""
        self.tts = RobotTTS(tts_config)
        logger.info("Robot Assistant initialized")
    
    def process_query(self, text_input: str) -> str:
        text = text_input.lower()

        # Example EE knowledge
        if "power" in text and ("voltage" in text or "current" in text):
            # very simple parser
            import re
            v = re.findall(r"(\d*\.?\d+)\s*(mv|v)", text)
            i = re.findall(r"(\d*\.?\d+)\s*(ma|a)", text)

            if v and i:
                v_val, v_unit = v[0]
                i_val, i_unit = i[0]

                v_val = float(v_val) * (0.001 if v_unit == "mv" else 1)
                i_val = float(i_val) * (0.001 if i_unit == "ma" else 1)

                p = v_val * i_val
                return f"The power is {p:.6f} watts, calculated as voltage times current."

        # Default fallback
        return text_input
    
    def respond(self, user_input: str):
        """
        Complete response cycle
        
        Args:
            user_input: Text from STT
        """
        logger.info(f"Received input: {user_input}")
        
        # Process with AI
        response = self.process_query(user_input)
        logger.info(f"AI Response: {response}")
        
        # Speak the response
        self.tts.speak(response, callback=lambda: logger.info("Response delivered"))
        
        return response


if __name__ == "__main__":
    """
    Interactive Text-to-Speech demo.
    - You type text in the terminal.
    - The TTS system speaks exactly what you typed.
    - No AI processing here.
    """

    print("=" * 60)
    print(" Robot TTS Interactive Demo (No AI)")
    print(" Type your message and press Enter.")
    print(" Type 'quit' or 'exit' to stop.")
    print("=" * 60)

    # Choose TTS engine
    # Offline: macOS voice via pyttsx3
    tts_config = TTSConfig(
        engine=TTSEngine.PYTTSX3,
        rate=150,
        volume=0.9,
        # Optional: use a specific macOS voice, e.g., Samantha:
        voice_id="com.apple.voice.compact.en-US.Samantha",
        cache_enabled=False,  # no cache needed for pyttsx3 direct speak
    )

    # If you want to demo Google TTS instead, comment the block above and use:
    # tts_config = TTSConfig(
    #     engine=TTSEngine.GTTS,
    #     language="en",
    #     cache_enabled=True,
    # )

    tts = RobotTTS(tts_config)

    try:
        while True:
            user_text = input("\nYou (type 'quit' to exit): ").strip()
            if user_text.lower() in ("quit", "exit"):
                break
            if not user_text:
                continue

            # Speak exactly what the user typed
            tts.speak(user_text)

    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]")

    finally:
        tts.shutdown()
        print("\nShutting down TTS. Goodbye!")
