"""Helper utilities for subgraph execution patterns."""

import logging
from typing import Any

from langgraph.types import Command
from langgraph.types import interrupt as bubble_interrupt

logger = logging.getLogger(__name__)


def _unwrap_resume(answer: Any) -> Any:
    """
    If the runner sent {<interrupt_id>: payload}, return `payload`.
    Otherwise return `answer` unchanged.
    
    This handles the CLI pattern where it resumes with {interrupt_id: {"content": "..."}}.
    """
    if isinstance(answer, dict) and len(answer) == 1:
        # Heuristic: if the only value looks like the real payload (has 'content' or is str),
        # unwrap it. This matches the CLI's `{id: {"content": "..."}}` pattern.
        (_, payload), = answer.items()
        return payload
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
        
        # Handle tokens sequentially; subgraph emits at most one per round
        for intr in tokens:
            logger.debug(f"Subgraph interrupt round {rounds}; bubbling to parent")
            answer = bubble_interrupt(intr.value)         # pause → user → resume here
            payload = _unwrap_resume(answer)              # unwrap {id: payload} if needed
            result = await subgraph.ainvoke(
                Command(resume=payload),
                config=subgraph_config
            )
    
    if rounds:
        logger.info(f"Subgraph completed after {rounds} HITL round(s)")
    return result