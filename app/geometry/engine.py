from datetime import datetime
from typing import List, Optional
from app.schemas.geometry import FloorPlanLayout
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import (
    ValidationReport, ValidationMetrics, SeverityLevel
)
from app.geometry.boundaries import check_plot_and_setback_boundaries
from app.geometry.overlaps import check_room_overlaps
from app.geometry.dimensions import check_room_dimensions_and_proportions
from app.geometry.accessibility import check_accessibility_and_openings
from app.geometry.adjacencies import check_adjacencies_and_privacy
from app.geometry.utilization import check_space_utilization_and_residuals
from app.geometry.completeness import check_required_rooms_completeness

class GeometryValidationEngine:
    """
    Authoritative Python Computational Geometry and Architectural Constraint Engine.
    Executes Shapely-backed spatial checks, boundary verifications, and architectural rules.
    """

    @classmethod
    def validate_layout(
        cls,
        layout: FloorPlanLayout,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None,
        constraints: Optional[ConfigurableConstraints] = None
    ) -> ValidationReport:
        # Enforce exact geometric area calculations on all rooms
        for r in layout.rooms:
            r.area = round(r.width * r.length, 2)

        enforce_setbacks = constraints.enforce_setbacks if constraints else True
        min_corridor_w = constraints.min_corridor_width if constraints else 3.0
        min_door_w = constraints.min_door_clearance if constraints else 2.8
        max_aspect = constraints.max_aspect_ratio if constraints else 2.4
        min_aspect = constraints.min_aspect_ratio if constraints else 0.42

        # 1. Boundary & Setbacks
        boundary_issues = check_plot_and_setback_boundaries(layout, enforce_setbacks=enforce_setbacks)

        # 2. Overlaps
        overlap_issues = check_room_overlaps(layout)

        # 3. Minimum & Maximum Dimensions & Proportions
        dimension_issues = check_room_dimensions_and_proportions(
            layout,
            max_aspect_ratio=max_aspect,
            min_aspect_ratio=min_aspect
        )

        # 4. Accessibility & Openings
        access_issues = check_accessibility_and_openings(
            layout,
            accessibility_mode=relationships.accessibility_mode if relationships else False,
            min_corridor_width=min_corridor_w,
            min_door_clearance=min_door_w
        )

        # 5. Adjacency & Privacy
        adjacency_issues = check_adjacencies_and_privacy(layout, relationships)

        # 6. Completeness
        completeness_issues = []
        if required_spaces:
            completeness_issues = check_required_rooms_completeness(layout, required_spaces)

        # 7. Space Utilization & Residuals
        util_issues, plot_area, built_up_area, carpet_area, circulation_area = check_space_utilization_and_residuals(layout)

        # Update layout metrics directly from real geometry
        layout.total_built_up_area = round(built_up_area, 2)
        layout.carpet_area = round(carpet_area, 2)
        layout.circulation_area = round(circulation_area, 2)
        layout.efficiency_ratio = round((carpet_area / built_up_area) if built_up_area > 0 else 0.0, 3)

        # Combine all issues
        all_issues = (
            boundary_issues
            + overlap_issues
            + dimension_issues
            + access_issues
            + adjacency_issues
            + completeness_issues
            + util_issues
        )

        error_count = sum(1 for i in all_issues if i.severity == SeverityLevel.ERROR)
        warning_count = sum(1 for i in all_issues if i.severity == SeverityLevel.WARNING)
        info_count = sum(1 for i in all_issues if i.severity == SeverityLevel.INFO)

        is_valid = (error_count == 0)
        coverage_ratio = round(built_up_area / plot_area, 3) if plot_area > 0 else 0.0

        metrics = ValidationMetrics(
            plot_area=round(plot_area, 1),
            buildable_area=round(layout.plot.buildable_width * layout.plot.buildable_length, 1),
            built_up_area=round(built_up_area, 1),
            carpet_area=round(carpet_area, 1),
            circulation_area=round(circulation_area, 1),
            ground_coverage_ratio=coverage_ratio,
            carpet_to_builtup_ratio=round((carpet_area / built_up_area) if built_up_area > 0 else 0.0, 3),
            room_count=len(layout.rooms),
            openings_count=len(layout.openings),
            hard_violations_count=error_count,
            warning_count=warning_count
        )

        if is_valid:
            summary = (
                f"Preliminary geometry validated successfully. All {len(layout.rooms)} spaces comply with "
                f"boundary setbacks and minimum dimensional codes ({warning_count} design warnings)."
            )
        else:
            summary = (
                f"Validation failed: {error_count} hard spatial conflicts detected. "
                f"Revisions required before architectural signoff."
            )

        return ValidationReport(
            is_valid=is_valid,
            hard_constraints_passed=is_valid,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            issues=all_issues,
            metrics=metrics,
            summary=summary,
            timestamp=datetime.utcnow().isoformat()
        )
