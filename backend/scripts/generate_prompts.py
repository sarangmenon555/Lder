import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import prompts


def main() -> None:
    failed = []
    for key in prompts.PROMPTS:
        path = prompts.ensure_audio(key)
        if path is None:
            failed.append(key)
            print(f"failed  {key}")
        else:
            print(f"ok      {key} -> {path}")
    if failed:
        print("Some prompts could not be synthesized. Check your network connection and run the script again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
