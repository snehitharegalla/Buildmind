import pytest
from app.schemas.geometry import FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType
from app.geometry.boundaries import check_plot_and_setback_boundaries
from app.geometry.overlaps import check_room_overlaps

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

def test_plot_boundary_violation():
    """Verify that rooms extending past the property envelope are caught as hard errors."""
    plot = make_test_plot()
    # Room placed at x=20, width=10 (extends to x=30, past plot width 25)
    rooms = [
        RoomGeometry(id="r_exceeded", name="Extended Living", room_type=RoomType.LIVING_ROOM, x=20.0, y=5.0, width=10.0, length=12.0)
    ]
    layout = FloorPlanLayout(id="test_bound", plot=plot, rooms=rooms)
    issues = check_plot_and_setback_boundaries(layout, enforce_setbacks=False)
    assert len(issues) >= 1
    assert any("plot_boundary" in i.constraint_type.value for i in issues)
    assert "Extended Living" in issues[0].affected_rooms

def test_setback_violation():
    """Verify that rooms encroaching into statutory setbacks are caught."""
    plot = make_test_plot()
    # Left setback is 2.0 ft, but room starts at x=0.5 ft
    rooms = [
        RoomGeometry(id="r_setback", name="Porch Room", room_type=RoomType.LIVING_ROOM, x=0.5, y=5.0, width=10.0, length=12.0)
    ]
    layout = FloorPlanLayout(id="test_sb", plot=plot, rooms=rooms)
    issues = check_plot_and_setback_boundaries(layout, enforce_setbacks=True)
    assert len(issues) >= 1
    assert any("setback_violation" in i.constraint_type.value for i in issues)

def test_room_overlap_detection():
    """Verify that colliding room polygons are identified with intersection bounding boxes."""
    plot = make_test_plot()
    # Two rooms that heavily overlap in space
    rooms = [
        RoomGeometry(id="r1", name="Master Bed", room_type=RoomType.BEDROOM, x=2.0, y=3.0, width=12.0, length=12.0),
        RoomGeometry(id="r2", name="Living Hall", room_type=RoomType.LIVING_ROOM, x=8.0, y=3.0, width=12.0, length=12.0)
    ]
    layout = FloorPlanLayout(id="test_overlap", plot=plot, rooms=rooms)
    issues = check_room_overlaps(layout)
    assert len(issues) >= 1
    overlap_issue = issues[0]
    assert overlap_issue.constraint_type.value == "room_overlap"
    assert "Master Bed" in overlap_issue.affected_rooms
    assert "Living Hall" in overlap_issue.affected_rooms
    assert overlap_issue.bounding_box is not None
    assert overlap_issue.bounding_box.width > 0
