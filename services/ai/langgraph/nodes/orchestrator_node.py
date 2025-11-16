import logging

from langchain_core.messages import AIMessage, HumanMessage

from langgraph.types import Command

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


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
            "result_keys": ["metrics_outputs", "physiology_outputs", "activity_outputs"],
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
        
        all_questions = self._collect_questions(state, config["result_keys"], config["agents"])
        
        if not all_questions:
            # For analysis stage, route to BOTH synthesis and season_planner in parallel (or skip synthesis)
            if stage == "analysis":
                if state.get("skip_synthesis", False):
                    logger.info("MasterOrchestrator: skip_synthesis=True, proceeding directly to season_planner")
                    return Command(goto="season_planner")
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
        
        answers = self._collect_answers(all_questions, config["display_name"])
        
        # Create agent-specific Q&A messages
        agent_qa_updates = self._create_agent_specific_qa_messages(all_questions, answers)
        
        # Only re-invoke agents that actually had questions
        agents_to_reinvoke = [key.replace("_messages", "") for key in agent_qa_updates.keys()]
        
        logger.info(f"MasterOrchestrator: Re-invoking {agents_to_reinvoke} with agent-specific Q&A messages")
        
        return Command(
            goto=agents_to_reinvoke,
            update=agent_qa_updates
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
        result_keys: list[str],
        agent_names: list[str]
    ) -> list[dict]:
        """Collect all questions from stage-specific agent outputs stored in result fields."""
        all_questions = []
        
        # Map result_keys to agent_names
        for result_key, agent_name in zip(result_keys, agent_names, strict=True):
            result = state.get(result_key)
            
            if not result:
                continue
            
            # Handle both ExpertOutput and AgentOutput with union type output field
            questions = None
            if hasattr(result, "output"):
                # Union type: list[Question] | ReceiverOutputs (experts) or list[Question] | str (agents)
                output = result.output
                if isinstance(output, list):
                    questions = output
            elif isinstance(result, dict):
                # Fallback for dict format (if any legacy code)
                questions = result.get("questions", [])
            
            if questions:
                for q in questions:
                    # Convert Question object to dict if needed
                    question_dict = q.model_dump() if hasattr(q, "model_dump") else q
                    all_questions.append({
                        "agent": agent_name,
                        "question": question_dict
                    })
                logger.debug(f"Collected {len(questions)} questions from {result_key} (agent: {agent_name})")
        
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
    
    def _create_agent_specific_qa_messages(
        self,
        questions: list[dict],
        answers: list[dict]
    ) -> dict:
        """Create agent-specific Q&A message updates with accumulated messages per agent."""
        updates = {}
        
        for qa_item, answer_item in zip(questions, answers, strict=True):
            agent_name = qa_item["agent"]
            question = qa_item["question"]["message"]
            answer = answer_item["answer"]
            
            # Store in agent-specific field
            field_name = f"{agent_name}_messages"
            
            # Initialize list if not present, then append Q&A pair
            if field_name not in updates:
                updates[field_name] = []
            
            # Append Q&A pair for this agent (one pair per question)
            updates[field_name].extend([
                AIMessage(content=f"{question}"),
                HumanMessage(content=answer)
            ])
        
        return updates


def master_orchestrator_node(state: TrainingAnalysisState) -> Command:
    """Master orchestrator node for unified HITL across all workflow stages."""
    orchestrator = MasterOrchestrator()
    return orchestrator(state)