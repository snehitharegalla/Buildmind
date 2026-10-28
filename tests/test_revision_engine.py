import pytest
from app.schemas.geometry import FloorPlanLayout, PlotGeometry, RoomGeometry, RoomType
from app.schemas.project import ConfigurableConstraints
from app.geometry.engine import GeometryValidationEngine
from app.ai.revision_engine import LayoutRevisionEngine

def test_automatic_revision_repair():
    """Verify that the revision engine repairs an encroached boundary layout into compliance."""
    plot = PlotGeometry(
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
    # Flawed layout: Room placed at x=1.0 (violating 2.0 ft setback) and extending to x=24.5 (violating right 2.0 setback)
    flawed_rooms = [
        RoomGeometry(id="r_err", name="Encroaching Living", room_type=RoomType.LIVING_ROOM, x=1.0, y=2.0, width=23.5, length=12.0)
    ]
    layout = FloorPlanLayout(id="test_flawed", plot=plot, rooms=flawed_rooms)
    
    # 1. First validation shows failure
    val_before = GeometryValidationEngine.validate_layout(layout)
    assert val_before.is_valid is False
    assert val_before.error_count > 0

    # 2. Run automated repair
    revised_layout, changes = LayoutRevisionEngine.repair_layout(
        layout=layout,
        validation=val_before,
        constraints=ConfigurableConstraints(),
        required_spaces=[]
    )
    assert len(changes) > 0

    # 3. Re-validate repaired layout
    val_after = GeometryValidationEngine.validate_layout(revised_layout)
    # Hard boundary errors must be resolved
    boundary_errors_after = [i for i in val_after.issues if i.constraint_type.value in ["plot_boundary", "setback_violation"]]
    assert len(boundary_errors_after) == 0
