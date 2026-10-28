import copy
from typing import List, Dict, Any, Tuple
from app.schemas.geometry import FloorPlanLayout, RoomGeometry
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import ValidationReport, SeverityLevel, ConstraintCategory
from app.geometry.auto_fix import AutoFixEngine

class LayoutRevisionEngine:
    """
    Automated architectural constraint repair and revision loop.
    Leverages AutoFixEngine's non-regression candidate evaluation
    to iteratively repair validation issues without degrading the layout.
    """

    @classmethod
    def repair_layout(
        cls,
        layout: FloorPlanLayout,
        validation: ValidationReport,
        constraints: ConfigurableConstraints,
        required_spaces: List[SpaceRequirement],
        relationships: DesignRelationships = None
    ) -> Tuple[FloorPlanLayout, List[str]]:
        result = AutoFixEngine.auto_fix_all(
            layout=layout,
            constraints=constraints,
            required_spaces=required_spaces,
            relationships=relationships,
            max_cycles=3
        )
        changes = [d.get("description", str(d)) for d in result.get("revisions_applied", [])]
        return result["fixed_layout"], changes
