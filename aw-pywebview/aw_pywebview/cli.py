import argparse

from .report import generate_report_by_config, load_report_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ActivityWatch report image")
    parser.add_argument(
        "--mode",
        choices=["daily_24h", "today_so_far"],
        help="Report mode",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days for daily_24h mode",
    )
    parser.add_argument(
        "--output-dir",
        help="Override output directory",
    )
    args = parser.parse_args()

    cfg = load_report_config()
    if args.mode:
        cfg.mode = args.mode
    if args.days:
        cfg.days = args.days
    if args.output_dir:
        cfg.output_dir = args.output_dir

    path = generate_report_by_config(cfg)
    if path:
        print(path)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
