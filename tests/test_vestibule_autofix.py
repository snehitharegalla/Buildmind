import copy
import pytest
from shapely.geometry import box
from app.schemas.geometry import (
    FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType, OpeningGeometry, OpeningType
)
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import SeverityLevel, ConstraintCategory, ValidationIssue
from app.geometry.engine import GeometryValidationEngine
from app.geometry.auto_fix import AutoFixEngine
from app.geometry.dimensions import ROOM_MINIMUMS
from app.database import SessionLocal
from app.models.project import Project, LayoutRecord

def make_30x25_plot():
    return PlotGeometry(
        width=30.0,
        length=25.0,
        total_area=750.0,
        unit="ft",
        setback_front=3.0,
        setback_rear=2.0,
        setback_left=2.0,
        setback_right=2.0,
        buildable_width=26.0,
        buildable_length=20.0
    )

def make_duplex_spaces():
    return [
        SpaceRequirement(id="req_1", room_type="living_room", label="Living Hall", min_width=11.0, min_length=11.0),
        SpaceRequirement(id="req_2", room_type="staircase", label="Internal Staircase", min_width=5.5, min_length=8.0),
        SpaceRequirement(id="req_3", room_type="kitchen", label="Kitchen", min_width=7.0, min_length=8.0),
        SpaceRequirement(id="req_4", room_type="bedroom", label="Master Bedroom", min_width=10.0, min_length=10.0),
        SpaceRequirement(id="req_5", room_type="bathroom", label="Common Bathroom", min_width=4.5, min_length=5.5),
        SpaceRequirement(id="req_circ", room_type="corridor", label="Central Circulation Lobby", min_width=3.0, min_length=3.0),
    ]

# -----------------------------------------------------------------------------
# 1. Exact Vestibule Bug Reproduction & Auto-Fix Repair
# -----------------------------------------------------------------------------
def test_vestibule_aspect_ratio_and_dimensions_repair():
    """
    Reproduces the exact vestibule issue:
    'Private Dressing & Bath Vestibule' with approx 7.5 x 2.9 ft (aspect ratio 2.62:1).
    Validator flags it under aspect ratio rules or clear dimension rules.
    Verifies that Auto-Fix resolves it into practical, code-compliant geometry.
    """
    plot = make_30x25_plot()
    spaces = make_duplex_spaces()

    # Recreate the exact 3-band crushed layout from DB
    rooms = [
        RoomGeometry(id="rm_living", name="Living Hall", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=19.5, length=7.6),
        RoomGeometry(id="rm_stair", name="Internal Staircase", room_type=RoomType.STAIRCASING, x=21.5, y=3.0, width=6.5, length=7.6),
        RoomGeometry(id="rm_lobby", name="Central Circulation Lobby", room_type=RoomType.CORRIDOR, x=2.0, y=10.6, width=12.48, length=5.6),
        RoomGeometry(id="rm_kit", name="Kitchen", room_type=RoomType.KITCHEN, x=14.48, y=10.6, width=13.52, length=5.6),
        RoomGeometry(id="rm_mbed", name="Master Bedroom", room_type=RoomType.MASTER_BEDROOM, x=2.0, y=16.2, width=18.5, length=6.8),
        RoomGeometry(id="rm_vestibule", name="Private Dressing & Bath Vestibule", room_type=RoomType.FOYER, x=20.5, y=16.2, width=7.5, length=2.86),
        RoomGeometry(id="rm_bath", name="Common Bathroom", room_type=RoomType.BATHROOM, x=20.5, y=19.06, width=7.5, length=3.94),
    ]

    openings = [
        OpeningGeometry(id="d_main", room_id="rm_living", wall_side="north", offset=2.0, width=3.5),
        OpeningGeometry(id="d_bath", room_id="rm_bath", wall_side="north", offset=1.0, width=2.8),
        OpeningGeometry(id="d_vest", room_id="rm_vestibule", wall_side="north", offset=1.0, width=2.8),
    ]

    layout = FloorPlanLayout(id="test_vestibule_repro", plot=plot, rooms=rooms, openings=openings)

    # Initial validation MUST detect vestibule issues
    val_before = GeometryValidationEngine.validate_layout(layout, required_spaces=spaces)
    vest_issues = [i for i in val_before.issues if "rm_vestibule" in i.affected_element_ids or "Private Dressing & Bath Vestibule" in i.affected_rooms]
    assert len(vest_issues) > 0, "Initial vestibule issue must be flagged"

    # Targeted fix on the vestibule issue
    target_iss = vest_issues[0]
    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, issue=target_iss, required_spaces=spaces)

    assert len(diffs) > 0, "Auto-Fix must produce a valid revision for the vestibule issue"
    val_after = GeometryValidationEngine.validate_layout(fixed_layout, required_spaces=spaces)
    remaining_vest_issues = [i for i in val_after.issues if "rm_vestibule" in i.affected_element_ids]
    assert len(remaining_vest_issues) == 0, "Vestibule issue must be fully resolved"

    # Check repaired vestibule geometry
    rep_vest = next(r for r in fixed_layout.rooms if r.id == "rm_vestibule")
    assert min(rep_vest.width, rep_vest.length) >= 3.0, f"Vestibule clear width {min(rep_vest.width, rep_vest.length)} must satisfy code minimum >= 3.0 ft"
    ratio = max(rep_vest.width, rep_vest.length) / min(rep_vest.width, rep_vest.length)
    assert ratio <= 2.4, f"Vestibule aspect ratio {ratio:.2f} must be <= 2.4:1"

