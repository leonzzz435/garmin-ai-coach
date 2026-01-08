import logging
import os
import select
import sys
import time
from typing import Callable, Protocol

from langchain_core.messages import AIMessage, HumanMessage

from langgraph.types import Command
from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)

_HITL_BEGIN_HOOK: Callable[[list[dict], str], None] | None = None
_HITL_END_HOOK: Callable[[], None] | None = None


def register_hitl_hooks(
    begin_hook: Callable[[list[dict], str], None] | None,
    end_hook: Callable[[], None] | None,
) -> None:
    global _HITL_BEGIN_HOOK, _HITL_END_HOOK
    _HITL_BEGIN_HOOK = begin_hook
    _HITL_END_HOOK = end_hook


def clear_hitl_hooks() -> None:
    register_hitl_hooks(None, None)


def _get_hitl_timeout_seconds() -> float | None:
    raw = os.getenv("HITL_TIMEOUT_SECONDS")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid HITL_TIMEOUT_SECONDS=%s; ignoring", raw)
        return None
    return value if value > 0 else None


class InteractionProvider(Protocol):
    def collect_answers(self, questions: list[dict], stage_name: str) -> list[dict]: ...


def _read_with_timeout(prompt: str, timeout_seconds: float | None) -> str:
    if timeout_seconds is None or timeout_seconds <= 0:
        return input(prompt)

    if os.name == "nt":
        logger.info("HITL timeout configured but unsupported on Windows; waiting indefinitely")
        return input(prompt)

    sys.stdout.flush()
    sys.stderr.flush()
    start = time.time()
    remaining = timeout_seconds
    while remaining > 0:
        ready, _, _ = select.select([sys.stdin], [], [], remaining)
        if ready:
            return sys.stdin.readline().strip()
        remaining = timeout_seconds - (time.time() - start)

    logger.warning("HITL input timed out after %.1fs; defaulting to empty answer", timeout_seconds)
    return ""


class ConsoleInteractionProvider:
    def __init__(self, timeout_seconds: float | None = None):
        self.timeout_seconds = timeout_seconds

    def collect_answers(self, questions: list[dict], stage_name: str) -> list[dict]:
        answers = []

        if _HITL_BEGIN_HOOK:
            try:
                _HITL_BEGIN_HOOK(questions, stage_name)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("HITL begin hook failed: %s", exc)

        try:
            print(f"\n{'=' * 60}")
            print(f"HITL INTERACTION REQUIRED - {stage_name}")
            print(f"{'=' * 60}")

            for i, qa in enumerate(questions, 1):
                agent_name = qa["agent"].replace("_", " ").title()
                question_data = qa["question"]

                print(f"\nQuestion {i}/{len(questions)} from {agent_name}:")
                print(f"  {question_data['message']}")
                if question_data.get("context"):
                    print(f"  Context: {question_data['context']}")

                user_answer = _read_with_timeout("\n👤 Your answer: ", self.timeout_seconds)

                logger.info(f"User answered {agent_name} question {i}: {user_answer}")

                answers.append(
                    {
                        "agent": qa["agent"],
                        "question": question_data["message"],
                        "answer": user_answer,
                    }
                )

            print(f"\n{'=' * 60}\n")
        finally:
            if _HITL_END_HOOK:
                try:
                    _HITL_END_HOOK()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.debug("HITL end hook failed: %s", exc)

        return answers


