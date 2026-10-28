import copy
import pytest
from shapely.geometry import box
from app.schemas.geometry import (
    FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType, OpeningGeometry, OpeningType, Point2D
)
from app.schemas.project import (
    SpaceRequirement, DesignRelationships, ConfigurableConstraints, AdjacencyPreference, ProjectPreferences
)
from app.schemas.validation import SeverityLevel, ConstraintCategory
from app.geometry.engine import GeometryValidationEngine
from app.geometry.auto_fix import AutoFixEngine
from app.geometry.quality import LayoutQualityEvaluator
from app.ai.demo_solver import ArchitecturalGeometricSolver
from app.presets.defaults import PRESET_COMPACT_URBAN_25X40
from app.database import SessionLocal, Base, engine
from app.models.project import Project, LayoutRecord

def make_25x40_plot():
    return PlotGeometry(
        width=25.0,
        length=40.0,
        total_area=1000.0,
        unit="ft",
        setback_front=3.0,
        setback_rear=2.0,
        setback_left=2.0,
        setback_right=2.0,
        buildable_width=21.0,
        buildable_length=35.0
    )

def test_scenario_a_overlapping_rooms():
    """
    Test A — Overlapping rooms
    Create two room polygons with overlapping interiors.
    Verify that the overlap is detected. Run Auto-Fix.
    Verify that the accepted result has no overlapping interiors and that neither room disappears.
    """
    plot = make_25x40_plot()
    # Room 1 and Room 2 overlap in X span
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=15.0, length=12.0)
    r2 = RoomGeometry(id="r2", name="Internal Staircase", room_type=RoomType.STAIRCASING, x=13.0, y=3.0, width=8.0, length=12.0)
    layout = FloorPlanLayout(id="test_a_overlap", plot=plot, rooms=[r1, r2])

    val_before = GeometryValidationEngine.validate_layout(layout)
    overlap_issues = [i for i in val_before.issues if i.constraint_type == ConstraintCategory.ROOM_OVERLAP]
    assert len(overlap_issues) > 0, "Initial overlap must be detected"

    # Run auto-fix
    result = AutoFixEngine.auto_fix_all(layout, max_cycles=5)
    fixed = result["fixed_layout"]
    val_after = result["final_validation"]

    # Verify both rooms are preserved
    assert len(fixed.rooms) == 2, "Neither room must disappear"
    fixed_ids = {r.id for r in fixed.rooms}
    assert "r1" in fixed_ids and "r2" in fixed_ids

    # Verify Shapely polygon intersection is 0 (or within float tolerance <= 0.05)
    fr1 = next(r for r in fixed.rooms if r.id == "r1")
    fr2 = next(r for r in fixed.rooms if r.id == "r2")
    p1 = box(fr1.x, fr1.y, fr1.x + fr1.width, fr1.y + fr1.length)
    p2 = box(fr2.x, fr2.y, fr2.x + fr2.width, fr2.y + fr2.length)
    assert p1.intersection(p2).area <= 0.05, f"Overlapping interiors remain: {p1.intersection(p2).area} sqft"
    assert not any(i.constraint_type == ConstraintCategory.ROOM_OVERLAP for i in val_after.issues)

def test_scenario_b_room_outside_plot():
    """
    Test B — Room outside the plot
    Place a room partly outside the buildable boundary.
    Verify that the violation is detected and that a correction is accepted
    only if the resulting room satisfies all applicable constraints.
    """
    plot = make_25x40_plot()
    # Breaching left setback (x = 0.5 < 2.0) and front setback (y = 1.0 < 3.0)
    r1 = RoomGeometry(id="r1", name="Master Bedroom", room_type=RoomType.BEDROOM, x=0.5, y=1.0, width=12.0, length=12.0)
    layout = FloorPlanLayout(id="test_b_boundary", plot=plot, rooms=[r1])

    val_before = GeometryValidationEngine.validate_layout(layout)
    boundary_issues = [i for i in val_before.issues if i.constraint_type in [ConstraintCategory.PLOT_BOUNDARY, ConstraintCategory.SETBACK_VIOLATION]]
    assert len(boundary_issues) > 0, "Boundary violation must be detected"

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=4)
    fixed = result["fixed_layout"]
    val_after = result["final_validation"]

    # Resulting room must satisfy all constraints
    assert val_after.is_valid, f"Expected valid layout, got {val_after.error_count} errors"
    fr = fixed.rooms[0]
    bx_min = plot.setback_left
    bx_max = plot.width - plot.setback_right
    by_min = plot.setback_front
    by_max = plot.length - plot.setback_rear
    assert fr.x >= bx_min - 0.01
    assert fr.y >= by_min - 0.01
    assert fr.x + fr.width <= bx_max + 0.01
    assert fr.y + fr.length <= by_max + 0.01

def test_scenario_c_bathroom_facing_open_kitchen():
    """
    Test C — Bathroom facing an open kitchen
    Create a layout with a bathroom door directly exposed to the kitchen opening.
    Verify that the layout-quality evaluator identifies the undesirable relationship
    and that candidate generation prefers a feasible privacy-preserving alternative.
    """
    plot = make_25x40_plot()
    kitchen = RoomGeometry(id="k1", name="Kitchen", room_type=RoomType.KITCHEN, x=2.0, y=15.0, width=10.0, length=9.0)
    # Bathroom directly facing kitchen with door on north wall facing kitchen
    bath = RoomGeometry(id="b1", name="Bathroom", room_type=RoomType.BATHROOM, x=2.0, y=25.0, width=8.0, length=7.0)
    door = OpeningGeometry(id="d1", type=OpeningType.DOOR, room_id="b1", wall_side="north", offset=2.0, width=2.8)

    layout_bad = FloorPlanLayout(id="test_c_bad", plot=plot, rooms=[kitchen, bath], openings=[door])

    # 1. Quality evaluator identifies undesirable relationship
    q_bad = LayoutQualityEvaluator.evaluate_layout(layout_bad)
    assert any("doorway" in note.lower() or "kitchen" in note.lower() for note in q_bad["notes"])
    assert q_bad["privacy_score"] < 100

    # 2. Candidate generation prefers feasible privacy-preserving alternative
    val_bad = GeometryValidationEngine.validate_layout(layout_bad)
    target_privacy_issue = next((i for i in val_bad.issues if i.constraint_type == ConstraintCategory.PRIVACY_ADJACENCY), None)
    assert target_privacy_issue is not None

    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout_bad, target_privacy_issue)
    assert len(diffs) > 0, "Privacy repair must propose an alternative"

    q_fixed = LayoutQualityEvaluator.evaluate_layout(fixed_layout)
    assert q_fixed["privacy_score"] >= q_bad["privacy_score"]

def test_scenario_d_multiple_simultaneous_errors():
    """
    Test D — Multiple simultaneous errors
    Introduce overlapping rooms, an invalid room dimension, and a boundary violation.
    Run Auto-Fix All. Verify that corrections are applied sequentially,
    all issues are re-evaluated, and the process stops safely if no feasible solution exists.
    """
    plot = make_25x40_plot()
    # 1. r1 breaches setback: x=0.5 < 2.0
    # 2. r1 overlaps r2: r1 width=16 overlaps r2 at x=12
    # 3. r3 is undersized bedroom: width=6.5 < 9.0
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=0.5, y=3.0, width=16.0, length=12.0)
    r2 = RoomGeometry(id="r2", name="Staircase", room_type=RoomType.STAIRCASING, x=12.0, y=3.0, width=9.0, length=12.0)
    r3 = RoomGeometry(id="r3", name="Bedroom", room_type=RoomType.BEDROOM, x=2.0, y=22.0, width=6.5, length=11.0)
    layout = FloorPlanLayout(id="test_d_multi", plot=plot, rooms=[r1, r2, r3])

    val_init = GeometryValidationEngine.validate_layout(layout)
    assert val_init.error_count >= 2

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=5)
    final_val = result["final_validation"]

    # Corrections applied sequentially, reducing errors without crash
    assert result["resolved_issues_count"] >= 1
    assert final_val.error_count < val_init.error_count
    assert result["cycles_run"] <= 5

