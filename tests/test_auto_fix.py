import pytest
from shapely.geometry import box
from app.schemas.geometry import FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType, OpeningGeometry, OpeningType
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints, AdjacencyPreference
from app.schemas.validation import SeverityLevel, ConstraintCategory
from app.geometry.engine import GeometryValidationEngine
from app.geometry.auto_fix import AutoFixEngine
from app.geometry.quality import LayoutQualityEvaluator
from app.geometry.adjacencies import check_adjacencies_and_privacy

def make_25x40_plot():
    """Standard 25 ft x 40 ft residential plot with statutory setbacks."""
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

def test_two_rooms_intentionally_overlap_repaired():
    """Test Case 1: Detect and repair intentional room overlap at geometry-engine level."""
    plot = make_25x40_plot()
    # Living Room (x=2, y=3, w=14, l=12) and Staircase (x=12, y=3, w=9, l=12)
    # They overlap horizontally between x=12 and x=16 (4 ft x 12 ft = 48 sqft overlap)
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=14.0, length=12.0)
    r2 = RoomGeometry(id="r2", name="Internal Staircase", room_type=RoomType.STAIRCASING, x=12.0, y=3.0, width=9.0, length=12.0)
    layout = FloorPlanLayout(id="overlap_test", plot=plot, rooms=[r1, r2])

    val = GeometryValidationEngine.validate_layout(layout)
    assert any(i.constraint_type == ConstraintCategory.ROOM_OVERLAP for i in val.issues)
    assert val.error_count > 0

    # Execute targeted Auto-Fix on overlap
    overlap_issue = next(i for i in val.issues if i.constraint_type == ConstraintCategory.ROOM_OVERLAP)
    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, overlap_issue)

    # Re-validate with Shapely
    p1 = box(fixed_layout.rooms[0].x, fixed_layout.rooms[0].y, fixed_layout.rooms[0].x + fixed_layout.rooms[0].width, fixed_layout.rooms[0].y + fixed_layout.rooms[0].length)
    p2 = box(fixed_layout.rooms[1].x, fixed_layout.rooms[1].y, fixed_layout.rooms[1].x + fixed_layout.rooms[1].width, fixed_layout.rooms[1].y + fixed_layout.rooms[1].length)

    inter_area = p1.intersection(p2).area
    assert inter_area <= 0.05, f"Expected 0 overlap area, got {inter_area}"
    assert len(diffs) > 0

def test_room_extends_beyond_buildable_boundary_repaired():
    """Test Case 2: Room extending into setbacks is detected and repositioned within buildable envelope."""
    plot = make_25x40_plot()
    # Room placed at x=0.5 (violating setback_left=2.0) and y=1.0 (violating setback_front=3.0)
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=0.5, y=1.0, width=12.0, length=12.0)
    layout = FloorPlanLayout(id="boundary_test", plot=plot, rooms=[r1])

    val = GeometryValidationEngine.validate_layout(layout)
    boundary_issues = [i for i in val.issues if i.constraint_type == ConstraintCategory.SETBACK_VIOLATION]
    assert len(boundary_issues) > 0

    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, boundary_issues[0])
    fixed_r = fixed_layout.rooms[0]

    assert fixed_r.x >= plot.setback_left - 0.01
    assert fixed_r.y >= plot.setback_front - 0.01
    assert (fixed_r.x + fixed_r.width) <= (plot.width - plot.setback_right + 0.01)

def test_sub_minimum_bedroom_dimensions_repaired():
    """Test Case 3: Bedroom with sub-minimum dimensions is detected and expanded."""
    plot = make_25x40_plot()
    # Bedroom with width 7.0 ft (code minimum is 9.0 ft)
    r_bed = RoomGeometry(id="bed", name="Master Bedroom", room_type=RoomType.BEDROOM, x=2.0, y=20.0, width=7.0, length=12.0)
    layout = FloorPlanLayout(id="dim_test", plot=plot, rooms=[r_bed])

    val = GeometryValidationEngine.validate_layout(layout)
    dim_issues = [i for i in val.issues if i.constraint_type == ConstraintCategory.MIN_DIMENSION]
    assert len(dim_issues) > 0

    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, dim_issues[0])
    fixed_bed = fixed_layout.rooms[0]

    assert fixed_bed.width >= 9.0 - 0.01, f"Expected bedroom width >= 9.0, got {fixed_bed.width}"