# -----------------------------------------------------------------------------
# 2. Full Multi-Cycle Auto-Fix Workflow Resolves 30x25 Layout
# -----------------------------------------------------------------------------
def test_full_autofix_resolves_all_issues():
    """
    Tests complete Auto-Fix All loop on the 30x25 demonstration project.
    Verifies 0 remaining hard errors and valid floor plan with practical layout.
    """
    plot = make_30x25_plot()
    spaces = make_duplex_spaces()

    rooms = [
        RoomGeometry(id="rm_living", name="Living Hall", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=19.5, length=7.6),
        RoomGeometry(id="rm_stair", name="Internal Staircase", room_type=RoomType.STAIRCASING, x=21.5, y=3.0, width=6.5, length=7.6),
        RoomGeometry(id="rm_lobby", name="Central Circulation Lobby", room_type=RoomType.CORRIDOR, x=2.0, y=10.6, width=12.48, length=5.6),
        RoomGeometry(id="rm_kit", name="Kitchen", room_type=RoomType.KITCHEN, x=14.48, y=10.6, width=13.52, length=5.6),
        RoomGeometry(id="rm_mbed", name="Master Bedroom", room_type=RoomType.MASTER_BEDROOM, x=2.0, y=16.2, width=18.5, length=6.8),
        RoomGeometry(id="rm_vestibule", name="Private Dressing & Bath Vestibule", room_type=RoomType.FOYER, x=20.5, y=16.2, width=7.5, length=2.86),
        RoomGeometry(id="rm_bath", name="Common Bathroom", room_type=RoomType.BATHROOM, x=20.5, y=19.06, width=7.5, length=3.94),
    ]

    openings = [
        OpeningGeometry(id="d_main", room_id="rm_living", wall_side="north", offset=2.0, width=3.5),
        OpeningGeometry(id="d_bath", room_id="rm_bath", wall_side="north", offset=1.0, width=2.8),
    ]

    layout = FloorPlanLayout(id="test_full_autofix", plot=plot, rooms=rooms, openings=openings)
    result = AutoFixEngine.auto_fix_all(layout, required_spaces=spaces, max_cycles=5)

    assert result["resolved_issues_count"] > 0, "Auto-Fix All must resolve issues"
    assert result["final_validation"].is_valid, "Final layout must satisfy all hard constraints"
    assert result["final_validation"].error_count == 0, "Final layout must have zero hard errors"

    fixed = result["fixed_layout"]
    assert len(fixed.rooms) == 7, "All 7 spaces must be retained in the layout"

    # Verify no room collapsed
    for r in fixed.rooms:
        assert min(r.width, r.length) >= 3.0, f"Room '{r.name}' dimension {min(r.width, r.length)} must be >= 3.0"

# -----------------------------------------------------------------------------
# 3. Room Overlap Auto-Fix
# -----------------------------------------------------------------------------
def test_room_overlap_fix():
    plot = make_30x25_plot()
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=16.0, length=10.0)
    r2 = RoomGeometry(id="r2", name="Internal Staircase", room_type=RoomType.STAIRCASING, x=15.0, y=3.0, width=8.0, length=10.0)
    layout = FloorPlanLayout(id="test_overlap", plot=plot, rooms=[r1, r2])

    val_before = GeometryValidationEngine.validate_layout(layout)
    assert any(i.constraint_type == ConstraintCategory.ROOM_OVERLAP for i in val_before.issues)

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=4)
    fixed = result["fixed_layout"]
    val_after = result["final_validation"]

    overlap_after = [i for i in val_after.issues if i.constraint_type == ConstraintCategory.ROOM_OVERLAP]
    assert len(overlap_after) == 0, "Room overlap must be completely resolved"

