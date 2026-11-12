"""Synthesised sound effects - no audio files needed.

Everything is generated at start-up from sine waves. If the audio device is
missing or fails to initialise the game simply runs silently.
"""
import array
import math

import pygame


class Sound:
    def __init__(self):
        self.enabled = True
        self.ok = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            rate, fmt, channels = pygame.mixer.get_init()
            if fmt != -16:
                return                       # only signed 16-bit output is supported here
            self.rate, self.channels = rate, channels
            self._build()
            self.ok = True
        except Exception:                    # no audio device, etc.
            self.ok = False

    # ------------------------------------------------------------ synth
    def _wave(self, notes, vol=0.30):
        """notes: list of (frequency_hz, seconds); frequency 0 = silence."""
        buf = array.array("h")
        for freq, dur in notes:
            n = max(1, int(self.rate * dur))
            for i in range(n):
                t = i / self.rate
                env = min(1.0, i / (0.004 * self.rate + 1)) * math.exp(-3.5 * i / n)
                v = math.sin(2 * math.pi * freq * t) if freq else 0.0
                v += 0.35 * math.sin(4 * math.pi * freq * t) if freq else 0.0
                sample = int(max(-1.0, min(1.0, v * env * vol)) * 32767)
                for _ in range(self.channels):
                    buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        self.sounds = {
            "tick": self._wave([(740, 0.04)], 0.16),
            "blip": self._wave([(520, 0.025)], 0.08),
            "click": self._wave([(420, 0.04)], 0.18),
            "bump": self._wave([(110, 0.09)], 0.35),
            "key": self._wave([(523, 0.08), (659, 0.08), (784, 0.08), (1047, 0.22)], 0.28),
            "win": self._wave([(523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.12),
                               (784, 0.08), (1047, 0.40)], 0.30),
            "fail": self._wave([(392, 0.16), (330, 0.16), (262, 0.34)], 0.30),
        }

    # -------------------------------------------------------------- API
    def play(self, name):
        if self.ok and self.enabled and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled
