import copy
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.schemas.geometry import FloorPlanLayout, PlotGeometry
from app.schemas.project import SpaceRequirement, DesignRelationships, ProjectPreferences, ConfigurableConstraints
from app.schemas.validation import ValidationReport
from app.schemas.ai import GenerationResult, LayoutCandidate
from app.geometry.engine import GeometryValidationEngine
from app.geometry.quality import LayoutQualityEvaluator
from app.ai.provider import get_llm_provider
from app.ai.revision_engine import LayoutRevisionEngine

logger = logging.getLogger(__name__)

class LayoutGenerationPipeline:
    """
    Complete AI architectural layout generation and iterative revision pipeline.
    Orchestrates LLM/solver proposals, authoritative Shapely geometric checks,
    and automatic multi-cycle constraint repair.
    """

    @classmethod
    async def generate_and_validate_all(
        cls,
        project_id: str,
        plot: PlotGeometry,
        spaces: List[SpaceRequirement],
        relationships: Optional[DesignRelationships] = None,
        preferences: Optional[ProjectPreferences] = None,
        constraints: Optional[ConfigurableConstraints] = None,
        variants: Optional[List[str]] = None,
        max_revisions: int = 3
    ) -> GenerationResult:
        if not variants:
            variants = ["space_optimized", "comfort_focused", "budget_conscious"]

        provider = get_llm_provider()
        candidates: List[LayoutCandidate] = []
        revision_timeline: List[Dict[str, Any]] = []

        for variant_type in variants:
            logger.info(f"Generating architectural proposal for variant: {variant_type}")

            # Step 1: Initial layout generation
            layout = await provider.generate_layout_proposal(
                variant_type=variant_type,
                plot=plot,
                spaces=spaces,
                relationships=relationships,
                preferences=preferences
            )

            # Step 2: Authoritative Python Geometry Validation
            report = GeometryValidationEngine.validate_layout(
                layout=layout,
                required_spaces=spaces,
                relationships=relationships,
                constraints=constraints
            )

            # Log initial validation step in timeline
            revision_timeline.append({
                "variant": variant_type,
                "iteration": 0,
                "stage": "initial_validation",
                "error_count": report.error_count,
                "warning_count": report.warning_count,
                "summary": report.summary,
                "passed": report.is_valid
            })

            # Step 3: Iterative Revision Loop if conflicts detected
            curr_iteration = 0
            while not report.is_valid and curr_iteration < max_revisions:
                curr_iteration += 1
                logger.info(f"Constraint conflicts in {variant_type}: Running revision iteration {curr_iteration}")

                revised_layout, changes_made = LayoutRevisionEngine.repair_layout(
                    layout=layout,
                    validation=report,
                    constraints=constraints or ConfigurableConstraints(),
                    required_spaces=spaces
                )

                # Revalidate revised layout
                new_report = GeometryValidationEngine.validate_layout(
                    layout=revised_layout,
                    required_spaces=spaces,
                    relationships=relationships,
                    constraints=constraints
                )

                revision_timeline.append({
                    "variant": variant_type,
                    "iteration": curr_iteration,
                    "stage": "automated_repair",
                    "changes_made": changes_made,
                    "error_count_before": report.error_count,
                    "error_count_after": new_report.error_count,
                    "summary": new_report.summary,
                    "passed": new_report.is_valid
                })

                layout = revised_layout
                report = new_report

            # Step 4: Evaluate Layout Quality & Privacy
            quality = LayoutQualityEvaluator.evaluate_layout(
                layout=layout,
                relationships=relationships,
                required_spaces=spaces
            )

            candidates.append(
                LayoutCandidate(
                    variant_type=variant_type,
                    title=f"{variant_type.replace('_', ' ').title()} Layout",
                    layout=layout,
                    validation=report,
                    generation_mode=provider.name,
                    design_notes=f"{layout.summary_notes} | Quality Score: {quality['overall_quality_score']}/100 (Privacy: {quality['privacy_score']}, Daylight: {quality['daylight_score']})"
                )
            )

        # Rank candidates strictly according to architectural priority:
        # 1. Satisfy hard constraints (0 errors)
        # 2. Minimize remaining validation warnings
        # 3. Maximize overall architectural quality score
        def candidate_rank_key(cand: LayoutCandidate):
            q = LayoutQualityEvaluator.evaluate_layout(cand.layout, relationships=relationships, required_spaces=spaces)
            hard_pass = 1 if (cand.validation.is_valid and q["hard_constraints_passed"]) else 0
            err_count = cand.validation.error_count
            quality_score = q["overall_quality_score"]
            return (-hard_pass, err_count, -quality_score)

        candidates.sort(key=candidate_rank_key)

        # Primary layout selection: Top-ranked candidate
        primary_candidate = candidates[0] if candidates else None
        primary_layout = primary_candidate.layout
        primary_validation = primary_candidate.validation

        return GenerationResult(
            project_id=project_id,
            candidates=candidates,
            primary_layout=primary_layout,
            primary_validation=primary_validation,
            revision_timeline=revision_timeline,
            generation_mode=provider.name,
            provider_label=provider.name,
            is_demo_mode=provider.is_demo
        )
