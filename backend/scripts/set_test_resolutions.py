from app.db.postgres import SessionLocal
from app.repositories.freight_bills import update_bill_resolution


def main():
    db = SessionLocal()
    try:
        update_bill_resolution(
            db,
            freight_bill_id="FB-2025-101",
            processing_status="completed",
            current_decision="auto_approve",
            final_resolution="approved",
            confidence_score=1.0,
        )

        update_bill_resolution(
            db,
            freight_bill_id="FB-2025-109",
            processing_status="completed",
            current_decision="dispute",
            final_resolution="disputed",
            confidence_score=0.10,
        )

        db.commit()
        print("Test resolutions updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()