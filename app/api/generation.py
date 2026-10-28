import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project, LayoutRecord, RevisionRecord
from app.schemas.geometry import FloorPlanLayout, PlotGeometry
from app.schemas.project import SpaceRequirement, DesignRelationships, ProjectPreferences, ConfigurableConstraints
from app.schemas.ai import GenerationRequest, GenerationResult
from app.ai.layout_generator import LayoutGenerationPipeline
from app.geometry.engine import GeometryValidationEngine

router = APIRouter(prefix="/generation", tags=["Generation"])

@router.post("/generate", response_model=GenerationResult)
async def generate_layouts(
    request: GenerationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate architectural floor plan proposals using LLM/geometric solver,
    validate against authoritative Python computational geometry, and auto-repair conflicts.
    """
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    plot = PlotGeometry(**project.plot_spec)
    spaces = [SpaceRequirement(**s) for s in project.space_requirements]
    relationships = DesignRelationships(**project.design_relationships) if project.design_relationships else None
    preferences = ProjectPreferences(**project.preferences) if project.preferences else None
    constraints = ConfigurableConstraints(**project.constraints) if project.constraints else None

    result = await LayoutGenerationPipeline.generate_and_validate_all(
        project_id=project.id,
        plot=plot,
        spaces=spaces,
        relationships=relationships,
        preferences=preferences,
        constraints=constraints,
        variants=request.target_variants,
        max_revisions=request.max_revisions
    )

    # Persist generated candidates into database
    for candidate in result.candidates:
        existing = db.query(LayoutRecord).filter(LayoutRecord.id == candidate.layout.id).first()
        if not existing:
            new_rec = LayoutRecord(
                id=candidate.layout.id,
                project_id=project.id,
                version=candidate.layout.version,
                variant_type=candidate.variant_type,
                name=candidate.title,
                data=candidate.layout.dict()
            )
            db.add(new_rec)
        else:
            existing.data = candidate.layout.dict()

    # Set primary layout as active in project
    project.selected_layout_id = result.primary_layout.id
    db.commit()

    return result