class MasterOrchestrator:
    STAGES = {
        "analysis": {
            "agents": [
                AgentRole.METRICS_EXPERT.value,
                AgentRole.PHYSIOLOGY_EXPERT.value,
                AgentRole.ACTIVITY_EXPERT.value,
            ],
            "result_keys": ["metrics_outputs", "physiology_outputs", "activity_outputs"],
            "next_node": "synthesis",
            "display_name": "Analysis",
        },
        "season_planning": {
            "agents": [AgentRole.SEASON_PLANNER.value],
            "result_keys": ["season_plan"],
            "next_node": "data_integration",
            "display_name": "Season Planning",
        },
        "weekly_planning": {
            "agents": [AgentRole.WORKOUT.value],
            "result_keys": ["weekly_plan"],
            "next_node": "plan_formatter",
            "display_name": "Weekly Planning",
        },
    }

    def __init__(self, interaction_provider: InteractionProvider = None):
        timeout_seconds = _get_hitl_timeout_seconds()
        if interaction_provider is None:
            self.interaction_provider = ConsoleInteractionProvider(timeout_seconds=timeout_seconds)
        else:
            self.interaction_provider = interaction_provider

    def __call__(self, state: TrainingAnalysisState) -> Command:
        stage = self._detect_stage(state)
        config = self.STAGES[stage]

        logger.info(
            "MasterOrchestrator: stage=%s next=%s skip_synthesis=%s hitl_enabled=%s",
            config["display_name"],
            config["next_node"],
            state.get("skip_synthesis", False),
            state.get("hitl_enabled", True),
        )

        all_questions = self._collect_questions(state, config["result_keys"], config["agents"])
        logger.info("MasterOrchestrator: found %d questions for stage %s", len(all_questions), config["display_name"])

        if not all_questions:
            if stage == "analysis":
                if state.get("skip_synthesis", False):
                    logger.info("MasterOrchestrator: skip_synthesis=True, proceeding directly to season_planner")
                    return Command(goto="season_planner", update={"synthesis_complete": True})
                else:
                    logger.info("MasterOrchestrator: No questions found, proceeding to synthesis and season_planner")
                    return Command(goto=["synthesis", "season_planner"])
            else:
                logger.info(f"MasterOrchestrator: No questions found, proceeding to {config['next_node']}")
                return Command(goto=config["next_node"])

        if not state.get("hitl_enabled", True):
            logger.info("MasterOrchestrator: HITL disabled, skipping questions")
            return Command(goto=config["next_node"])

        logger.info(
            "MasterOrchestrator: Initiating HITL with %d questions (stage=%s)",
            len(all_questions),
            config["display_name"],
        )

        answers = self.interaction_provider.collect_answers(all_questions, config["display_name"])
        logger.info(
            "MasterOrchestrator: HITL completed with %d answers for stage %s",
            len(answers),
            config["display_name"],
        )

        agent_qa_updates = self._create_agent_specific_qa_messages(all_questions, answers)

        hitl_updates = {
            "hitl_questions_total": len(all_questions),
            "hitl_interactions_completed": len(answers),
            "hitl_sessions": [
                {
                    "stage": config["display_name"],
                    "questions": len(all_questions),
                    "answered": len(answers),
                }
            ],
        }
        agent_qa_updates.update(hitl_updates)

        agents_to_reinvoke = []
        for key in agent_qa_updates.keys():
            agent_role = key.replace("_messages", "")
            if agent_role == AgentRole.WORKOUT.value:
                agents_to_reinvoke.append("weekly_planner")
            else:
                agents_to_reinvoke.append(agent_role)

        logger.info(f"MasterOrchestrator: Re-invoking {agents_to_reinvoke} with agent-specific Q&A messages")

        return Command(goto=agents_to_reinvoke, update=agent_qa_updates)

    def _detect_stage(self, state: TrainingAnalysisState) -> str:
        if state.get("synthesis_complete"):
            if state.get("season_plan_complete"):
                return "weekly_planning"
            return "season_planning"
        return "analysis"

    def _collect_questions(
        self, state: TrainingAnalysisState, result_keys: list[str], agent_names: list[str]
    ) -> list[dict]:
        all_questions = []

        for result_key, agent_name in zip(result_keys, agent_names, strict=True):
            result = state.get(result_key)

            if not result:
                continue

            questions = None
            if hasattr(result, "output"):
                output = result.output
                if isinstance(output, list):
                    questions = output
            elif isinstance(result, dict):
                output = result.get("output", [])
                if isinstance(output, list):
                    questions = output

            if questions:
                for q in questions:
                    question_dict = q.model_dump() if hasattr(q, "model_dump") else q
                    all_questions.append({"agent": agent_name, "question": question_dict})
                logger.debug(f"Collected {len(questions)} questions from {result_key} (agent: {agent_name})")

        return all_questions

    def _create_agent_specific_qa_messages(self, questions: list[dict], answers: list[dict]) -> dict:
        updates = {}

        for qa_item, answer_item in zip(questions, answers, strict=True):
            agent_name = qa_item["agent"]
            question = qa_item["question"]["message"]
            answer = answer_item["answer"]

            if agent_name == AgentRole.WORKOUT.value:
                field_name = "weekly_planner_messages"
            else:
                field_name = f"{agent_name}_messages"

            if field_name not in updates:
                updates[field_name] = []

            updates[field_name].extend([AIMessage(content=f"{question}"), HumanMessage(content=answer)])

        return updates


def master_orchestrator_node(state: TrainingAnalysisState) -> Command:
    orchestrator = MasterOrchestrator()
    return orchestrator(state)
