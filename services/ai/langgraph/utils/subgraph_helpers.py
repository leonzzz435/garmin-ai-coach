"""Helper utilities for subgraph execution patterns."""

import logging
from typing import Any

from langgraph.types import Command
from langgraph.types import interrupt as bubble_interrupt

logger = logging.getLogger(__name__)


def _unwrap_resume(answer: Any, interrupt_id: str | None = None) -> Any:
    """
    If the runner sent {<interrupt_id>: payload}, return `payload` for the matching ID.
    Otherwise return `answer` unchanged.
    
    This handles the CLI pattern where it resumes with {interrupt_id: {"content": "..."}}.
    
    Args:
        answer: The resume value from LangGraph (may be dict or direct value)
        interrupt_id: The current interrupt_id to extract answer for
    
    Returns:
        The unwrapped answer content
    """
    logger.critical(
        f"UNWRAP_RESUME_START | "
        f"interrupt_id={interrupt_id} | "
        f"answer_type={type(answer).__name__} | "
        f"answer_keys={list(answer.keys()) if isinstance(answer, dict) else 'N/A'} | "
        f"answer_preview={str(answer)[:200]}"
    )
    
    # If answer is a dict with multiple interrupt answers, extract the one for this ID
    if isinstance(answer, dict) and interrupt_id and interrupt_id in answer:
        extracted = answer[interrupt_id]
        logger.critical(
            f"UNWRAP_RESUME_MATCHED | "
            f"interrupt_id={interrupt_id} | "
            f"extracted_type={type(extracted).__name__} | "
            f"extracted_value={str(extracted)[:100]}"
        )
        return extracted
    
    # Legacy: if single-item dict, unwrap it
    if isinstance(answer, dict) and len(answer) == 1:
        (key, payload), = answer.items()
        logger.critical(
            f"UNWRAP_RESUME_SINGLE_DICT | "
            f"dict_key={key} | "
            f"interrupt_id={interrupt_id} | "
            f"payload_type={type(payload).__name__} | "
            f"payload_value={str(payload)[:100]}"
        )
        return payload
    
    logger.critical(
        f"UNWRAP_RESUME_PASSTHROUGH | "
        f"interrupt_id={interrupt_id} | "
        f"returning_as_is={str(answer)[:100]}"
    )
    return answer


async def run_subgraph_until_done(
    subgraph,
    first_input: dict[str, Any] | None,
    subgraph_config: dict[str, Any],
    max_rounds: int = 16,
) -> dict[str, Any]:
    """
    Call subgraph, bubbling every HITL round until it finishes.
    Returns the final subgraph result (with messages).
    
    This handles multiple sequential interrupts (e.g., follow-up questions).
    Each interrupt is bubbled to the parent workflow, which collects user input,
    then resumes the subgraph with the answer.
    
    Args:
        subgraph: The compiled subgraph to execute
        first_input: Initial input state (or None to resume existing thread)
        subgraph_config: Config with thread_id for checkpointing
        max_rounds: Safety limit on interrupt rounds (default 16)
    
    Returns:
        Final result dict with completed messages
    
    Raises:
        RuntimeError: If max_rounds exceeded (likely infinite loop)
    """
    result = await subgraph.ainvoke(first_input, config=subgraph_config)
    
    rounds = 0
    while result and result.get("__interrupt__"):
        rounds += 1
        if rounds > max_rounds:
            raise RuntimeError(
                f"Exceeded {max_rounds} HITL rounds in subgraph (possible loop)."
            )
        
        tokens = result["__interrupt__"]
        if not isinstance(tokens, list):
            tokens = [tokens]
        
        logger.critical(
            f"SUBGRAPH_INTERRUPT_DETECTED | "
            f"round={rounds} | "
            f"token_count={len(tokens)}"
        )
        
        # Handle tokens sequentially; subgraph emits at most one per round
        for token_idx, intr in enumerate(tokens):
            interrupt_id = getattr(intr, "interrupt_id", None) or getattr(intr, "id", None)
            question_preview = (
                intr.value.get("message", "")[:100]
                if isinstance(intr.value, dict)
                else str(intr.value)[:100]
            )
            
            logger.critical(
                f"SUBGRAPH_BUBBLE_INTERRUPT | "
                f"round={rounds} | "
                f"token_idx={token_idx} | "
                f"interrupt_id={interrupt_id} | "
                f"question='{question_preview}...'"
            )
            
            answer = bubble_interrupt(intr.value)         # pause → user → resume here
            
            logger.critical(
                f"SUBGRAPH_BUBBLE_RESUMED | "
                f"round={rounds} | "
                f"interrupt_id={interrupt_id} | "
                f"answer_type={type(answer).__name__} | "
                f"answer_keys={list(answer.keys()) if isinstance(answer, dict) else 'N/A'} | "
                f"answer_preview={str(answer)[:200]}"
            )
            
            # Pass the answer directly - LangGraph will route it internally
            logger.critical(
                f"SUBGRAPH_RESUME_PAYLOAD | "
                f"round={rounds} | "
                f"interrupt_id={interrupt_id} | "
                f"resume_type={type(answer).__name__} | "
                f"resume_keys={list(answer.keys()) if isinstance(answer, dict) else 'N/A'} | "
                f"resume_preview={str(answer)[:200]}"
            )
            
            result = await subgraph.ainvoke(
                Command(resume=answer),
                config=subgraph_config
            )
    
    if rounds:
        logger.critical(f"SUBGRAPH_COMPLETED | total_rounds={rounds}")
    return result