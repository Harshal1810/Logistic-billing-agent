from datetime import datetime

from sqlalchemy.orm import Session

from app.models.review_task import ReviewTask


def create_review_task(
    db: Session,
    run_id: str,
    freight_bill_id: str,
    interrupt_payload: dict,
    review_summary: str | None = None,
) -> ReviewTask:
    existing = (
        db.query(ReviewTask)
        .filter(
            ReviewTask.run_id == run_id,
            ReviewTask.freight_bill_id == freight_bill_id,
            ReviewTask.status == "pending",
        )
        .one_or_none()
    )
    if existing is not None:
        existing.interrupt_payload = interrupt_payload
        existing.review_summary = review_summary
        db.add(existing)
        return existing

    row = ReviewTask(
        run_id=run_id,
        freight_bill_id=freight_bill_id,
        status="pending",
        interrupt_payload=interrupt_payload,
        review_summary=review_summary,
    )
    db.add(row)
    return row


def get_pending_review_task_for_bill(db: Session, freight_bill_id: str) -> ReviewTask | None:
    return (
        db.query(ReviewTask)
        .filter(
            ReviewTask.freight_bill_id == freight_bill_id,
            ReviewTask.status == "pending",
        )
        .order_by(ReviewTask.created_at.desc())
        .first()
    )


def get_pending_review_task_for_run(db: Session, run_id: str) -> ReviewTask | None:
    return (
        db.query(ReviewTask)
        .filter(
            ReviewTask.run_id == run_id,
            ReviewTask.status == "pending",
        )
        .order_by(ReviewTask.created_at.desc())
        .first()
    )


def get_latest_review_task_for_bill(db: Session, freight_bill_id: str) -> ReviewTask | None:
    return (
        db.query(ReviewTask)
        .filter(ReviewTask.freight_bill_id == freight_bill_id)
        .order_by(ReviewTask.created_at.desc())
        .first()
    )


def list_pending_review_tasks(db: Session) -> list[ReviewTask]:
    return (
        db.query(ReviewTask)
        .filter(ReviewTask.status == "pending")
        .order_by(ReviewTask.created_at.asc())
        .all()
    )


def resolve_review_task(
    db: Session,
    task: ReviewTask,
    reviewer_decision: str,
    reviewer_notes: str | None,
) -> ReviewTask:
    if task.status != "pending":
        # Idempotent completion for repeated identical submissions.
        if task.reviewer_decision == reviewer_decision and task.reviewer_notes == reviewer_notes:
            return task
        raise ValueError(f"Review task {task.id} is already {task.status}")

    task.status = "completed"
    task.reviewer_decision = reviewer_decision
    task.reviewer_notes = reviewer_notes
    task.resolved_at = datetime.utcnow()
    db.add(task)
    return task


def update_review_summary(
    db: Session,
    task: ReviewTask,
    review_summary: str,
) -> ReviewTask:
    task.review_summary = review_summary
    db.add(task)
    return task
