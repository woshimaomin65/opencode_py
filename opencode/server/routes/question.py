"""
Question routes for OpenCode server.

Provides API endpoints for question management:
- List pending questions
- Reply to question requests
- Reject question requests
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question", tags=["question"])


class QuestionReplyRequest(BaseModel):
    """Request body for question reply."""
    answers: Dict[str, str]


from pydantic import BaseModel


# Placeholder for Question module (needs to be implemented)
class QuestionManager:
    """Manager for AI questions."""
    
    _pending_questions: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    async def list(cls) -> List[Dict[str, Any]]:
        """List all pending questions."""
        return list(cls._pending_questions.values())
    
    @classmethod
    async def reply(cls, request_id: str, answers: Dict[str, str]) -> None:
        """Reply to a question."""
        if request_id not in cls._pending_questions:
            raise ValueError(f"Question {request_id} not found")
        
        # Store the reply and notify waiting processes
        cls._pending_questions[request_id]["answers"] = answers
        cls._pending_questions[request_id]["status"] = "answered"
    
    @classmethod
    async def reject(cls, request_id: str) -> None:
        """Reject a question."""
        if request_id not in cls._pending_questions:
            raise ValueError(f"Question {request_id} not found")
        
        cls._pending_questions[request_id]["status"] = "rejected"
    
    @classmethod
    async def add_question(cls, request_id: str, question: Dict[str, Any]) -> None:
        """Add a new pending question."""
        cls._pending_questions[request_id] = {
            "request_id": request_id,
            **question,
            "status": "pending",
        }


# Singleton instance
_question_manager = QuestionManager()


def get_question_manager() -> QuestionManager:
    """Get the question manager instance."""
    return _question_manager


# GET /question/ - List pending questions
@router.get("/")
async def list_questions():
    """
    List pending questions.
    
    Get all pending question requests across all sessions.
    """
    try:
        manager = get_question_manager()
        questions = await manager.list()
        return questions
    except Exception as e:
        logger.error(f"Error listing questions: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /question/{requestID}/reply - Reply to question request
@router.post("/{request_id}/reply")
async def reply_to_question(
    request_id: str = Path(..., description="Question request ID"),
    body: QuestionReplyRequest = None,
):
    """
    Reply to question request.
    
    Provide answers to a question request from the AI assistant.
    """
    try:
        manager = get_question_manager()
        await manager.reply(
            request_id=request_id,
            answers=body.answers,
        )
        return True
    except Exception as e:
        logger.error(f"Error replying to question {request_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Question not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /question/{requestID}/reject - Reject question request
@router.post("/{request_id}/reject")
async def reject_question(request_id: str = Path(..., description="Question request ID")):
    """
    Reject question request.
    
    Reject a question request from the AI assistant.
    """
    try:
        manager = get_question_manager()
        await manager.reject(request_id)
        return True
    except Exception as e:
        logger.error(f"Error rejecting question {request_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Question not found")
        raise HTTPException(status_code=400, detail=str(e))
