import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from langgraph.types import Command

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


class Question(BaseModel):
    """Structured question for HITL interaction."""
    
    id: str = Field(..., description="Unique identifier (e.g., 'metrics_q1')")
    message: str = Field(..., description="Question text")
    context: str | None = Field(None, description="Additional context")
    message_type: Literal["question", "observation", "clarification"] = Field(
        "question", 
        description="Type of message"
    )


class AgentOutput(BaseModel):
    """Structured output from agents with optional questions."""
    
    content: str = Field(..., description="Final analysis/output text if all questions clarified")
    questions: list[Question] | None = Field(None, description="Optional HITL questions")


class MasterOrchestrator:
    """Unified orchestrator for all HITL interactions across workflow stages.
    
    Single orchestrator instance handles three decision points:
    1. After experts → routes to synthesis or re-invokes experts
    2. After season planner → routes to data_integration or re-invokes planner
    3. After weekly planner → routes to plan_formatter or re-invokes planner
    
    Stage detection based on state markers automatically determines context.
    """
    
    STAGES = {
        "analysis": {
            "agents": ["metrics_expert", "physiology_expert", "activity_expert"],
            "result_keys": ["metrics_result", "physiology_result", "activity_result"],
            "next_node": "synthesis",
            "display_name": "Analysis"
        },
        "season_planning": {
            "agents": ["season_planner"],
            "result_keys": ["season_plan"],
            "next_node": "data_integration",
            "display_name": "Season Planning"
        },
        "weekly_planning": {
            "agents": ["weekly_planner"],
            "result_keys": ["weekly_plan"],
            "next_node": "plan_formatter",
            "display_name": "Weekly Planning"
        }
    }
    
    def __call__(self, state: TrainingAnalysisState) -> Command:
        """Main orchestration logic with stage detection and HITL handling."""
        stage = self._detect_stage(state)
        config = self.STAGES[stage]
        
        logger.info(f"MasterOrchestrator: Processing {config['display_name']} stage")
        
        all_questions = self._collect_questions(state, config["result_keys"])
        
        if not all_questions:
            logger.info(f"MasterOrchestrator: No questions found, proceeding to {config['next_node']}")
            return Command(goto=config["next_node"])
        
        if not state.get("hitl_enabled", True):
            logger.info("MasterOrchestrator: HITL disabled, skipping questions")
            return Command(goto=config["next_node"])
        
        logger.info(f"MasterOrchestrator: Found {len(all_questions)} questions, initiating HITL")
        
        answers = self._collect_answers(all_questions, config["display_name"])
        
        qa_messages = self._create_qa_messages(all_questions, answers)
        
        logger.info(f"MasterOrchestrator: Re-invoking {config['agents']} with {len(qa_messages)} Q&A messages")
        
        return Command(
            goto=config["agents"],
            update={"messages": state["messages"] + qa_messages}
        )
    
    def _detect_stage(self, state: TrainingAnalysisState) -> str:
        """Determine current workflow stage from state markers."""
        if state.get("synthesis_complete"):
            if state.get("season_plan_complete"):
                return "weekly_planning"
            return "season_planning"
        return "analysis"
    
    def _collect_questions(
        self,
        state: TrainingAnalysisState,
        result_keys: list[str]
    ) -> list[dict]:
        """Collect all questions from stage-specific agent outputs stored in result fields."""
        all_questions = []
        
        for result_key in result_keys:
            result = state.get(result_key)
            
            if result and isinstance(result, dict):
                questions = result.get("questions", [])
                if questions:
                    agent_name = result_key.replace("_result", "").replace("_plan", "")
                    for q in questions:
                        all_questions.append({
                            "agent": agent_name,
                            "question": q
                        })
                    logger.debug(f"Collected {len(questions)} questions from {result_key}")
        
        return all_questions
    
    def _collect_answers(
        self,
        questions: list[dict],
        stage_name: str
    ) -> list[dict]:
        """Collect user answers for all questions via interactive CLI prompts."""
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
            
            # Get real user input from CLI
            user_answer = input("\n👤 Your answer: ").strip()
            
            # Log the interaction for debugging
            logger.info(f"User answered {agent_name} question {i}: {user_answer}")
            
            answers.append({
                "agent": qa["agent"],
                "question": question_data["message"],
                "answer": user_answer
            })
        
        print(f"\n{'='*60}\n")
        return answers
    
    def _create_qa_messages(
        self, 
        questions: list[dict], 
        answers: list[dict]
    ) -> list:
        """Create AIMessage/HumanMessage pairs from Q&A data."""
        qa_messages = []
        
        for qa_item, answer_item in zip(questions, answers):
            agent_name = qa_item["agent"].replace("_", " ").upper()
            question = qa_item["question"]["message"]
            answer = answer_item["answer"]
            
            qa_messages.extend([
                AIMessage(content=f"{question}"),
                HumanMessage(content=answer)
            ])
        
        return qa_messages


def master_orchestrator_node(state: TrainingAnalysisState) -> Command:
    """Master orchestrator node for unified HITL across all workflow stages."""
    orchestrator = MasterOrchestrator()
    return orchestrator(state)