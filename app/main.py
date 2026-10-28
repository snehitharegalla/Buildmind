import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.project import Project, LayoutRecord
from app.presets.defaults import PRESET_COMPACT_URBAN_25X40
from app.ai.demo_solver import ArchitecturalGeometricSolver
from app.geometry.engine import GeometryValidationEngine
from app.schemas.geometry import FloorPlanLayout
from app.api import api_router

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("buildmind")

# Create database tables
Base.metadata.create_all(bind=engine)

def seed_demo_project_if_empty():
    """Seeds the mandatory 25 ft x 40 ft demonstration project if database is fresh."""
    db = SessionLocal()
    try:
        demo_spec = PRESET_COMPACT_URBAN_25X40
        project_id = "demo_project_25x40"
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            logger.info("Database empty: Seeding mandatory 25 ft x 40 ft residential demonstration project...")
            init_layout = ArchitecturalGeometricSolver.generate_variant(
                variant_type="space_optimized",
                plot=demo_spec["plot"],
                spaces=demo_spec["spaces"],
                relationships=demo_spec["relationships"],
                preferences=demo_spec["preferences"]
            )
            # Authoritative validation
            GeometryValidationEngine.validate_layout(
                layout=init_layout,
                required_spaces=demo_spec["spaces"],
                relationships=demo_spec["relationships"],
                constraints=demo_spec["constraints"]
            )

            project = Project(
                id=project_id,
                name=demo_spec["name"],
                description=demo_spec["description"],
                plot_spec=demo_spec["plot"].dict(),
                space_requirements=[s.dict() for s in demo_spec["spaces"]],
                design_relationships=demo_spec["relationships"].dict(),
                preferences=demo_spec["preferences"].dict(),
                constraints=demo_spec["constraints"].dict(),
                selected_layout_id=init_layout.id
            )

            layout_rec = LayoutRecord(
                id=init_layout.id,
                project_id=project_id,
                version=1,
                variant_type="space_optimized",
                name=init_layout.name,
                data=init_layout.dict()
            )

            db.add(project)
            db.add(layout_rec)
            db.commit()
            logger.info(f"Demo project seeded successfully with ID: {project_id}")
        else:
            # Verify demo layout validity; refresh if previous version had conflicts
            layout_rec = db.query(LayoutRecord).filter(LayoutRecord.id == project.selected_layout_id).first()
            if layout_rec:
                curr_l = FloorPlanLayout(**layout_rec.data)
                val = GeometryValidationEngine.validate_layout(
                    curr_l,
                    required_spaces=demo_spec["spaces"],
                    relationships=demo_spec["relationships"],
                    constraints=demo_spec["constraints"]
                )
                if not val.is_valid or val.error_count > 0:
                    logger.info("Refreshing demo project layout with updated geometric solver...")
                    clean_l = ArchitecturalGeometricSolver.generate_variant(
                        variant_type="space_optimized",
                        plot=demo_spec["plot"],
                        spaces=demo_spec["spaces"],
                        relationships=demo_spec["relationships"],
                        preferences=demo_spec["preferences"]
                    )
                    layout_rec.data = clean_l.dict()
                    db.commit()
    except Exception as e:
        logger.error(f"Error seeding demo project: {e}")
        db.rollback()
    finally:
        db.close()

seed_demo_project_if_empty()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Constraint-Aware Architectural Layout Generation & Geometry Validation Engine."
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "llm_provider": settings.LLM_PROVIDER
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "buildmind-backend"}