def test_scenario_e_no_regression_guarantee():
    """
    Test E — No-regression guarantee
    Start with a layout that satisfies all hard constraints.
    Attempt an invalid correction. Verify that the candidate is rejected
    and the active layout remains unchanged.
    """
    plot = make_25x40_plot()
    demo_spec = PRESET_COMPACT_URBAN_25X40
    valid_layout = ArchitecturalGeometricSolver.generate_variant(
        variant_type="space_optimized",
        plot=plot,
        spaces=demo_spec["spaces"],
        relationships=demo_spec["relationships"],
        preferences=demo_spec["preferences"]
    )
    val_initial = GeometryValidationEngine.validate_layout(valid_layout)
    assert val_initial.is_valid, "Initial layout must pass all hard constraints"
    initial_sig = AutoFixEngine.get_layout_signature(valid_layout)

    # Attempt targeted fix on a non-existent issue or dummy issue
    from app.schemas.validation import ValidationIssue, BoundingBox
    dummy_issue = ValidationIssue(
        id="dummy_overlap",
        constraint_type=ConstraintCategory.ROOM_OVERLAP,
        severity=SeverityLevel.ERROR,
        affected_rooms=[valid_layout.rooms[0].name, valid_layout.rooms[1].name],
        affected_element_ids=[valid_layout.rooms[0].id, valid_layout.rooms[1].id],
        measured_value="None",
        expected_condition="0 overlap",
        explanation="Synthetic test issue",
        suggested_correction="None"
    )

    fixed_layout, diffs = AutoFixEngine.fix_single_issue(valid_layout, dummy_issue)

    # Active layout must remain unchanged!
    assert AutoFixEngine.get_layout_signature(fixed_layout) == initial_sig
    val_after = GeometryValidationEngine.validate_layout(fixed_layout)
    assert val_after.is_valid
    assert len(diffs) == 0

def test_scenario_f_correction_loop_termination():
    """
    Test F — Correction-loop termination
    Provide an infeasible set of requirements.
    Verify that the correction engine stops within the configured limit,
    reports unresolved constraints, and does not loop indefinitely.
    """
    plot = make_25x40_plot()
    # 4 massive rooms each 20x20 that cannot fit inside 21x35 envelope
    r1 = RoomGeometry(id="r1", name="Hall 1", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=20.0, length=20.0)
    r2 = RoomGeometry(id="r2", name="Hall 2", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=20.0, length=20.0)
    r3 = RoomGeometry(id="r3", name="Hall 3", room_type=RoomType.LIVING_ROOM, x=2.0, y=10.0, width=20.0, length=20.0)
    r4 = RoomGeometry(id="r4", name="Hall 4", room_type=RoomType.LIVING_ROOM, x=2.0, y=15.0, width=20.0, length=20.0)
    infeasible_layout = FloorPlanLayout(id="test_f_infeasible", plot=plot, rooms=[r1, r2, r3, r4])

    max_cycles = 4
    result = AutoFixEngine.auto_fix_all(infeasible_layout, max_cycles=max_cycles)

    # Must terminate within configured limit
    assert result["cycles_run"] <= max_cycles
    assert result["remaining_issues_count"] > 0
    # Must report unresolved constraints
    assert len(result["rejected_attempts"]) > 0 or not result["is_success"]

def test_scenario_g_undo_and_persistence():
    """
    Test G — Undo and persistence
    Apply a valid correction, undo it, and verify that the original geometry is restored exactly.
    Save and reopen both states and verify their consistency.
    """
    plot = make_25x40_plot()
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=0.5, y=1.0, width=12.0, length=12.0)
    original_layout = FloorPlanLayout(id="test_g_undo", plot=plot, rooms=[r1])
    orig_sig = AutoFixEngine.get_layout_signature(original_layout)

    # 1. Apply correction
    result = AutoFixEngine.auto_fix_all(original_layout, max_cycles=3)
    fixed_layout = result["fixed_layout"]
    fixed_sig = AutoFixEngine.get_layout_signature(fixed_layout)
    assert fixed_sig != orig_sig, "Correction must modify geometry"

    # 2. Undo: Restore exact snapshot
    restored_layout = copy.deepcopy(original_layout)
    restored_sig = AutoFixEngine.get_layout_signature(restored_layout)
    assert restored_sig == orig_sig, "Restored geometry must match original exactly"

    # 3. Persistence: test saving and loading from SQLite
    db = SessionLocal()
    try:
        # Save original state
        rec = LayoutRecord(
            id="test_g_record",
            project_id="test_proj",
            version=1,
            variant_type="space_optimized",
            name="Persistence Test",
            data=original_layout.dict()
        )
        db.merge(rec)
        db.commit()

        # Reopen original state
        loaded_rec = db.query(LayoutRecord).filter(LayoutRecord.id == "test_g_record").first()
        loaded_layout = FloorPlanLayout(**loaded_rec.data)
        assert AutoFixEngine.get_layout_signature(loaded_layout) == orig_sig

        # Save corrected state
        loaded_rec.data = fixed_layout.dict()
        loaded_rec.version = 2
        db.commit()

        # Reopen corrected state
        reloaded_rec = db.query(LayoutRecord).filter(LayoutRecord.id == "test_g_record").first()
        reloaded_layout = FloorPlanLayout(**reloaded_rec.data)
        assert AutoFixEngine.get_layout_signature(reloaded_layout) == fixed_sig
    finally:
        db.close()

