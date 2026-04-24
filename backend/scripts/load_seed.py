import argparse

from app.services.seed_loader import load_seed_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-freight-bills",
        action="store_true",
        help="Also preload freight_bills from seed JSON (default: False)",
    )
    args = parser.parse_args()
    load_seed_data(
        "data/seed data logistics.json",
        include_freight_bills=args.include_freight_bills,
    )
