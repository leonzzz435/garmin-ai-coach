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
    def format_question(payload: dict, index: int | None = None) -> str:
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

    while True:
        try:
            result = await workflow_app.ainvoke(state, config=config)

            interrupts = InterruptHandler.extract_all_interrupts(result)

            if interrupts:
                if len(interrupts) == 1:
                    interrupt_id, payload = interrupts[0]
                    question = InterruptHandler.format_question(payload)

                    user_response = prompt_callback(question)

                    if user_response.lower() in ["quit", "exit", "cancel"]:
                        logger.info("Workflow cancelled by user during HITL interaction")
                        result["cancelled"] = True
                        return result

                    state = Command(resume={interrupt_id: {"content": user_response}})
                    
                else:
                    logger.info(f"Handling {len(interrupts)} concurrent agent questions")

                    if progress_callback:
                        progress_callback(f"\n{'=' * 70}")
                        progress_callback(f"🤖 {len(interrupts)} AGENT QUESTIONS")
                        progress_callback(f"{'=' * 70}\n")

                    answers = {}
                    for idx, (interrupt_id, payload) in enumerate(interrupts, 1):
                        question = InterruptHandler.format_question(payload, index=idx)
                        
                        if progress_callback:
                            progress_callback(question)
                        
                        user_response = prompt_callback(f"\n👤 Answer {idx}: ")
                        
                        if user_response.lower() in ["quit", "exit", "cancel"]:
                            logger.info("Workflow cancelled by user during HITL interaction")
                            result["cancelled"] = True
                            return result
                        
                        answers[interrupt_id] = {"content": user_response}
                    
                    state = Command(resume=answers)
                
                continue

            if progress_callback:
                progress_callback("✅ Workflow completed")

            return result

        except KeyboardInterrupt:
            logger.info("Workflow interrupted by user (Ctrl+C)")
            raise
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            raise