import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)

GEMINI_KEY = (os.environ.get('GEMINI_API_KEY') or os.environ.get('SMART_SCAN_KEY') or '').strip()
GEMINI_MODEL = (os.environ.get('GEMINI_MODEL') or 'gemini-3.8-flash').strip()
# Auto-migrate the model value used by earlier project packages.
if GEMINI_MODEL in {'gemini-2.5-flash', 'gemini-2.5-flash-lite'}:
    GEMINI_MODEL = 'gemini-3.8-flash'
GEMINI_FALLBACK_MODEL = (os.environ.get('GEMINI_FALLBACK_MODEL') or 'gemini-3.5-flash-lite').strip()
if GEMINI_FALLBACK_MODEL in {'gemini-2.5-flash', 'gemini-2.5-flash-lite'}:
    GEMINI_FALLBACK_MODEL = 'gemini-3.5-flash-lite'
GEMINI_TTS_MODEL = (os.environ.get('GEMINI_TTS_MODEL') or 'gemini-3.8-flash-tts').strip()
GEMINI_TTS_FALLBACK_MODEL = (os.environ.get('GEMINI_TTS_FALLBACK_MODEL') or 'gemini-3.8-flash-lite-tts').strip()
GEMINI_TRANSCRIBE_MODEL = (os.environ.get('GEMINI_TRANSCRIBE_MODEL') or 'gemini-3.5-transcribe').strip()


def _endpoint(model):
    return f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'

GEMINI_ENDPOINT = _endpoint(GEMINI_MODEL)
GEMINI_FALLBACK_ENDPOINT = _endpoint(GEMINI_FALLBACK_MODEL)
GEMINI_TTS_ENDPOINT = _endpoint(GEMINI_TTS_MODEL)
GEMINI_TTS_FALLBACK_ENDPOINT = _endpoint(GEMINI_TTS_FALLBACK_MODEL)
GEMINI_TRANSCRIBE_ENDPOINT = _endpoint(GEMINI_TRANSCRIBE_MODEL)


def is_smart_scan_configured():
    return bool(GEMINI_KEY)
