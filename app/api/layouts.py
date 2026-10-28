import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.database import get_db
from app.models.project import LayoutRecord, Project
from app.schemas.geometry import FloorPlanLayout, RoomGeometry, OpeningGeometry
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import AutoFixRequest, AutoFixResponse, ValidationReport
from app.geometry.engine import GeometryValidationEngine
from app.geometry.auto_fix import AutoFixEngine

router = APIRouter(prefix="/layouts", tags=["Layouts"])

@router.get("/{layout_id}", response_model=FloorPlanLayout)
def get_layout(layout_id: str, db: Session = Depends(get_db)):
    """Retrieve layout geometry."""
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Layout not found")
    return FloorPlanLayout(**record.data)

@router.put("/{layout_id}", response_model=FloorPlanLayout)
def save_layout(layout_id: str, layout_data: FloorPlanLayout, db: Session = Depends(get_db)):
    """Persist updated layout geometry into database."""
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        # Create record if not existing
        record = LayoutRecord(
            id=layout_id,
            project_id=layout_data.id,
            version=layout_data.version,
            variant_type=layout_data.variant_type,
            name=layout_data.name,
            data=layout_data.dict()
        )
        db.add(record)
    else:
        # Re-calculate areas and metrics
        GeometryValidationEngine.validate_layout(layout_data)
        record.data = layout_data.dict()
        record.version += 1
        record.name = layout_data.name

    db.commit()
    return FloorPlanLayout(**record.data)

@router.put("/{layout_id}/room/{room_id}", response_model=FloorPlanLayout)
def update_room(
    layout_id: str,
    room_id: str,
    room_update: RoomGeometry,
    db: Session = Depends(get_db)
):
    """Update single room coordinates, dimensions, finish, or properties."""
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Layout not found")

    layout = FloorPlanLayout(**record.data)
    room_found = False
    for i, r in enumerate(layout.rooms):
        if r.id == room_id:
            layout.rooms[i] = room_update
            room_found = True
            break

    if not room_found:
        raise HTTPException(status_code=404, detail="Room not found in layout")

    # Authoritative re-validation
    GeometryValidationEngine.validate_layout(layout)
    record.data = layout.dict()
    db.commit()
    return layout

@router.post("/{layout_id}/room", response_model=FloorPlanLayout)
def add_room(
    layout_id: str,
    new_room: RoomGeometry,
    db: Session = Depends(get_db)
):
    """Add a new room to the active floor plan layout."""
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Layout not found")

    layout = FloorPlanLayout(**record.data)
    layout.rooms.append(new_room)
    GeometryValidationEngine.validate_layout(layout)
    record.data = layout.dict()
    db.commit()
    return layout

@router.delete("/{layout_id}/room/{room_id}", response_model=FloorPlanLayout)
def delete_room(
    layout_id: str,
    room_id: str,
    db: Session = Depends(get_db)
):
    """Delete a room from the active floor plan layout."""
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Layout not found")

    layout = FloorPlanLayout(**record.data)
    layout.rooms = [r for r in layout.rooms if r.id != room_id]
    layout.openings = [o for o in layout.openings if o.room_id != room_id]

    GeometryValidationEngine.validate_layout(layout)
    record.data = layout.dict()
    db.commit()
    return layout

@router.post("/{layout_id}/auto-fix", response_model=AutoFixResponse)
def auto_fix_layout(
    layout_id: str,
    req: AutoFixRequest = Body(default_factory=AutoFixRequest),
    db: Session = Depends(get_db)
):
    """
    Controlled Architectural Auto-Fix and Repair System.
    Supports 'Auto-Fix All' multi-cycle optimization or targeted 'Fix This Issue'.
    Supports 'preview_only=True' to inspect proposed modifications without committing.
    """
    record = db.query(LayoutRecord).filter(LayoutRecord.id == layout_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Layout not found")

    layout = FloorPlanLayout(**record.data)

    project = db.query(Project).filter(Project.id == record.project_id).first()
    req_spaces = None
    rels = None
    constraints = None
    if project:
        if project.space_requirements:
            req_spaces = [SpaceRequirement(**s) for s in project.space_requirements]
        if project.design_relationships:
            rels = DesignRelationships(**project.design_relationships)
        if project.constraints:
            constraints = ConfigurableConstraints(**project.constraints)

    if req.issue_id:
        initial_val = GeometryValidationEngine.validate_layout(
            layout,
            required_spaces=req_spaces,
            relationships=rels,
            constraints=constraints
        )
        target_issue = next((iss for iss in initial_val.issues if iss.id == req.issue_id), None)
        if not target_issue:
            raise HTTPException(status_code=404, detail=f"Validation issue '{req.issue_id}' not found in active layout")

        fixed_layout, diffs = AutoFixEngine.fix_single_issue(
            layout=layout,
            issue=target_issue,
            constraints=constraints,
            required_spaces=req_spaces,
            relationships=rels
        )
        final_val = GeometryValidationEngine.validate_layout(
            fixed_layout,
            required_spaces=req_spaces,
            relationships=rels,
            constraints=constraints
        )

        is_resolved = len(diffs) > 0 and not any(iss.id == req.issue_id for iss in final_val.issues)
        success = is_resolved and final_val.error_count <= initial_val.error_count
        resolved_count = 1 if is_resolved else 0
        explanation = (
            f"Applied targeted repair for '{target_issue.title or target_issue.constraint_type}'."
            if success
            else f"Could not safely repair '{target_issue.title or target_issue.constraint_type}' without violating other spatial constraints. Active layout preserved."
        )

        if not req.preview_only and success:
            record.data = fixed_layout.dict()
            record.version += 1
            db.commit()

        return AutoFixResponse(
            success=success,
            cycles_run=1,
            resolved_issues_count=resolved_count,
            remaining_issues_count=len(final_val.issues),
            fixed_layout=fixed_layout if success else layout,
            initial_validation=initial_val,
            final_validation=final_val if success else initial_val,
            revisions_applied=diffs,
            rejected_attempts=[] if success else [explanation],
            explanation=explanation
        )
    else:
        result = AutoFixEngine.auto_fix_all(
            layout=layout,
            constraints=constraints,
            required_spaces=req_spaces,
            relationships=rels,
            max_cycles=req.max_cycles
        )

        fixed_layout = result["fixed_layout"]
        success = result["is_success"] or result["resolved_issues_count"] > 0
        if not req.preview_only and success and result["revisions_applied"]:
            record.data = fixed_layout.dict()
            record.version += 1
            db.commit()

        return AutoFixResponse(
            success=success,
            cycles_run=result["cycles_run"],
            resolved_issues_count=result["resolved_issues_count"],
            remaining_issues_count=result["remaining_issues_count"],
            fixed_layout=fixed_layout,
            initial_validation=result["initial_validation"],
            final_validation=result["final_validation"],
            revisions_applied=result["revisions_applied"],
            rejected_attempts=result.get("rejected_attempts", []),
            explanation=f"Auto-Fix All executed {result['cycles_run']} iteration cycles. Resolved {result['resolved_issues_count']} issues. {result['remaining_issues_count']} issues remaining."
        )
