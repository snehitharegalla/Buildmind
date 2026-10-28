import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.project import Project, LayoutRecord, RevisionRecord
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectDetailResponse, ProjectSummaryResponse
)
from app.schemas.geometry import FloorPlanLayout, PlotGeometry
from app.presets.defaults import ALL_PRESETS, PRESET_COMPACT_URBAN_25X40
from app.ai.demo_solver import ArchitecturalGeometricSolver
from app.geometry.engine import GeometryValidationEngine

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/presets", response_model=List[dict])
def get_architectural_presets():
    """Retrieve pre-configured realistic architectural presets."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "plot": p["plot"].dict(),
            "spaces": [s.dict() for s in p["spaces"]],
            "relationships": p["relationships"].dict(),
            "preferences": p["preferences"].dict(),
            "constraints": p["constraints"].dict()
        }
        for p in ALL_PRESETS
    ]

@router.get("", response_model=List[ProjectSummaryResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all projects in the library with preview layout data."""
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    results = []
    for p in projects:
        # Find active or first layout
        preview_rooms = []
        room_count = 0
        if p.layouts:
            chosen = None
            if p.selected_layout_id:
                for l in p.layouts:
                    if l.id == p.selected_layout_id:
                        chosen = l
                        break
            if not chosen and p.layouts:
                chosen = p.layouts[0]
            
            if chosen and isinstance(chosen.data, dict):
                rms = chosen.data.get("rooms", [])
                room_count = len(rms)
                preview_rooms = [
                    {"name": r.get("name"), "x": r.get("x", 0), "y": r.get("y", 0), "width": r.get("width", 10), "length": r.get("length", 10), "material_finish": r.get("material_finish", "terrazzo")}
                    for r in rms[:12]
                ]

        results.append(
            ProjectSummaryResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                updated_at=p.updated_at,
                plot_width=p.plot_spec.get("width", 25.0),
                plot_length=p.plot_spec.get("length", 40.0),
                total_area=p.plot_spec.get("total_area", 1000.0),
                unit=p.plot_spec.get("unit", "ft"),
                layout_count=len(p.layouts),
                selected_layout_id=p.selected_layout_id,
                room_count=room_count,
                preview_rooms=preview_rooms
            )
        )
    return results

@router.post("", response_model=ProjectDetailResponse)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new architectural project and seed initial baseline layout."""
    project_id = str(uuid.uuid4())
    
    # Create project record
    new_project = Project(
        id=project_id,
        name=data.name,
        description=data.description,
        plot_spec=data.plot.dict(),
        space_requirements=[s.dict() for s in data.spaces],
        design_relationships=data.relationships.dict(),
        preferences=data.preferences.dict(),
        constraints=data.constraints.dict()
    )

    # Generate initial default Space-Optimized layout
    init_layout = ArchitecturalGeometricSolver.generate_variant(
        variant_type="space_optimized",
        plot=data.plot,
        spaces=data.spaces,
        relationships=data.relationships,
        preferences=data.preferences
    )

    # Validate
    GeometryValidationEngine.validate_layout(
        layout=init_layout,
        required_spaces=data.spaces,
        relationships=data.relationships,
        constraints=data.constraints
    )

    layout_record = LayoutRecord(
        id=init_layout.id,
        project_id=project_id,
        version=1,
        variant_type="space_optimized",
        name=init_layout.name,
        data=init_layout.dict()
    )

    new_project.selected_layout_id = init_layout.id
    db.add(new_project)
    db.add(layout_record)
    db.commit()
    db.refresh(new_project)

    return get_project(project_id, db)

@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Retrieve full project details, specifications, and layouts."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    layouts = [FloorPlanLayout(**l.data) for l in project.layouts]
    selected_layout = None
    if project.selected_layout_id:
        for l in layouts:
            if l.id == project.selected_layout_id:
                selected_layout = l
                break
    if not selected_layout and layouts:
        selected_layout = layouts[0]

    revisions = [
        {
            "id": r.id,
            "iteration": r.iteration,
            "trigger_reason": r.trigger_reason,
            "prompt_request": r.prompt_request,
            "changes_made": r.changes_made,
            "resolved_all_errors": r.resolved_all_errors,
            "created_at": r.created_at
        }
        for r in project.revisions
    ]

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        plot=PlotGeometry(**project.plot_spec),
        spaces=project.space_requirements,
        relationships=project.design_relationships,
        preferences=project.preferences,
        constraints=project.constraints,
        selected_layout=selected_layout,
        layouts=layouts,
        revisions=revisions
    )

@router.put("/{project_id}", response_model=ProjectDetailResponse)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    """Update project specifications, plot dimensions, or active layout."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.plot is not None:
        project.plot_spec = data.plot.dict()
    if data.spaces is not None:
        project.space_requirements = [s.dict() for s in data.spaces]
    if data.relationships is not None:
        project.design_relationships = data.relationships.dict()
    if data.preferences is not None:
        project.preferences = data.preferences.dict()
    if data.constraints is not None:
        project.constraints = data.constraints.dict()
    if data.selected_layout_id is not None:
        project.selected_layout_id = data.selected_layout_id

    project.updated_at = datetime.datetime.utcnow()
    db.commit()
    return get_project(project_id, db)

@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and its associated layouts."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "success", "message": f"Project '{project.name}' deleted"}
