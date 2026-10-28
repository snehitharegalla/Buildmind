from fastapi import APIRouter
from app.schemas.ai import CopilotChatRequest, CopilotChatResponse
from app.ai.copilot import ArchitecturalCopilot

router = APIRouter(prefix="/copilot", tags=["Copilot"])

@router.post("/chat", response_model=CopilotChatResponse)
async def chat_with_copilot(request: CopilotChatRequest):
    """
    Context-aware AI Architectural Copilot endpoint.
    Processes user requests to resize rooms, analyze setbacks, explain validation errors,
    or introduce program spaces, returning structured modifications and preview diffs.
    """
    return await ArchitecturalCopilot.process_chat(request)
