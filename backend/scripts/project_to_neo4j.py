from app.db.postgres import SessionLocal
from app.graph.constraints import create_constraints
from app.graph.projector import GraphProjector


def main() -> None:
    create_constraints()

    db = SessionLocal()
    try:
        projector = GraphProjector(db)
        projector.project_all()
        print("Projection to Neo4j completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()