def test_bathroom_in_front_of_open_kitchen_detected_and_repaired():
    """Test Case 4: Bathroom placed directly facing kitchen workspace is detected and buffered."""
    plot = make_25x40_plot()
    kitchen = RoomGeometry(id="k1", name="Kitchen", room_type=RoomType.KITCHEN, x=2.0, y=15.0, width=10.0, length=9.0)
    # Bathroom directly facing / adjacent to kitchen without corridor buffer
    bath = RoomGeometry(id="b1", name="Bathroom", room_type=RoomType.BATHROOM, x=12.0, y=15.0, width=9.0, length=9.0)
    # Door directly opening into kitchen workspace
    door = OpeningGeometry(id="d1", type=OpeningType.DOOR, room_id="b1", wall_side="west", offset=2.0, width=2.8)

    layout = FloorPlanLayout(id="privacy_test", plot=plot, rooms=[kitchen, bath], openings=[door])
    val = GeometryValidationEngine.validate_layout(layout)

    privacy_issues = [i for i in val.issues if i.constraint_type == ConstraintCategory.PRIVACY_ADJACENCY]
    assert len(privacy_issues) > 0, "Expected privacy / adjacency issue between bathroom and kitchen"

    # Auto-Fix should reposition bathroom or buffer door
    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, privacy_issues[0])
    assert len(diffs) > 0

def test_missing_required_room_detected_and_repaired():
    """Test Case 5: Missing mandatory space is flagged and synthesized into layout."""
    plot = make_25x40_plot()
    living = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=12.0, length=12.0)
    layout = FloorPlanLayout(id="missing_test", plot=plot, rooms=[living])

    required_spaces = [
        SpaceRequirement(id="req_bed", room_type="bedroom", label="Bedroom", quantity=1, is_mandatory=True, preferred_width=11.0, preferred_length=11.0, min_width=9.0, min_length=9.0)
    ]

    val = GeometryValidationEngine.validate_layout(layout, required_spaces=required_spaces)
    missing_issues = [i for i in val.issues if i.constraint_type == ConstraintCategory.MISSING_ROOM]
    assert len(missing_issues) > 0

    fixed_layout, diffs = AutoFixEngine.fix_single_issue(layout, missing_issues[0], required_spaces=required_spaces)
    room_types = [r.room_type for r in fixed_layout.rooms]
    assert RoomType.BEDROOM in room_types

def test_auto_fix_all_multiple_simultaneous_errors():
    """Test Case 6: Multi-cycle Auto-Fix All loop corrects multiple simultaneous errors."""
    plot = make_25x40_plot()
    # Simultaneous errors:
    # 1. r1 breaches left setback (x=0.5 < 2.0)
    # 2. r1 and r2 overlap (r1 width=16 overlaps r2 at x=12)
    # 3. r3 is undersized bedroom (width=7.0 < 9.0)
    r1 = RoomGeometry(id="r1", name="Living Room", room_type=RoomType.LIVING_ROOM, x=0.5, y=3.0, width=16.0, length=12.0)
    r2 = RoomGeometry(id="r2", name="Stairs", room_type=RoomType.STAIRCASING, x=12.0, y=3.0, width=9.0, length=12.0)
    r3 = RoomGeometry(id="r3", name="Bedroom", room_type=RoomType.BEDROOM, x=2.0, y=22.0, width=7.0, length=12.0)

    layout = FloorPlanLayout(id="multi_error", plot=plot, rooms=[r1, r2, r3])

    initial_val = GeometryValidationEngine.validate_layout(layout)
    assert initial_val.error_count >= 2

    result = AutoFixEngine.auto_fix_all(layout, max_cycles=5)
    final_val = result["final_validation"]

    assert result["resolved_issues_count"] >= 1
    assert final_val.error_count < initial_val.error_count

def test_quality_evaluator_scores_and_separates_hard_constraints():
    """Test Case 7: Quality evaluator separates hard constraint failures from soft scores."""
    plot = make_25x40_plot()
    # Invalid layout with overlap
    r1 = RoomGeometry(id="r1", name="Living", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=14.0, length=12.0)
    r2 = RoomGeometry(id="r2", name="Stairs", room_type=RoomType.STAIRCASING, x=10.0, y=3.0, width=10.0, length=12.0)
    invalid_layout = FloorPlanLayout(id="inv", plot=plot, rooms=[r1, r2])

    q_invalid = LayoutQualityEvaluator.evaluate_layout(invalid_layout)
    assert q_invalid["hard_constraints_passed"] is False
    assert q_invalid["overall_quality_score"] <= 35.0 # Invalid designs capped

    # Valid residential layout with privacy buffer
    valid_rooms = [
        RoomGeometry(id="r1", name="Living", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=14.0, length=12.0),
        RoomGeometry(id="r2", name="Staircase", room_type=RoomType.STAIRCASING, x=16.0, y=3.0, width=7.0, length=12.0),
        RoomGeometry(id="r3", name="Kitchen", room_type=RoomType.KITCHEN, x=2.0, y=15.0, width=11.0, length=9.0),
        RoomGeometry(id="r4", name="Bathroom", room_type=RoomType.BATHROOM, x=15.0, y=15.0, width=8.0, length=9.0),
        RoomGeometry(id="r5", name="Master Bedroom", room_type=RoomType.BEDROOM, x=2.0, y=24.0, width=21.0, length=14.0)
    ]
    valid_layout = FloorPlanLayout(id="val", plot=plot, rooms=valid_rooms)
    q_valid = LayoutQualityEvaluator.evaluate_layout(valid_layout)

    assert q_valid["hard_constraints_passed"] is True
    assert q_valid["overall_quality_score"] > 70.0
