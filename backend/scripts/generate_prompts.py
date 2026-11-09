import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import languages, prompts


def main() -> None:
    failed = []
    for code in languages.LANGUAGES:
        for key in prompts.PROMPTS:
            path = prompts.ensure_audio(key, code)
            if path is None:
                failed.append(f"{key}.{code}")
                print(f"failed  {key} ({code})")
            else:
                print(f"ok      {key} ({code}) -> {path}")
    source = ROOT / "static" / "prompts"
    files = sorted(f.name for f in source.glob("*.mp3") if f.stat().st_size > 0)
    web = ROOT.parent / "frontend" / "public" / "static" / "prompts"
    if web.parent.parent.exists():
        web.mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copy2(source / name, web / name)
        print(f"copied {len(files)} files to {web}")
    manifest = ROOT.parent / "worker" / "src" / "data" / "audio_manifest.json"
    if manifest.parent.exists():
        manifest.write_text(json.dumps(files), encoding="utf-8")
        print(f"updated {manifest}")
    if failed:
        print("Some prompts could not be synthesized. Check your network connection and run the script again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
