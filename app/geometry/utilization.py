from typing import List, Tuple
from shapely.geometry import box, MultiPolygon
from shapely.ops import unary_union
from app.schemas.geometry import FloorPlanLayout
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

def check_space_utilization_and_residuals(
    layout: FloorPlanLayout
) -> Tuple[List[ValidationIssue], float, float, float, float]:
    issues: List[ValidationIssue] = []
    unit = layout.plot.unit
    plot = layout.plot

    # Plot polygon
    plot_poly = box(0, 0, plot.width, plot.length)
    plot_area = plot.width * plot.length

    # Union of all room polygons
    room_polys = [box(r.x, r.y, r.x + r.width, r.y + r.length) for r in layout.rooms if r.width > 0 and r.length > 0]
    
    if not room_polys:
        return issues, plot_area, 0.0, 0.0, 0.0

    union_rooms = unary_union(room_polys)
    built_up_area = union_rooms.area

    # Calculate carpet area (sum of individual room interior areas)
    carpet_area = sum(r.width * r.length for r in layout.rooms)
    
    # Circulation estimated: corridors or hallways
    circulation_area = sum(
        r.width * r.length for r in layout.rooms 
        if getattr(r.room_type, "value", str(r.room_type)) in ["corridor", "foyer"]
    )

    coverage_ratio = built_up_area / plot_area if plot_area > 0 else 0.0
    efficiency_ratio = carpet_area / built_up_area if built_up_area > 0 else 0.0

    # 1. Ground Coverage Limits Check
    if coverage_ratio > 0.82:
        issues.append(
            ValidationIssue(
                id="coverage_high",
                constraint_type=ConstraintCategory.SPACE_UTILIZATION,
                severity=SeverityLevel.WARNING,
                affected_rooms=[],
                affected_element_ids=[],
                measured_value=f"Ground Coverage {coverage_ratio * 100:.1f}% ({built_up_area:.1f} sq {unit})",
                expected_condition="<= 80% maximum site coverage ratio",
                explanation=f"Excessive ground coverage leaves insufficient open space for drainage, landscaping, or parking.",
                suggested_correction="Reduce total footprint or consider moving spaces to a second level.",
                bounding_box=None
            )
        )
    elif coverage_ratio < 0.25:
        issues.append(
            ValidationIssue(
                id="coverage_low",
                constraint_type=ConstraintCategory.SPACE_UTILIZATION,
                severity=SeverityLevel.INFO,
                affected_rooms=[],
                affected_element_ids=[],
                measured_value=f"Ground Coverage {coverage_ratio * 100:.1f}%",
                expected_condition="35% - 75% optimal site utilization",
                explanation="The plot is significantly underutilized for a single-story program.",
                suggested_correction="Consider expanding room dimensions or incorporating garden courtyards.",
                bounding_box=None
            )
        )

    # 2. Residual Slivers / Unusable Dead Space Check
    # Difference between plot and rooms
    unbuilt_space = plot_poly.difference(union_rooms)
    if isinstance(unbuilt_space, MultiPolygon):
        parts = list(unbuilt_space.geoms)
    else:
        parts = [unbuilt_space]

    for idx, geom in enumerate(parts):
        minx, miny, maxx, maxy = geom.bounds
        w = maxx - minx
        l = maxy - miny
        area = geom.area
        # If there's an internal enclosed gap or narrow dead sliver
        if 0.5 < w < 2.5 and 0.5 < l < 3.0 and area < 10.0:
            issues.append(
                ValidationIssue(
                    id=f"residual_sliver_{idx}",
                    constraint_type=ConstraintCategory.RESIDUAL_SPACE,
                    severity=SeverityLevel.WARNING,
                    affected_rooms=[],
                    affected_element_ids=[],
                    measured_value=f"Unusable void: {w:.1f} × {l:.1f} {unit} ({area:.1f} sq {unit})",
                    expected_condition="Seamless wall alignment without dead gaps",
                    explanation="A narrow, inaccessible void has formed between room boundaries.",
                    suggested_correction="Align adjoining walls flush to eliminate the dead pocket and reclaim floor area.",
                    bounding_box=BoundingBox(x=minx, y=miny, width=w, length=l)
                )
            )

    return issues, plot_area, built_up_area, carpet_area, circulation_area