# -----------------------------------------------------------------------------
# 4. Room Outside Buildable Boundary Auto-Fix
# -----------------------------------------------------------------------------
def test_plot_boundary_fix():
    plot = make_30x25_plot()
    # r1 breaches the right setback (x+w = 2.0 + 28.0 = 30.0 > 28.0 max)
    r1 = RoomGeometry(id="r1", name="Living Hall", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=28.0, length=10.0)
    layout = FloorPlanLayout(id="test_boundary", plot=plot, rooms=[r1])

    val_before = GeometryValidationEngine.validate_layout(layout)
    assert any(i.constraint_type in [ConstraintCategory.PLOT_BOUNDARY, ConstraintCategory.SETBACK_VIOLATION] for i in val_before.issues)

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=3)
    val_after = result["final_validation"]
    b_after = [i for i in val_after.issues if i.constraint_type in [ConstraintCategory.PLOT_BOUNDARY, ConstraintCategory.SETBACK_VIOLATION]]
    assert len(b_after) == 0, "Boundary breach must be resolved"
    assert result["fixed_layout"].rooms[0].x + result["fixed_layout"].rooms[0].width <= 28.05

# -----------------------------------------------------------------------------
# 5. Undersized Room Dimension Auto-Fix
# -----------------------------------------------------------------------------
def test_undersized_room_fix():
    plot = make_30x25_plot()
    # Bathroom with length 3.0 ft < 4.5 ft code min
    r1 = RoomGeometry(id="r1", name="Common Bathroom", room_type=RoomType.BATHROOM, x=2.0, y=3.0, width=6.0, length=3.0)
    layout = FloorPlanLayout(id="test_undersized", plot=plot, rooms=[r1])

    val_before = GeometryValidationEngine.validate_layout(layout)
    assert any(i.constraint_type == ConstraintCategory.MIN_DIMENSION for i in val_before.issues)

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=3)
    val_after = result["final_validation"]
    dim_after = [i for i in val_after.issues if i.constraint_type == ConstraintCategory.MIN_DIMENSION]
    assert len(dim_after) == 0, "Undersized room dimension must be resolved"
    r = result["fixed_layout"].rooms[0]
    assert max(r.width, r.length) >= 4.5 and min(r.width, r.length) >= 4.0

# -----------------------------------------------------------------------------
# 6. Bathroom-to-Kitchen Facing Privacy Relationship
# -----------------------------------------------------------------------------
def test_bathroom_kitchen_facing_fix():
    plot = make_30x25_plot()
    # Bathroom and Kitchen placed directly opposite with facing doors
    r_bath = RoomGeometry(id="rm_bath", name="Common Bathroom", room_type=RoomType.BATHROOM, x=2.0, y=10.0, width=6.0, length=6.0)
    r_kit = RoomGeometry(id="rm_kit", name="Kitchen", room_type=RoomType.KITCHEN, x=10.0, y=10.0, width=8.0, length=8.0)
    d_bath = OpeningGeometry(id="d_bath", room_id="rm_bath", wall_side="east", offset=1.0, width=2.8)
    d_kit = OpeningGeometry(id="d_kit", room_id="rm_kit", wall_side="west", offset=1.0, width=3.0)

    layout = FloorPlanLayout(id="test_privacy", plot=plot, rooms=[r_bath, r_kit], openings=[d_bath, d_kit])
    val_before = GeometryValidationEngine.validate_layout(layout)
    priv_issues = [i for i in val_before.issues if i.constraint_type == ConstraintCategory.PRIVACY_ADJACENCY]
    assert len(priv_issues) > 0, "Facing bathroom-kitchen sightline must be detected"

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=3)
    priv_after = [i for i in result["final_validation"].issues if i.constraint_type == ConstraintCategory.PRIVACY_ADJACENCY]
    assert len(priv_after) == 0, "Facing sightline conflict must be eliminated"

