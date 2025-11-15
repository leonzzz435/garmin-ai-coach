import asyncio
import logging
from collections.abc import Callable

from langgraph.checkpoint.serde.types import INTERRUPT
from langgraph.types import Command

logger = logging.getLogger(__name__)


class InterruptHandler:

    @staticmethod
    def extract_all_interrupts(result: dict) -> list[tuple[str, dict]]:

        payload = result.get("__interrupt__")
        if not payload:
            return []

        if not isinstance(payload, list):
            payload = [payload]

        interrupts = []
        for intr in payload:
            interrupt_id = (
                getattr(intr, "interrupt_id", None) or
                getattr(intr, "id", None) or
                (intr.get("id") if isinstance(intr, dict) else None)
            )
            value = getattr(intr, "value", intr)
            if isinstance(value, dict):
                interrupts.append((interrupt_id, value))
        return interrupts

    @staticmethod
    def format_question(payload: dict, index: int | str | None = None) -> str:
        message = payload.get("message", "Message not found")
        message_type = payload.get("message_type", "question")
        context = payload.get("context", "")
        agent = payload.get("agent", "Agent")

        type_indicator = f"[{message_type.upper()}]" if message_type != "question" else ""
        
        header = (
            f"{'Question ' + str(index) if index is not None else 'AGENT COMMUNICATION'} "
            f"{f'[{agent.upper()}]' if agent and agent != 'Unknown Agent' else ''} "
            f"{type_indicator}"
        ).strip()

        return f"{header}\n{context}\n\n{message}" if context else f"{header}\n\n{message}"


