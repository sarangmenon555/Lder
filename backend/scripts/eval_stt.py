import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import stt

AUDIO_DIR = ROOT / "eval" / "audio"
MANIFEST = AUDIO_DIR / "manifest.jsonl"
RESULTS = ROOT / "eval" / "stt_results.json"

MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".webm": "audio/webm", ".m4a": "audio/mp4", ".flac": "audio/flac"}


def main() -> None:
    try:
        import jiwer
    except ImportError:
        print("Install jiwer first: pip install jiwer")
        sys.exit(1)
    if not MANIFEST.exists():
        print(f"Create {MANIFEST} with one JSON object per line: {{\"file\": \"a.wav\", \"text\": \"reference transcript\"}}")
        sys.exit(1)
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    references, hypotheses, details = [], [], []
    for row in rows:
        path = AUDIO_DIR / row["file"]
        mime = MIME.get(path.suffix.lower(), "audio/wav")
        hypothesis = stt.transcribe(path.read_bytes(), mime)
        references.append(row["text"])
        hypotheses.append(hypothesis)
        details.append({"file": row["file"], "reference": row["text"], "hypothesis": hypothesis})
        time.sleep(2)
    wer = jiwer.wer(references, hypotheses)
    cer = jiwer.cer(references, hypotheses)
    result = {"n": len(rows), "wer": round(wer, 3), "cer": round(cer, 3), "details": details}
    RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"n={result['n']} WER={result['wer']} CER={result['cer']}")
    print(f"Saved {RESULTS}")


if __name__ == "__main__":
    main()
