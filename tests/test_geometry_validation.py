import pytest
from app.schemas.geometry import FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType
from app.schemas.project import SpaceRequirement, ConfigurableConstraints
from app.geometry.engine import GeometryValidationEngine
from app.geometry.dimensions import check_room_dimensions_and_proportions
from app.geometry.completeness import check_required_rooms_completeness

def make_test_plot():
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

def test_valid_layout():
    """Verify that a compliant layout passes validation with 0 hard errors."""
    plot = make_test_plot()
    rooms = [
        RoomGeometry(id="r1", name="Living", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=14.0, length=12.0),
        RoomGeometry(id="r2", name="Stairs", room_type=RoomType.STAIRCASING, x=16.0, y=3.0, width=7.0, length=12.0),
        RoomGeometry(id="r3", name="Kitchen", room_type=RoomType.KITCHEN, x=2.0, y=15.0, width=11.0, length=9.0),
        RoomGeometry(id="r4", name="Bath", room_type=RoomType.BATHROOM, x=13.0, y=15.0, width=10.0, length=9.0),
        RoomGeometry(id="r5", name="Bedroom", room_type=RoomType.BEDROOM, x=2.0, y=24.0, width=21.0, length=14.0)
    ]
    layout = FloorPlanLayout(id="test_layout_valid", plot=plot, rooms=rooms)
    report = GeometryValidationEngine.validate_layout(layout)
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.hard_constraints_passed is True

def test_room_dimension_violation():
    """Verify that undersized rooms fail the minimum dimension check."""
    plot = make_test_plot()
    # Bedroom that is only 6ft x 6ft (minimum is 9ft x 9ft)
    rooms = [
        RoomGeometry(id="r_tiny", name="Tiny Bed", room_type=RoomType.BEDROOM, x=2.0, y=3.0, width=6.0, length=6.0)
    ]
    layout = FloorPlanLayout(id="test_tiny", plot=plot, rooms=rooms)
    issues = check_room_dimensions_and_proportions(layout)
    assert len(issues) >= 1
    assert any("Tiny Bed" in i.affected_rooms for i in issues)
    assert any("min_dimension" in i.constraint_type.value for i in issues)

def test_missing_required_room():
    """Verify that missing mandatory spaces are flagged."""
    plot = make_test_plot()
    rooms = [
        RoomGeometry(id="r1", name="Living", room_type=RoomType.LIVING_ROOM, x=2.0, y=3.0, width=12.0, length=12.0)
    ]
    layout = FloorPlanLayout(id="test_missing", plot=plot, rooms=rooms)
    reqs = [
        SpaceRequirement(id="req_bed", room_type="bedroom", label="Master Bedroom", quantity=1, is_mandatory=True),
        SpaceRequirement(id="req_kit", room_type="kitchen", label="Kitchen", quantity=1, is_mandatory=True)
    ]
    issues = check_required_rooms_completeness(layout, reqs)
    assert len(issues) == 2
    missing_labels = [i.affected_rooms[0] for i in issues]
    assert "Master Bedroom" in missing_labels
    assert "Kitchen" in missing_labels
