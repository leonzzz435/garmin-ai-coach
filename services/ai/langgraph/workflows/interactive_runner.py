import logging
from collections.abc import Callable

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
            async for chunk in workflow_app.astream(state, config=config, stream_mode="values"):
                final_state = chunk
            
            snapshot = workflow_app.get_state(config)
            
            logger.debug(f"Snapshot next: {snapshot.next}")
            logger.debug(f"Snapshot tasks: {len(snapshot.tasks) if snapshot.tasks else 0}")
            
            if snapshot.next:
                interrupts = []
                for task in snapshot.tasks:
                    logger.debug(f"Task {task.id}: interrupts={hasattr(task, 'interrupts')}")
                    if hasattr(task, "interrupts") and task.interrupts:
                        for intr in task.interrupts:
                            # Use real interrupt id from token
                            iid = getattr(intr, "interrupt_id", None) or getattr(intr, "id", None)
                            interrupts.append((iid, intr.value))
                
                logger.info(f"Found {len(interrupts)} interrupts to handle")
                
                if interrupts:
                    if len(interrupts) > 1:
                        logger.info(f"Found {len(interrupts)} interrupts - will handle sequentially")
                        if progress_callback:
                            progress_callback(f"\n{'=' * 70}")
                            progress_callback(f"🤖 {len(interrupts)} AGENT QUESTIONS (Sequential)")
                            progress_callback(f"{'=' * 70}\n")
                    
                    interrupt_id, payload = interrupts[0]
                    
                    if len(interrupts) > 1:
                        question = InterruptHandler.format_question(
                            payload,
                            index=f"1/{len(interrupts)}"
                        )
                    else:
                        question = InterruptHandler.format_question(payload)

                    if progress_callback:
                        progress_callback(question)
                    
                    user_response = prompt_callback(
                        "\n👤 Your answer: " if len(interrupts) == 1
                        else f"\n👤 Answer 1/{len(interrupts)}: "
                    )

                    if user_response.lower() in ["quit", "exit", "cancel"]:
                        logger.info("Workflow cancelled by user during HITL interaction")
                        return {**final_state, "cancelled": True}

                    state = Command(resume={interrupt_id: {"content": user_response}})
                    continue
            
            if progress_callback:
                progress_callback("✅ Workflow completed")

            return final_state

        except KeyboardInterrupt:
            logger.info("Workflow interrupted by user (Ctrl+C)")
            raise
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            raise