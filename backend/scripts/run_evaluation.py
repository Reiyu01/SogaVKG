import argparse

from app.core.runtime import build_runtime
from app.evaluation.runner import EvaluationRunner, load_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SogaVKG query MVP evaluation")
    parser.add_argument(
        "dataset",
        nargs="?",
        default="evaluation/lab_mvp.json",
        help="Path to a strict evaluation dataset",
    )
    args = parser.parse_args()
    report = EvaluationRunner(build_runtime().service).run(load_dataset(args.dataset))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
