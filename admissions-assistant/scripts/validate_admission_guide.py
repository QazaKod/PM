"""Validate a reviewed policy file before publishing it; no DB or network calls."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.admission_guide import load_catalog, GuideUnavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        data = load_catalog(args.path)
    except GuideUnavailable as exc:
        parser.exit(1, f'Invalid procedure: {exc}\n')
    print(f'Valid reviewed procedure: {data.version}; {len(data.routes)} routes; review due {data.review_due}')


if __name__ == '__main__':
    main()
