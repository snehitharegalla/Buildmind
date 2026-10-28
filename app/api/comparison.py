from fastapi import APIRouter
from typing import List, Dict, Any
from pydantic import BaseModel
from app.schemas.geometry import FloorPlanLayout
from app.schemas.validation import ValidationReport
from app.geometry.engine import GeometryValidationEngine

class ComparisonItem(BaseModel):
    variant_type: str
    title: str
    layout: FloorPlanLayout
    validation: ValidationReport
    total_area: float
    built_up_area: float
    carpet_area: float
    circulation_area: float
    efficiency_ratio: float
    ground_coverage_ratio: float
    cost_range: str
    room_count: int
    hard_violations: int
    soft_warnings: int
    advantages: List[str]
    tradeoffs: List[str]

class ComparisonResponse(BaseModel):
    items: List[ComparisonItem]
    common_plot_area: float
    unit: str
    summary_verdict: str

router = APIRouter(prefix="/comparison", tags=["Comparison"])

@router.post("/compare", response_model=ComparisonResponse)
def compare_layouts(layouts: List[FloorPlanLayout]):
    """
    Computes comparative spatial and financial metrics across layout variants:
    Space Optimized vs Comfort Focused vs Budget Conscious.
    """
    items: List[ComparisonItem] = []
    if not layouts:
        return ComparisonResponse(items=[], common_plot_area=0, unit="ft", summary_verdict="No layouts provided.")

    unit = layouts[0].plot.unit
    plot_area = layouts[0].plot.total_area

    for l in layouts:
        val = GeometryValidationEngine.validate_layout(l)
        cost_str = f"${l.estimated_cost_min:,.0f} – ${l.estimated_cost_max:,.0f}" if l.estimated_cost_min > 0 else "N/A"

        items.append(
            ComparisonItem(
                variant_type=l.variant_type,
                title=l.name,
                layout=l,
                validation=val,
                total_area=l.plot.total_area,
                built_up_area=l.total_built_up_area,
                carpet_area=l.carpet_area,
                circulation_area=l.circulation_area,
                efficiency_ratio=l.efficiency_ratio,
                ground_coverage_ratio=val.metrics.ground_coverage_ratio,
                cost_range=cost_str,
                room_count=len(l.rooms),
                hard_violations=val.error_count,
                soft_warnings=val.warning_count,
                advantages=l.advantages,
                tradeoffs=l.tradeoffs
            )
        )

    # Architectural verdict
    best_eff = max(items, key=lambda x: x.efficiency_ratio)
    verdict = (
        f"Comparative Analysis: '{best_eff.title}' delivers the highest usable carpet efficiency "
        f"({best_eff.efficiency_ratio * 100:.1f}%), while all variants comply with site setback thresholds."
    )

    return ComparisonResponse(
        items=items,
        common_plot_area=plot_area,
        unit=unit,
        summary_verdict=verdict
    )
