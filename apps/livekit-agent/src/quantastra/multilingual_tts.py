"""Multilingual Sarvam TTS wrapper — auto-detects Indian language from text
and routes to the appropriate Sarvam TTS instance for that language."""

from __future__ import annotations

import logging
import unicodedata

log = logging.getLogger(__name__)

_SCRIPT_TO_LANG: dict[str, str] = {
    "DEVANAGARI": "hi-IN",   # Hindi, Marathi
    "BENGALI":    "bn-IN",   # Bengali
    "GUJARATI":   "gu-IN",   # Gujarati
    "TAMIL":      "ta-IN",   # Tamil
    "TELUGU":     "te-IN",   # Telugu
    "KANNADA":    "kn-IN",   # Kannada
    "MALAYALAM":  "ml-IN",   # Malayalam
    "GURMUKHI":   "pa-IN",   # Punjabi
    "ORIYA":      "or-IN",   # Odia
}


def detect_indian_language(text: str) -> str:
    """Detect the dominant Indian language script in text.

    Returns a BCP-47 language code (e.g. ``"hi-IN"``).
    Falls back to ``"en-IN"`` for English-only text.
    """
    script_counts: dict[str, int] = {}
    for char in text:
        if char.isspace() or char.isdigit() or ord(char) < 128:
            continue  # ASCII (English), digits, whitespace — skip
        try:
            script = unicodedata.name(char).split()[0]
        except ValueError:
            continue
        if script in _SCRIPT_TO_LANG:
            script_counts[script] = script_counts.get(script, 0) + 1

    if not script_counts:
        return "en-IN"

    dominant = max(script_counts, key=script_counts.get)
    return _SCRIPT_TO_LANG[dominant]


class MultilingualSarvamTTS:
    """TTS wrapper that auto-detects language per utterance.

    Maintains a cache of ``sarvam.TTS`` instances keyed by language code
    so the correct voice model is used for each Indian language.

    Duck-types the LiveKit ``TTS`` protocol so it can be passed directly
    to ``AgentSession`` or ``Agent.__init__``.
    """

    def __init__(
        self,
        model: str = "bulbul:v3",
        speaker: str = "shubh",
        pace: float = 1.0,
        temperature: float = 0.6,
        **kwargs,
    ):
        self._model = model
        self._speaker = speaker
        self._pace = pace
        self._temperature = temperature
        self._extra_kwargs = kwargs
        self._cache: dict[str, object] = {}
        # Eager default TTS — needed before first synthesize() because LiveKit
        # calls .on(), .prewarm() at setup time before any text arrives.
        self._default = self._get_tts("en-IN")

    def _get_tts(self, lang_code: str):
        """Return (or create + cache) a Sarvam TTS for *lang_code*."""
        if lang_code not in self._cache:
            from livekit.plugins import sarvam

            self._cache[lang_code] = sarvam.TTS(
                target_language_code=lang_code,
                model=self._model,
                speaker=self._speaker,
                pace=self._pace,
                temperature=self._temperature,
                **self._extra_kwargs,
            )
            log.info("MultilingualSarvamTTS: created TTS for %s", lang_code)
        return self._cache[lang_code]

    def synthesize(self, text: str):
        """Auto-detect language and delegate to the matching Sarvam TTS."""
        lang = detect_indian_language(text)
        log.debug("TTS language: %s (text len=%d)", lang, len(text))
        tts = self._get_tts(lang)
        return tts.synthesize(text)

    def prewarm(self) -> None:
        """Pre-warm all cached TTS connections."""
        for tts in self._cache.values():
            tts.prewarm()

    def on(self, event: str, handler):
        """Register event handler on all cached TTS instances."""
        for tts in self._cache.values():
            tts.on(event, handler)

    def off(self, event: str, handler):
        """Remove event handler from all cached TTS instances."""
        for tts in self._cache.values():
            tts.off(event, handler)

    async def aclose(self) -> None:
        """Close all cached TTS connections."""
        for tts in self._cache.values():
            await tts.aclose()

    @property
    def label(self) -> str:
        return f"{type(self).__module__}.{type(self).__name__}"

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "sarvam"

    @property
    def capabilities(self):
        from livekit.agents.tts.tts import TTSCapabilities

        return TTSCapabilities(streaming=False)

    @property
    def sample_rate(self) -> int:
        return 22050

    @property
    def num_channels(self) -> int:
        return 1
