#!/usr/bin/env python3

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build CAT list file for condor queue")
    parser.add_argument("--samples-base", required=True)
    parser.add_argument("--cat-glob", default="cat[0-9][0-9][0-9][0-9][0-9][0-9]")
    parser.add_argument("--limit", type=int, default=0, help="0 means all")
    parser.add_argument("--output", default="condor/cat_list.txt")
    parser.add_argument(
        "--include-training",
        action="store_true",
        help="Also include cats flagged with TRAINING_CAT.txt (used to train the "
        "CT networks); by default they are excluded from evaluation runs.",
    )
    args = parser.parse_args()

    base = Path(args.samples_base)
    cats = sorted([p.name for p in base.glob(args.cat_glob) if p.is_dir()])
    if not args.include_training:
        flagged = [c for c in cats if (base / c / "TRAINING_CAT.txt").is_file()]
        if flagged:
            print(f"Excluding {len(flagged)} training cats (TRAINING_CAT.txt marker); "
                  f"pass --include-training to keep them")
            cats = [c for c in cats if c not in set(flagged)]
    if args.limit > 0:
        cats = cats[:args.limit]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(cats) + ("\n" if cats else ""))

    print(f"Wrote {len(cats)} cats to {out}")


if __name__ == "__main__":
    main()
