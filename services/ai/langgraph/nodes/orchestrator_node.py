import logging
from typing import Protocol

from langchain_core.messages import AIMessage, HumanMessage

from langgraph.types import Command
from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


class InteractionProvider(Protocol):
    def collect_answers(self, questions: list[dict], stage_name: str) -> list[dict]:
        ...


class ConsoleInteractionProvider:
    def collect_answers(self, questions: list[dict], stage_name: str) -> list[dict]:
        answers = []
        
        print(f"\n{'='*60}")
        print(f"HITL INTERACTION REQUIRED - {stage_name}")
        print(f"{'='*60}")
        
        for i, qa in enumerate(questions, 1):
            agent_name = qa["agent"].replace("_", " ").title()
            question_data = qa["question"]
            
            print(f"\nQuestion {i}/{len(questions)} from {agent_name}:")
            print(f"  {question_data['message']}")
            if question_data.get("context"):
                print(f"  Context: {question_data['context']}")
            
            user_answer = input("\n👤 Your answer: ").strip()
            
            logger.info(f"User answered {agent_name} question {i}: {user_answer}")
            
            answers.append({
                "agent": qa["agent"],
                "question": question_data["message"],
                "answer": user_answer
            })
        
        print(f"\n{'='*60}\n")
        return answers


class MasterOrchestrator:
    STAGES = {
        "analysis": {
            "agents": [AgentRole.METRICS_EXPERT.value, AgentRole.PHYSIOLOGY_EXPERT.value, AgentRole.ACTIVITY_EXPERT.value],
            "result_keys": ["metrics_outputs", "physiology_outputs", "activity_outputs"],
            "next_node": "synthesis",
            "display_name": "Analysis"
        },
        "season_planning": {
            "agents": [AgentRole.SEASON_PLANNER.value],
            "result_keys": ["season_plan"],
            "next_node": "data_integration",
            "display_name": "Season Planning"
        },
        "weekly_planning": {
            "agents": [AgentRole.WORKOUT.value],
            "result_keys": ["weekly_plan"],
            "next_node": "plan_formatter",
            "display_name": "Weekly Planning"
        }
    }
    
    def __init__(self, interaction_provider: InteractionProvider = None):
        self.interaction_provider = interaction_provider or ConsoleInteractionProvider()
    
    def __call__(self, state: TrainingAnalysisState) -> Command:
        stage = self._detect_stage(state)
        config = self.STAGES[stage]
        
        logger.info(f"MasterOrchestrator: Processing {config['display_name']} stage")
        
        all_questions = self._collect_questions(state, config["result_keys"], config["agents"])
        
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
        
        logger.info(f"MasterOrchestrator: Found {len(all_questions)} questions, initiating HITL")
        
        answers = self.interaction_provider.collect_answers(all_questions, config["display_name"])
        
        agent_qa_updates = self._create_agent_specific_qa_messages(all_questions, answers)
        
        agents_to_reinvoke = []
        for key in agent_qa_updates.keys():
            agent_role = key.replace("_messages", "")
            if agent_role == AgentRole.WORKOUT.value:
                agents_to_reinvoke.append("weekly_planner")
            else:
                agents_to_reinvoke.append(agent_role)
        
        logger.info(f"MasterOrchestrator: Re-invoking {agents_to_reinvoke} with agent-specific Q&A messages")
        
        return Command(
            goto=agents_to_reinvoke,
            update=agent_qa_updates
        )
    
    def _detect_stage(self, state: TrainingAnalysisState) -> str:
        if state.get("synthesis_complete"):
            if state.get("season_plan_complete"):
                return "weekly_planning"
            return "season_planning"
        return "analysis"
    
    def _collect_questions(
        self,
        state: TrainingAnalysisState,
        result_keys: list[str],
        agent_names: list[str]
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
                    all_questions.append({
                        "agent": agent_name,
                        "question": question_dict
                    })
                logger.debug(f"Collected {len(questions)} questions from {result_key} (agent: {agent_name})")
        
        return all_questions
    
    def _create_agent_specific_qa_messages(
        self,
        questions: list[dict],
        answers: list[dict]
    ) -> dict:
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
            
            updates[field_name].extend([
                AIMessage(content=f"{question}"),
                HumanMessage(content=answer)
            ])
        
        return updates


def master_orchestrator_node(state: TrainingAnalysisState) -> Command:
    orchestrator = MasterOrchestrator()
    return orchestrator(state)