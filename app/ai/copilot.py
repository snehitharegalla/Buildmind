import uuid
from typing import Dict, Any, Optional
from app.schemas.geometry import FloorPlanLayout, PlotGeometry
from app.schemas.ai import (
    CopilotChatRequest, CopilotChatResponse, ProposedModification, ProposedDiff
)
from app.schemas.validation import ValidationReport
from app.geometry.engine import GeometryValidationEngine
from app.ai.provider import get_llm_provider

class ArchitecturalCopilot:
    """
    Context-aware AI Architectural Design Copilot.
    Interprets natural language design modifications, explains spatial validation results,
    and returns structured geometric proposals with interactive confirmation diffs.
    """

    @classmethod
    async def process_chat(
        cls,
        request: CopilotChatRequest
    ) -> CopilotChatResponse:
        provider = get_llm_provider()
        layout = request.current_layout

        if not layout:
            return CopilotChatResponse(
                message_id=str(uuid.uuid4()),
                response_text="No active floor plan layout loaded in the workspace.",
                provider_label=provider.name
            )

        # 1. Run baseline validation
        base_val = GeometryValidationEngine.validate_layout(layout)
        val_summary = f"Hard Errors: {base_val.error_count}, Warnings: {base_val.warning_count}. {base_val.summary}"

        # 2. Query provider
        copilot_result = await provider.chat_copilot(
            user_message=request.message,
            current_layout=layout,
            plot=layout.plot,
            validation_summary=val_summary
        )

        reply_text = copilot_result.get("reply_text", "")
        action_type = copilot_result.get("action_type", "general_query")
        raw_diffs = copilot_result.get("diffs", [])
        modified_layout = copilot_result.get("modified_layout")

        proposed_mod = None
        new_val = None

        if modified_layout and raw_diffs:
            # Revalidate modified layout to preview changes
            new_val = GeometryValidationEngine.validate_layout(modified_layout)
            conflicts = [i.explanation for i in new_val.issues if i.severity.value == "error"]

            diff_items = [
                ProposedDiff(
                    action=d["action"],
                    target_room_name=d.get("target_room_name"),
                    target_room_id=d.get("target_room_id"),
                    old_value=d.get("old_value"),
                    new_value=d.get("new_value"),
                    description=d.get("description", "")
                )
                for d in raw_diffs
            ]

            proposed_mod = ProposedModification(
                id=str(uuid.uuid4()),
                action_type=action_type,
                title=f"Architectural Modification Proposal: {action_type.replace('_', ' ').title()}",
                explanation=reply_text,
                diffs=diff_items,
                preview_layout=modified_layout,
                preview_validation=new_val,
                conflicts_detected=conflicts
            )

        return CopilotChatResponse(
            message_id=str(uuid.uuid4()),
            response_text=reply_text,
            proposed_modification=proposed_mod,
            applied_layout=None, # Returned as proposal first, client approves
            validation=new_val or base_val,
            provider_label=provider.name
        )
