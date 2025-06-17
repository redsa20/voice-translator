import os

class Settings:
    WHISPER_MODEL = "large-v3"
    TRANSLATION_MODEL = "gpt-4o"
    SOURCE_LANGUAGE = "en"
    TARGET_LANGUAGE = "he"
    ENABLE_REFINEMENT = True
    VAD_TYPE = "webrtc"  # or "silero"
    VAD_MAX_SILENCE = 2.0
    DEVICE = "cuda" if os.environ.get("USE_CUDA", "1") == "1" else "cpu"
