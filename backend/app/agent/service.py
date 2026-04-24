from uuid import uuid4

from app.agent.graph import build_review_resume_graph, build_workflow_graph
from app.agent.logging_utils import log_event
from app.db.postgres import SessionLocal
from app.graph.constraints import create_constraints
from app.graph.projector import GraphProjector
from app.repositories.agent_runs import (
    create_agent_run,
    get_agent_run_by_run_id,
    get_latest_agent_run_for_bill,
    update_agent_run,
)
from app.repositories.review_tasks import (
    get_latest_review_task_for_bill,
    get_pending_review_task_for_run,
    resolve_review_task,
)


_WORKFLOW = build_workflow_graph().compile()
_RESUME_WORKFLOW = build_review_resume_graph().compile()


def _sync_run_state(run_id: str, freight_bill_id: str, state_values: dict) -> dict:
    status = state_values.get("workflow_status", "completed")
    current_node = state_values.get("current_node", "completed")

    db = SessionLocal()
    try:
        update_agent_run(
            db=db,
            run_id=run_id,
            workflow_status=status,
            current_node=current_node,
            state_payload=state_values,
            last_error=None,
        )
        db.commit()
    finally:
        db.close()

    return {
        "run_id": run_id,
        "freight_bill_id": freight_bill_id,
        "workflow_status": status,
        "current_node": current_node,
        "state_payload": state_values,
    }


def start_workflow(freight_bill_id: str, force_reprocess: bool = False) -> dict:
    db = SessionLocal()
    try:
        latest = get_latest_agent_run_for_bill(db, freight_bill_id)
        if (
            latest is not None
            and latest.workflow_status in {"running", "waiting_for_review", "completed"}
            and not force_reprocess
        ):
            log_event(
                "workflow.start_skipped_idempotent",
                run_id=latest.run_id,
                freight_bill_id=freight_bill_id,
                workflow_status=latest.workflow_status,
            )
            return {
                "run_id": latest.run_id,
                "freight_bill_id": freight_bill_id,
                "workflow_status": latest.workflow_status,
                "current_node": latest.current_node,
                "state_payload": latest.state_payload,
            }
    finally:
        db.close()

    run_id = uuid4().hex

    db = SessionLocal()
    try:
        create_agent_run(
            db=db,
            run_id=run_id,
            freight_bill_id=freight_bill_id,
            workflow_status="running",
            current_node="start",
            state_payload={"freight_bill_id": freight_bill_id, "run_id": run_id},
        )
        db.commit()
        log_event("workflow.start", run_id=run_id, freight_bill_id=freight_bill_id)

        create_constraints()
        projector = GraphProjector(db)
        projector.project_all()
    finally:
        db.close()

    try:
        result_state = _WORKFLOW.invoke(
            {"freight_bill_id": freight_bill_id, "run_id": run_id},
        )
        return _sync_run_state(run_id, freight_bill_id, dict(result_state or {}))
    except Exception as exc:
        log_event(
            "workflow.failed",
            run_id=run_id,
            freight_bill_id=freight_bill_id,
            error=str(exc),
        )
        db = SessionLocal()
        try:
            update_agent_run(
                db=db,
                run_id=run_id,
                workflow_status="failed",
                current_node="error",
                last_error=str(exc),
            )
            db.commit()
        finally:
            db.close()
        raise


def resume_workflow(
    freight_bill_id: str,
    reviewer_decision: str,
    reviewer_notes: str | None,
) -> dict:
    log_event(
        "workflow.resume_requested",
        freight_bill_id=freight_bill_id,
        reviewer_decision=reviewer_decision,
    )
    db = SessionLocal()
    try:
        latest_run = get_latest_agent_run_for_bill(db, freight_bill_id)
        if latest_run is None:
            raise ValueError(f"No workflow run found for freight bill {freight_bill_id}")

        if latest_run.workflow_status not in {"waiting_for_review", "running"}:
            latest_task = get_latest_review_task_for_bill(db, freight_bill_id)
            if (
                latest_task is not None
                and latest_task.status == "completed"
                and latest_task.reviewer_decision == reviewer_decision
                and latest_task.reviewer_notes == reviewer_notes
            ):
                return {
                    "run_id": latest_run.run_id,
                    "freight_bill_id": freight_bill_id,
                    "workflow_status": latest_run.workflow_status,
                    "current_node": latest_run.current_node,
                    "state_payload": latest_run.state_payload,
                }
            raise ValueError(
                f"Workflow is not waiting for review for freight bill {freight_bill_id}"
            )

        run_id = latest_run.run_id
        task = get_pending_review_task_for_run(db, run_id)
        if task is None:
            raise ValueError(f"No pending review task found for freight bill {freight_bill_id}")

        if latest_run.current_node not in {"review_gate", "completed"}:
            raise ValueError(
                f"Workflow run {run_id} is not resumable from node {latest_run.current_node}"
            )

        start_state = dict(latest_run.state_payload or {})
        start_state["run_id"] = run_id
        start_state["freight_bill_id"] = freight_bill_id
        start_state["reviewer_decision"] = reviewer_decision
        start_state["reviewer_notes"] = reviewer_notes
    finally:
        db.close()

    result_state = _RESUME_WORKFLOW.invoke(start_state)

    db = SessionLocal()
    try:
        task = get_pending_review_task_for_run(db, run_id)
        if task is None:
            raise ValueError(f"No pending review task found for run {run_id}")
        resolve_review_task(
            db=db,
            task=task,
            reviewer_decision=reviewer_decision,
            reviewer_notes=reviewer_notes,
        )
        db.commit()
        log_event(
            "workflow.resume_applied",
            run_id=run_id,
            freight_bill_id=freight_bill_id,
            reviewer_decision=reviewer_decision,
        )
    finally:
        db.close()

    return _sync_run_state(run_id, freight_bill_id, dict(result_state or {}))


def get_workflow_run_for_bill(freight_bill_id: str):
    db = SessionLocal()
    try:
        return get_latest_agent_run_for_bill(db, freight_bill_id)
    finally:
        db.close()


def get_workflow_run_by_run_id(run_id: str):
    db = SessionLocal()
    try:
        return get_agent_run_by_run_id(db, run_id)
    finally:
        db.close()
