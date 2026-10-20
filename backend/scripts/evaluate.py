import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.services import classifier, keywords

DATASET = ROOT / "eval" / "dataset.jsonl"
RESULTS = ROOT / "eval" / "results.json"
LABELS = ["fine", "unwell", "needs_help", "confused", "unclear"]


def load_rows() -> list[dict]:
    rows = []
    with DATASET.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def keyword_baseline(text: str) -> dict:
    if not text.strip():
        return {"status": "unclear", "distress": False, "medicine": "unknown"}
    kw = keywords.analyze(text)
    if kw.critical:
        status = "needs_help"
    elif kw.concern or kw.mild:
        status = "unwell"
    else:
        status = "fine"
    return {"status": status, "distress": bool(kw.critical), "medicine": kw.medicine}


def full_pipeline(text: str, delay: float) -> dict:
    kw = keywords.analyze(text)
    llm = None
    error = None
    if text.strip():
        try:
            llm = classifier.classify_with_llm(text, [], "morning")
        except classifier.ClassifierError as exc:
            error = str(exc)
        time.sleep(delay)
    decision = classifier.build_decision(text, llm, kw, get_settings().confidence_threshold, error)
    return {
        "status": decision.status,
        "distress": decision.distress,
        "medicine": decision.medicine_taken,
        "error": error,
    }


def score(rows: list[dict], predictions: list[dict]) -> dict:
    total = len(rows)
    correct = sum(1 for r, p in zip(rows, predictions) if r["label"] == p["status"])
    tp = sum(1 for r, p in zip(rows, predictions) if r["distress"] and p["distress"])
    fp = sum(1 for r, p in zip(rows, predictions) if not r["distress"] and p["distress"])
    fn = sum(1 for r, p in zip(rows, predictions) if r["distress"] and not p["distress"])
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    medicine_correct = sum(1 for r, p in zip(rows, predictions) if r["medicine"] == p["medicine"])
    confusion: dict[str, Counter] = defaultdict(Counter)
    for r, p in zip(rows, predictions):
        confusion[r["label"]][p["status"]] += 1
    return {
        "n": total,
        "status_accuracy": round(correct / total, 3),
        "distress_precision": None if precision is None else round(precision, 3),
        "distress_recall": None if recall is None else round(recall, 3),
        "distress_f1": None if f1 is None else round(f1, 3),
        "distress_missed": fn,
        "distress_false_alarms": fp,
        "medicine_accuracy": round(medicine_correct / total, 3),
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def print_report(name: str, result: dict) -> None:
    print(f"\n{name}")
    print("-" * len(name))
    for key in (
        "n",
        "status_accuracy",
        "distress_recall",
        "distress_precision",
        "distress_f1",
        "distress_missed",
        "distress_false_alarms",
        "medicine_accuracy",
    ):
        print(f"{key:24}{result[key]}")
    print("confusion (rows are true labels):")
    header = "".join(f"{label:>12}" for label in LABELS)
    print(f"{'':14}{header}")
    for label in LABELS:
        counts = result["confusion"].get(label, {})
        print(f"{label:14}" + "".join(f"{counts.get(other, 0):>12}" for other in LABELS))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--delay", type=float, default=2.5)
    args = parser.parse_args()

    rows = load_rows()
    texts = [r["text"] for r in rows]
    output = {"baseline": score(rows, [keyword_baseline(t) for t in texts])}
    print_report("Keyword-only baseline", output["baseline"])

    if args.skip_llm or not get_settings().groq_api_key:
        print("\nSkipping the full pipeline because the LLM is disabled or GROQ_API_KEY is not set.")
    else:
        predictions = [full_pipeline(t, args.delay) for t in texts]
        output["pipeline"] = score(rows, predictions)
        output["pipeline"]["classifier_errors"] = sum(1 for p in predictions if p.get("error"))
        output["pipeline"]["model"] = get_settings().classifier_model
        print_report("Full pipeline (LLM plus keyword safety layer)", output["pipeline"])
        misses = [
            {"text": r["text"], "label": r["label"], "predicted": p["status"]}
            for r, p in zip(rows, predictions)
            if r["label"] != p["status"]
        ]
        output["pipeline_misses"] = misses

    RESULTS.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {RESULTS}")


if __name__ == "__main__":
    main()
