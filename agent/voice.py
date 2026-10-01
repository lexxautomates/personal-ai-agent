"""Free, self-hosted voice stack for Jarvis.

- STT: faster-whisper (base.en, CPU, int8) wrapped on the livekit STT interface.
- TTS: Piper (en_US-lessac-medium, downloaded on first run) on the livekit TTS interface.
- VAD: livekit-plugins-silero.
- LLM: livekit-plugins-openai with_ollama (qwen2.5:7b-instruct, OLLAMA_URL).

No paid APIs, no signup-required services.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path

import numpy as np

from livekit.agents import stt, tts
from livekit.agents.stt import (
    SpeechData,
    SpeechEvent,
    SpeechEventType,
    STTCapabilities,
)
from livekit.agents.types import (
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
)
from livekit.agents.tts import AudioEmitter, ChunkedStream, TTSCapabilities
from livekit.agents.utils import AudioBuffer

logger = logging.getLogger("jarvis.voice")

_WHISPER_SR = 16000


def _to_16k_mono_float32(buffer: AudioBuffer) -> np.ndarray:
    """Convert a LiveKit AudioBuffer to 16kHz mono float32 for whisper."""
    data = np.asarray(buffer.data, dtype=np.float32) / 32768.0
    sr = buffer.sample_rate
    if buffer.num_channels > 1:
        data = data.reshape(-1, buffer.num_channels).mean(axis=1)
    if sr != _WHISPER_SR and data.size:
        # Lightweight linear resample (no scipy dependency).
        src_t = np.linspace(0, 1, num=data.size, endpoint=False)
        dst_n = int(data.size * _WHISPER_SR / sr)
        dst_t = np.linspace(0, 1, num=dst_n, endpoint=False)
        data = np.interp(dst_t, src_t, data).astype(np.float32)
    return data


class WhisperSTT(stt.STT):
    """faster-whisper on the livekit STT interface. Non-streaming: the voice
    pipeline calls recognize() once per VAD-delimited utterance."""

    def __init__(self, model: str = "base.en") -> None:
        super().__init__(
            capabilities=STTCapabilities(streaming=False, interim_results=False)
        )
        self._model_name = model
        self._model = None

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "faster-whisper"

    def _load(self) -> None:
        from faster_whisper import WhisperModel

        logger.info("loading faster-whisper %s (cpu/int8)", self._model_name)
        self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> SpeechEvent:
        if self._model is None:
            await asyncio.to_thread(self._load)
        audio = _to_16k_mono_float32(buffer)
        segments, _info = await asyncio.to_thread(
            self._model.transcribe, audio, language="en"
        )
        text = " ".join(s.text for s in segments).strip()
        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(language="en", text=text)],
        )


# ---------------------------------------------------------------------------
# Piper TTS
# ---------------------------------------------------------------------------

_VOICE = "en_US-lessac-medium"
_VOICE_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    f"/en/en_US/lessac/medium/{_VOICE}"
)


def _ensure_voice(voice: str = _VOICE) -> str:
    """Download the Piper voice on first run. Returns the .onnx path."""
    d = Path.home() / ".jarvis" / "voices" / voice
    d.mkdir(parents=True, exist_ok=True)
    onnx = d / f"{voice}.onnx"
    cfg = d / f"{voice}.onnx.json"
    if not onnx.exists() or not cfg.exists():
        import urllib.request

        logger.info("downloading piper voice %s (first run)", voice)
        for url, dest in ((_VOICE_BASE + ".onnx", onnx),
                          (_VOICE_BASE + ".onnx.json", cfg)):
            req = urllib.request.Request(url, headers={"User-Agent": "jarvis/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                f.write(r.read())
    return str(onnx)


def _chunk_audio_bytes(chunk) -> bytes:
    raw = getattr(chunk, "audio_int16_bytes", None)
    if raw:
        return bytes(raw)
    arr = np.asarray(getattr(chunk, "audio_int16_array"), dtype=np.int16)
    return arr.tobytes()


class _PiperChunkedStream(ChunkedStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        voice = await asyncio.to_thread(self._tts._load_voice)
        request_id = f"piper-{uuid.uuid4().hex[:12]}"
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
        )
        buf = bytearray()
        frame_bytes = self._tts.sample_rate * 2 * self._tts.num_channels  # ~1s
        for chunk in await asyncio.to_thread(
            lambda: list(voice.synthesize(self._input_text))
        ):
            buf += _chunk_audio_bytes(chunk)
            while len(buf) >= frame_bytes:
                output_emitter.push(bytes(buf[:frame_bytes]))
                del buf[:frame_bytes]
        if buf:
            output_emitter.push(bytes(buf))


class PiperTTS(tts.TTS):
    """Piper neural TTS on the livekit TTS interface."""

    def __init__(self, voice: str = _VOICE) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=22050,
            num_channels=1,
        )
        self._voice_name = voice
        self._voice = None

    @property
    def model(self) -> str:
        return f"piper/{self._voice_name}"

    @property
    def provider(self) -> str:
        return "piper"

    def _load_voice(self):
        if self._voice is None:
            from piper import PiperVoice

            onnx = _ensure_voice(self._voice_name)
            logger.info("loading piper voice %s", self._voice_name)
            self._voice = PiperVoice.load(onnx)
        return self._voice

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> ChunkedStream:
        return _PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)


# ---------------------------------------------------------------------------
# Stack factory
# ---------------------------------------------------------------------------

def create_voice_stack():
    """Build (vad, stt, llm, tts). VAD/LLM come from livekit plugins;
    STT/TTS are the free self-hosted adapters above."""
    from livekit.plugins import openai as openai_plugin
    from livekit.plugins import silero
    from livekit.agents.types import APIConnectOptions

    class OllamaLLM(openai_plugin.LLM):
        """Ollama-backed LLM with a generous per-request timeout.

        The agents inference layer applies conn_options.timeout per request
        (default 10s). A cold Ollama model load takes ~30s on this box, so
        every chat() call gets a two-minute budget. Pinned to
        livekit-agents==1.8.3 / livekit-plugins-openai==1.8.3.
        """

        _OLLAMA_CONN_OPTIONS = APIConnectOptions(timeout=120.0)

        def chat(self, *, chat_ctx, tools=None, **kwargs):  # noqa: ANN001, ANN003, ANN202
            kwargs["conn_options"] = self._OLLAMA_CONN_OPTIONS
            return super().chat(chat_ctx=chat_ctx, tools=tools, **kwargs)

    vad = silero.VAD.load()
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    if not ollama_url.endswith("/v1"):
        ollama_url += "/v1"
    llm = OllamaLLM(
        model="qwen2.5:7b-instruct",
        api_key="ollama",
        base_url=ollama_url,
    )
    return vad, WhisperSTT(), llm, PiperTTS()
