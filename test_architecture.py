
import agentops

from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel

# Define structured state for the flow
class AnalysisState(BaseModel):
    metrics_result: str = ""
    activities_result: str = ""
    physiology_result: str = ""
    synthesis_result: str = ""

# Define agents with backstories and goals
agent_metrics = Agent(
    role="Metrics Analysis Specialist",
    goal="Analyze training metrics",
    backstory="An expert in analyzing performance metrics for athletes."
)

agent_activities = Agent(
    role="Activities Analysis Specialist",
    goal="Analyze workout activities",
    backstory="A seasoned analyst focusing on workout patterns and improvements."
)

agent_physiology = Agent(
    role="Physiology Analysis Specialist",
    goal="Analyze physiological responses",
    backstory="Specialist in understanding physiological trends and recovery."
)

synthesis_agent = Agent(
    role="Synthesis Specialist",
    goal="Aggregate and synthesize analysis results",
    backstory="An AI adept at combining insights into actionable recommendations."
)

# Define tasks
metrics_task = Task(
    name="Metrics Analysis",
    description="Analyze training metrics and patterns",
    agent=agent_metrics,
    tools=[],
    expected_output="Metrics analysis completed."
)

activities_task = Task(
    name="Activities Analysis",
    description="Analyze workout activities and patterns",
    agent=agent_activities,
    tools=[],
    expected_output="Activities analysis completed."
)

physiology_task = Task(
    name="Physiology Analysis",
    description="Analyze physiological responses and trends",
    agent=agent_physiology,
    tools=[],
    expected_output="Physiology analysis completed."
)

synthesis_task = Task(
    name="Synthesis",
    description="Combine and synthesize analysis results",
    agent=synthesis_agent,
    tools=[],
    context=[metrics_task, activities_task, physiology_task],
    expected_output="Synthesis report generated."
)

# Define the custom Flow
class AnalysisFlow(Flow[AnalysisState]):
    
    @start()
    def analyze_metrics(self):
        """Perform metrics analysis."""
        crew = Crew(tasks=[metrics_task], agents=[agent_metrics], verbose=True)
        result = crew.kickoff()
        self.state.metrics_result = result
        print(f"Metrics Analysis Result: {result}")
        return result

    @listen(analyze_metrics)
    def analyze_activities(self, metrics_result):
        """Perform activities analysis."""
        crew = Crew(tasks=[activities_task], agents=[agent_activities], verbose=True)
        result = crew.kickoff()
        self.state.activities_result = result
        print(f"Activities Analysis Result: {result}")
        return result

    @listen(analyze_activities)
    def analyze_physiology(self, activities_result):
        """Perform physiology analysis."""
        crew = Crew(tasks=[physiology_task], agents=[agent_physiology], verbose=True)
        result = crew.kickoff()
        self.state.physiology_result = result
        print(f"Physiology Analysis Result: {result}")
        return result

    @listen(analyze_physiology)
    def synthesize_results(self, physiology_result):
        """Combine analysis results into a synthesis report."""
        session = agentops.init("31106bb1-bcb6-42cf-8123-328cfd226526")
        crew = Crew(tasks=[synthesis_task], agents=[synthesis_agent], verbose=True)
        result = crew.kickoff()
        self.state.synthesis_result = result
        print(f"Synthesis Result:\n{result}")
        return result

# Main entry point to execute the flow
def main():
    flow = AnalysisFlow()
    result = flow.kickoff() 
    print(f"\nFinal Synthesis Result:\n{result}")

main()