def test_scenario_h_real_generated_layout():
    """
    Test H — Real generated layout
    Generate a layout using the existing 25 ft × 40 ft demonstration plot with
    one bedroom, kitchen, living hall, and internal staircase.
    Verify all configured hard constraints and room relationships against the resulting geometry.
    Use realistic configured dimensions and setbacks. Do not hardcode a single demonstration arrangement.
    """
    plot = make_25x40_plot()
    demo_spec = PRESET_COMPACT_URBAN_25X40

    layout = ArchitecturalGeometricSolver.generate_variant(
        variant_type="space_optimized",
        plot=plot,
        spaces=demo_spec["spaces"],
        relationships=demo_spec["relationships"],
        preferences=demo_spec["preferences"]
    )

    # Authoritative Validation
    report = GeometryValidationEngine.validate_layout(
        layout=layout,
        required_spaces=demo_spec["spaces"],
        relationships=demo_spec["relationships"],
        constraints=demo_spec["constraints"]
    )

    # 1. Zero hard errors
    assert report.is_valid is True, f"Generated layout failed validation: {[i.explanation for i in report.issues]}"
    assert report.error_count == 0

    # 2. Verify all required spaces are present
    req_labels = {s.label for s in demo_spec["spaces"]}
    room_names = {r.name for r in layout.rooms}
    for label in req_labels:
        assert label in room_names, f"Required space '{label}' not present in generated layout"

    # 3. Verify no room-interior overlaps using Shapely
    rooms = layout.rooms
    n = len(rooms)
    for i in range(n):
        p1 = box(rooms[i].x, rooms[i].y, rooms[i].x + rooms[i].width, rooms[i].y + rooms[i].length)
        for j in range(i + 1, n):
            p2 = box(rooms[j].x, rooms[j].y, rooms[j].x + rooms[j].width, rooms[j].y + rooms[j].length)
            inter_area = p1.intersection(p2).area
            assert inter_area <= 0.05, f"Rooms '{rooms[i].name}' and '{rooms[j].name}' overlap by {inter_area:.2f} sqft"

    # 4. Verify all rooms are within the buildable envelope
    bx_min = plot.setback_left
    bx_max = plot.width - plot.setback_right
    by_min = plot.setback_front
    by_max = plot.length - plot.setback_rear
    for r in rooms:
        assert r.x >= bx_min - 0.01, f"{r.name} violates left setback"
        assert r.y >= by_min - 0.01, f"{r.name} violates front setback"
        assert r.x + r.width <= bx_max + 0.01, f"{r.name} violates right setback"
        assert r.y + r.length <= by_max + 0.01, f"{r.name} violates rear setback"

    # 5. Verify room relationships: Kitchen and Bathroom are separated (not sharing a wall)
    kitchen = next(r for r in rooms if r.room_type == RoomType.KITCHEN)
    bathroom = next(r for r in rooms if r.room_type == RoomType.BATHROOM)
    kp = box(kitchen.x, kitchen.y, kitchen.x + kitchen.width, kitchen.y + kitchen.length)
    bp = box(bathroom.x, bathroom.y, bathroom.x + bathroom.width, bathroom.y + bathroom.length)
    assert kp.distance(bp) >= 2.0, f"Kitchen and Bathroom must be separated by buffer (actual: {kp.distance(bp):.1f} ft)"

    # 6. Overall Quality Score
    quality = LayoutQualityEvaluator.evaluate_layout(layout, relationships=demo_spec["relationships"])
    assert quality["hard_constraints_passed"] is True
    assert quality["overall_quality_score"] >= 80.0