async def run_workflow_with_hitl(
    workflow_app,
    initial_state: dict,
    config: dict,
    prompt_callback: Callable[[str], str],
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    
    state = initial_state
    final_state = None

    while True:
        try:
            # Track if we just resumed from interrupts
            is_resume = isinstance(state, Command) and state.resume
            
            # Stream with "updates" mode to capture __interrupt__ events properly
            # Also include "values" to get final state
            # NOTE: NOT using subgraphs=True - it causes namespace confusion
            interrupts = []
            try:
                async for mode, chunk in workflow_app.astream(
                    state,
                    config=config,
                    stream_mode=["values", "updates"],
                ):
                    if mode == "values":
                        final_state = chunk
                    elif mode == "updates" and isinstance(chunk, dict) and INTERRUPT in chunk:
                        # Fresh interrupts from stream - this is the source of truth
                        interrupt_tokens = chunk[INTERRUPT]
                        if not isinstance(interrupt_tokens, (list, tuple)):
                            interrupt_tokens = [interrupt_tokens]
                        
                        for intr in interrupt_tokens:
                            # Get LangGraph token id (unique per emission) and the stable interrupt_id (may repeat per node)
                            token_id = getattr(intr, "id", None) or getattr(intr, "interrupt_id", None)
                            interrupt_attr = getattr(intr, "interrupt_id", None)
                            value = getattr(intr, "value", intr)
                            
                            if isinstance(value, dict):
                                # Use tool_call_id for display if available; always route by token_id
                                display_id = value.get("tool_call_id") or interrupt_attr or token_id
                                interrupts.append((display_id, token_id, value))
                                
                                question_preview = value.get("message", "")[:100]
                                logger.critical(
                                    f"STREAM_INTERRUPT | "
                                    f"display_id={display_id} | "
                                    f"token_id={token_id} | "
                                    f"interrupt_id={interrupt_attr} | "
                                    f"tool_call_id={value.get('tool_call_id')} | "
                                    f"question='{question_preview}...'"
                                )
            except ValueError as e:
                logger.error(f"Stream iteration error: {e}, falling back to snapshot-based detection")
                # Fallback: try to get state and check for interrupts
                snapshot = workflow_app.get_state(config)
                final_state = snapshot.values if hasattr(snapshot, "values") else {}
            
            # Get snapshot for diagnostics only (not for interrupt IDs)
            snapshot = workflow_app.get_state(config)
            
            # Post-resume state verification
            if is_resume:
                message_count = len(snapshot.values.get("messages", [])) if hasattr(snapshot, "values") else 0
                logger.critical(
                    f"POST_RESUME_STATE | "
                    f"next_nodes={snapshot.next} | "
                    f"message_count={message_count} | "
                    f"pending_tasks={len(snapshot.tasks) if snapshot.tasks else 0}"
                )
            
            # Calculate message count for diagnostics
            state_message_count = len(snapshot.values.get("messages", [])) if hasattr(snapshot, "values") else 0
            
            logger.critical(
                f"SNAPSHOT_STATE | "
                f"next_nodes={snapshot.next} | "
                f"task_count={len(snapshot.tasks) if snapshot.tasks else 0} | "
                f"state_message_count={state_message_count} | "
                f"interrupts_from_stream={len(interrupts)}"
            )
            
            logger.critical(f"INTERRUPTS_DETECTED: count={len(interrupts)}")
            
            if interrupts:
                    # Log each interrupt for diagnostic purposes
                    for idx, (display_id, langgraph_id, payload) in enumerate(interrupts, start=1):
                        q_preview = str(payload.get("message", str(payload)))[:40] if isinstance(payload, dict) else str(payload)[:40]
                        logger.critical(f"  INTERRUPT_{idx}: id={display_id}, langgraph_id={langgraph_id}, question='{q_preview}...'")
                    
                    # Batch-resume: collect answers for ALL interrupts in one go
                    if len(interrupts) > 1:
                        logger.info(f"Found {len(interrupts)} interrupts - collecting all answers")
                        if progress_callback:
                            progress_callback(f"\n{'=' * 70}")
                            progress_callback(f"🤖 {len(interrupts)} AGENT QUESTIONS (Sequential)")
                            progress_callback(f"{'=' * 70}\n")
                    
                    # Collect all answers
                    resumes = {}
                    for idx, (display_id, langgraph_id, payload) in enumerate(interrupts, start=1):
                        # Show each question
                        if len(interrupts) > 1:
                            question = InterruptHandler.format_question(
                                payload,
                                index=f"{idx}/{len(interrupts)}"
                            )
                        else:
                            question = InterruptHandler.format_question(payload)

                        if progress_callback:
                            progress_callback(question)
                        
                        user_response = prompt_callback(
                            "\n👤 Your answer: " if len(interrupts) == 1
                            else f"\n👤 Answer {idx}/{len(interrupts)}: "
                        )

                        if user_response.lower() in ["quit", "exit", "cancel"]:
                            logger.info("Workflow cancelled by user during HITL interaction")
                            return {**final_state, "cancelled": True}

                        # Use provided answer or sensible default
                        answer = (user_response or "").strip() or "Proceed with your analysis; no special focus needed."
                        
                        # Enhanced pairing diagnostics
                        question_preview = (
                            payload.get("message", "")[:100]
                            if isinstance(payload, dict)
                            else str(payload)[:100]
                        )
                        logger.critical(
                            f"RESUME_PAIRING | "
                            f"display_id={display_id} | "
                            f"langgraph_id={langgraph_id} | "
                            f"tool_call_id={payload.get('tool_call_id')} | "
                            f"question='{question_preview}...' | "
                            f"answer='{answer[:100]}...'"
                        )
                        
                        # IMPORTANT: Key resumes by LangGraph's interrupt id for correct routing
                        # AND include tool_call_id inside the value so the subgraph can extract its own answer.
                        tcid = payload.get("tool_call_id")
                        resumes[langgraph_id] = ({tcid: {"content": answer}} if tcid else {"content": answer})
                    
                    # Resume with ALL answers at once
                    # If there's only one interrupt, resume with the direct payload.
                    # Some LangGraph backends reuse the same top-level token id across sequential interrupts,
                    # so keying by id can cause stale routing. Direct payload avoids off-by-one pairing.
                    if len(resumes) == 1:
                        only_key, only_value = next(iter(resumes.items()))
                        logger.critical(
                            f"RESUME_COMMAND_DIRECT | "
                            f"key={only_key} | "
                            f"payload_type={type(only_value).__name__} | "
                            f"payload_preview={str(only_value)[:200]}"
                        )
                        state = Command(resume=only_value)
                    else:
                        logger.critical(
                            f"RESUME_COMMAND | "
                            f"resume_count={len(resumes)} | "
                            f"interrupt_ids={list(resumes.keys())} | "
                            f"full_resume_dict={resumes}"
                        )
                        state = Command(resume=resumes)
                    continue
            
            # No interrupts - check if workflow has more work
            if snapshot.next:
                logger.debug("Graph has next nodes scheduled")
                continue
            
            # No interrupts, no next nodes - workflow is complete
            if progress_callback:
                progress_callback("✅ Workflow completed")

            return final_state

        except KeyboardInterrupt:
            logger.info("Workflow interrupted by user (Ctrl+C)")
            raise
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            raise