# -----------------------------------------------------------------------------
# 7. Candidate Rejection when Introducing New Hard Violation
# -----------------------------------------------------------------------------
def test_candidate_rejected_if_new_hard_error_introduced():
    plot = make_30x25_plot()
    current = FloorPlanLayout(
        id="curr",
        plot=plot,
        rooms=[RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=12.0, length=12.0)]
    )
    val_curr = GeometryValidationEngine.validate_layout(current)

    # Candidate introduces a boundary breach
    candidate = FloorPlanLayout(
        id="cand",
        plot=plot,
        rooms=[RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=30.0, length=12.0)]
    )
    val_cand = GeometryValidationEngine.validate_layout(candidate)

    is_ok, reason = AutoFixEngine.evaluate_candidate(
        candidate_layout=candidate,
        current_layout=current,
        candidate_val=val_cand,
        current_val=val_curr
    )
    assert not is_ok, "Candidate that introduces new hard violation must be rejected"
    assert "hard error" in reason.lower() or "count increased" in reason.lower()

# -----------------------------------------------------------------------------
# 8. Genuinely Infeasible Layout Terminates Safely
# -----------------------------------------------------------------------------
def test_infeasible_layout_terminates_cleanly():
    # 10x10 plot (buildable 6x6 = 36 sq ft) with 4 huge rooms requiring 400 sq ft
    tiny_plot = PlotGeometry(
        width=10.0, length=10.0, total_area=100.0, unit="ft",
        setback_front=2.0, setback_rear=2.0, setback_left=2.0, setback_right=2.0,
        buildable_width=6.0, buildable_length=6.0
    )
    big_spaces = [
        SpaceRequirement(id="req_1", room_type="living_room", label="Living Room", min_width=14.0, min_length=14.0),
        SpaceRequirement(id="req_2", room_type="bedroom", label="Master Bedroom", min_width=12.0, min_length=12.0),
    ]
    rooms = [
        RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=2.0, width=14.0, length=14.0),
        RoomGeometry(id="r2", name="Master Bedroom", room_type=RoomType.MASTER_BEDROOM, x=2.0, y=2.0, width=12.0, length=12.0),
    ]
    layout = FloorPlanLayout(id="infeasible_test", plot=tiny_plot, rooms=rooms)

    result = AutoFixEngine.auto_fix_all(layout, required_spaces=big_spaces, max_cycles=3)
    # Loop must stop gracefully within attempt limit without hanging or corrupting state
    assert result["cycles_run"] <= 3, "Loop must terminate within max_cycles limit"
    assert len(result["fixed_layout"].rooms) == 2, "Original room count must be preserved"

# -----------------------------------------------------------------------------
# 9. Database Undo, Save, Reopen, and Revalidate Workflow
# -----------------------------------------------------------------------------
def test_db_save_reopen_and_revalidate():
    db = SessionLocal()
    try:
        # Fetch project 0d583bff-d2fa-4b7d-9a94-c0bd1f22b2ce
        proj = db.query(Project).filter(Project.id == "0d583bff-d2fa-4b7d-9a94-c0bd1f22b2ce").first()
        if not proj:
            pytest.skip("Project 0d583bff-d2fa-4b7d-9a94-c0bd1f22b2ce not in DB")

        layout_rec = db.query(LayoutRecord).filter(LayoutRecord.id == "8069a315-7c2c-40d3-ad3d-0ad9c3ac78b6").first()
        if not layout_rec:
            pytest.skip("Layout 8069a315-7c2c-40d3-ad3d-0ad9c3ac78b6 not in DB")

        layout = FloorPlanLayout(**layout_rec.data)
        spaces = [SpaceRequirement(**s) for s in proj.space_requirements] if proj.space_requirements else None
        rels = DesignRelationships(**proj.design_relationships) if proj.design_relationships else None
        constraints = ConfigurableConstraints(**proj.constraints) if proj.constraints else None

        # Execute Auto-Fix All
        result = AutoFixEngine.auto_fix_all(layout, required_spaces=spaces, relationships=rels, constraints=constraints)
        fixed_layout = result["fixed_layout"]

        # Save to DB
        original_data = copy.deepcopy(layout_rec.data)
        layout_rec.data = fixed_layout.dict()
        layout_rec.version += 1
        db.commit()

        # Reopen from DB in a fresh query
        db.expire_all()
        reopened_rec = db.query(LayoutRecord).filter(LayoutRecord.id == "8069a315-7c2c-40d3-ad3d-0ad9c3ac78b6").first()
        reopened_layout = FloorPlanLayout(**reopened_rec.data)

        # Revalidate reopened layout
        reopened_val = GeometryValidationEngine.validate_layout(reopened_layout, required_spaces=spaces, relationships=rels, constraints=constraints)
        assert reopened_val.is_valid, "Reopened layout from DB must be 100% valid"
        assert reopened_val.error_count == 0, "Reopened layout must have 0 hard errors"

    finally:
        db.close()
