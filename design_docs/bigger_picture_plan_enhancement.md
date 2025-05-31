# Enhanced Weekly Planning Feature - Simplified Approach

## Overview

This document outlines a simplified approach to enhance the weekly planning feature with:

1. A high-level seasonal planning component integrated directly into the weekly plan flow
2. Extension to a two-week plan instead of a one-week plan
3. Streamlined workout details to keep the output manageable

## Key Changes

### 1. Integrated Season Planning Agent

Instead of creating a separate command and flow for season planning, we'll add a seasonal planning agent directly to the weekly plan flow. This agent will:

- Generate a high-level season plan (~12-24 weeks) with each weekly plan request
- Provide context for the two-week plan that follows
- Eliminate the need for separate storage or invalidation mechanisms

### 2. Two-Week Planning

The current weekly plan will be extended to cover two weeks instead of one, with:
- Slightly reduced detail level to keep the overall output manageable
- Clear connection to the seasonal context
- Appropriate adaptation options

## Implementation Plan

### 1. Update the WeeklyPlanState

```python
class WeeklyPlanState(BaseModel):
    """State management for weekly planning flow."""
    training_context: str = ""
    season_plan: str = ""  # New field for high-level season plan
    two_week_plan: str = ""  # Renamed from weekly_plan
    html_result: str = ""
```

### 2. Enhanced WeeklyPlanCrew

Add a new agent to the existing WeeklyPlanCrew:

```python
@agent
def season_planner_agent(self) -> Agent:
    """Create season planning agent."""
    return Agent(
        config=self.agents_config['season_planner_agent'],
        llm=ModelSelector.get_llm(AgentRole.SEASON_PLANNER)  # New role
    )

@task
def season_plan_task(self) -> Task:
    """Create season planning task."""
    return Task(
        config=self.tasks_config['season_plan_task'],
        context=[self.training_context_task()]  # Use training context as input
    )

@task
def weekly_plan_task(self) -> Task:
    """Create two-week planning task."""
    return Task(
        config=self.tasks_config['weekly_plan_task'],
        context=[self.training_context_task(), self.season_plan_task()]  # Use both tasks as context
    )

@task
def formatter_task(self) -> Task:
    """Create formatter task."""
    return Task(
        config=self.tasks_config['formatter_task'],
        context=[self.weekly_plan_task()]  # This already includes the other tasks indirectly
    )

@crew
def season_planner_crew(self) -> Crew:
    """Create season planner crew."""
    return Crew(
        agents=[self.season_planner_agent()],
        tasks=[self.season_plan_task()],
        process=Process.sequential
    )
```

### 3. Update Weekly Plan Flow

Modify the flow to incorporate the seasonal planning step and extend to two weeks:

```python
class EnhancedWeeklyPlanFlow(Flow[WeeklyPlanState]):
    """Enhanced weekly planning flow with integrated season planning."""
    
    # [existing initialization code]
    
    @start()
    async def analyze_training_context(self):
        """Analyze training context."""
        # Similar to existing implementation, but calculate two-week dates
        try:
            # Load cached analysis results
            # [existing code]
            
            # Calculate the two-week period dates instead of one week
            current_date = datetime.now()
            two_week_dates = []
            for i in range(14):  # 14 days instead of 7
                day = current_date + timedelta(days=i)
                two_week_dates.append({
                    'date': day.isoformat(),
                    'date_formatted': day.strftime('%Y-%m-%d'),
                    'day_name': day.strftime('%A')
                })
            
            result = await self.crew_instance.training_context_crew().kickoff_async(
                inputs={
                    # [existing params]
                    'week_dates': json.dumps(two_week_dates, indent=2)  # Now includes 14 days
                }
            )
            self.state.training_context = result
            logger.info("Training Context Analysis completed")
            return result
        except Exception as e:
            logger.error(f"Training context analysis failed: {str(e)}")
            self.state.training_context = f"Error during training context analysis: {str(e)}"
            raise
    
    @listen(analyze_training_context)
    async def generate_season_plan(self):
        """Generate high-level season plan."""
        try:
            # No need to pass training_context explicitly as it's already in the context
            result = await self.crew_instance.season_planner_crew().kickoff_async(
                inputs={
                    'athlete_name': self.athlete_name,
                    'athlete_context': self.athlete_context,
                    'competitions': json.dumps(self.crew_instance.competitions, indent=2),
                    'current_date': json.dumps(self.crew_instance.current_date, indent=2)
                }
            )
            self.state.season_plan = result
            logger.info("Season Plan Generation completed")
            return result
        except Exception as e:
            logger.error(f"Season plan generation failed: {str(e)}")
            self.state.season_plan = f"Error during season plan generation: {str(e)}"
            raise
    
    @listen(generate_season_plan)
    async def generate_two_week_plan(self):
        """Generate two-week training plan."""
        try:
            # Calculate the two-week period dates
            current_date = datetime.now()
            two_week_dates = []
            for i in range(14):  # 14 days instead of 7
                day = current_date + timedelta(days=i)
                two_week_dates.append({
                    'date': day.isoformat(),
                    'date_formatted': day.strftime('%Y-%m-%d'),
                    'day_name': day.strftime('%A')
                })
            
            # No need to pass training_context or season_plan explicitly as they're in the context
            result = await self.crew_instance.weekly_planner_crew().kickoff_async(
                inputs={
                    'athlete_name': self.athlete_name,
                    'athlete_context': self.athlete_context,
                    'competitions': json.dumps(self.crew_instance.competitions, indent=2),
                    'current_date': json.dumps(self.crew_instance.current_date, indent=2),
                    'week_dates': json.dumps(two_week_dates, indent=2)  # Now includes 14 days
                }
            )
            self.state.two_week_plan = result
            logger.info("Two-Week Plan Generation completed")
            return result
        except Exception as e:
            logger.error(f"Two-week plan generation failed: {str(e)}")
            self.state.two_week_plan = f"Error during two-week plan generation: {str(e)}"
            raise
    
    @listen(generate_two_week_plan)
    async def format_to_html(self):
        """Convert plans to HTML."""
        try:
            # No need to pass two_week_plan or season_plan explicitly as they're in the context
            logger.info("Starting HTML formatting")
            result = await self.crew_instance.formatter_crew().kickoff_async()
            self.state.html_result = result
            logger.info("HTML formatting completed successfully")
            return result
        except Exception as e:
            logger.error(f"HTML formatting failed: {str(e)}")
            self.state.html_result = f"Error during HTML formatting: {str(e)}"
            raise
```

### 4. Configuration Updates

#### AI Settings Update

```python
# In services/ai/ai_settings.py

class AgentRole(str, Enum):
    """Agent roles for different types of tasks."""
    # Existing roles...
    SEASON_PLANNER = "season_planner"  # New role
```

#### New Season Planner Agent Config

```yaml
# Add to services/ai/flows/weekly_plan/config/agents.yaml

season_planner_agent:
  role: Coach Magnus Thorsson - Season Strategist
  goal: |
    Create a high-level training plan covering the next 12-24 weeks that provides
    periodization structure and training phases leading up to key competitions.
  backstory: |
    Coach Magnus Thorsson is a legendary ultra-endurance champion from Iceland who now 
    coaches remotely from his mountain cabin near Reykjavík. After winning the Arctic 
    Ultra five times and setting records in events across all seven continents, Magnus 
    developed the "Thorsson Method" of periodization that's now used by world champions 
    in multiple endurance disciplines.
    
    Magnus grew up in a small fishing village where his father taught him that "the sea 
    doesn't care about your schedule" - a philosophy he applies to training: the body's 
    readiness dictates the work, not the calendar. His approach combines old-world 
    intuition with modern science, creating training plans that feel almost mystically 
    attuned to an athlete's needs.
    
    As a seasonal planner, Magnus excels at:
    - Designing progressive training phases based on race goals
    - Balancing workload and recovery across macro-cycles
    - Creating season-long intensity progressions
    - Building confidence through strategic fitness milestones
```

#### Season Planning Task Config

```yaml
# Add to services/ai/flows/weekly_plan/config/tasks.yaml

season_plan_task:
  name: season_plan_generation
  description: >
    You are Coach Magnus Thorsson, a legendary ultra-endurance champion who developed the "Thorsson Method" of periodization. Based on Dr. Chen's training context analysis and the athlete's competition schedule, create a high-level season plan covering the next 12-24 weeks.

    ## Athlete Information
    - Name: {athlete_name}
    - Custom Context: {athlete_context}
    - Current Date: {current_date}
    - Upcoming Competitions: {competitions}

    ## Training Context Analysis
    {training_context_task}

    ## Your Task
    Create a high-level season plan that provides a framework for the next 12-24 weeks of training, leading up to key competitions. This should be concise yet informative, focusing on:

    1. PLAN OVERVIEW: A brief summary of the season plan structure and progression
    2. TRAINING PHASES: Define 3-5 key training phases with approximate date ranges
    3. PHASE DETAILS: For each phase, provide:
       - Primary focus and goals
       - Weekly volume targets (approximate)
       - Intensity distribution
       - Key workout types

    For each phase, include a brief table showing:
    - Weeks covered (e.g., "Weeks 1-4: May 6 - June 2")
    - Weekly volume range
    - Primary focus
    - Key workout types

    KEEP THIS CONCISE! This is a high-level plan that will contextualize a more detailed two-week plan.
    
    Format your response as a structured markdown document with clear headings and bullet points.
  expected_output: >
    A high-level season plan covering 12-24 weeks with clear training phases,
    focusing on periodization to prepare for key competitions.
  output_file: stuff/weekly_plans/season_plan.md
  agent: season_planner_agent
```

#### Updated Weekly Plan Task Config

```yaml
# Update the existing weekly plan task to generate a two-week plan

weekly_plan_task:
  name: two_week_plan_generation
  description: >
    You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization. Based on Dr. Chen's training context analysis and your season plan, create a detailed 14-day training plan.

    ## Athlete Information
    - Name: {athlete_name}
    - Current Date: {current_date}
    - Upcoming Two Weeks: {week_dates}
    - Upcoming Competitions: {competitions}
    - Custom User Instructions: {athlete_context}

    ## Analysis Information
    {training_context_task}

    ## Season Plan
    {season_plan_task}

    ## Your Task
    Create a detailed 14-day training plan that:
    1. Aligns with the current phase in your season plan
    2. Adapts to the athlete's current Training Readiness Score
    3. Provides an appropriate balance of workload and recovery
    
    For each day of the two-week period, provide:

    1. DAY & DATE: The day of the week and date
    2. WORKOUT TYPE: Primary workout type (e.g., Easy Run, Interval Session, etc.)
    3. PURPOSE: The purpose of this workout within the training plan
    4. STRUCTURE: A streamlined structure including:
       - Main sets with intensities and durations
       - Key workout parameters
    5. INTENSITY GUIDANCE: Target zones, effort levels, or pace guidelines
    6. ADAPTATION OPTIONS: Brief options for adjusting based on readiness

    Begin with a concise overview of how this two-week block fits within the current training phase.
    
    IMPORTANT: Keep workout details more concise than in a one-week plan, focusing on the most important elements while maintaining enough detail for execution.

    Use the following style guidelines:
    - Clear headings for each day
    - Emojis for key sections
    - Bullet points for clarity
    - Bold text for intensity guidance
  expected_output: >
    A two-week training plan with appropriately detailed workouts for each day,
    aligned with the season plan and current training phase.
  output_file: stuff/weekly_plans/two_week_plan.md
  agent: weekly_planner_agent
```

#### Updated Formatter Task Config

```yaml
# Update the formatter task to handle both plans

formatter_task:
  name: format_to_html
  description: >
    You are Pixel, a former Silicon Valley UX designer who created the "Training Visualization Framework." Your task is to transform the season plan and two-week training plan from markdown format into a professional HTML document.

    ## Your Task
    Convert the markdown content into a complete HTML document with the following features:

    1. A clean, responsive design that works well on both desktop and mobile
    2. Two clearly separated sections:
       a. A high-level season plan overview at the top
       b. The detailed two-week plan below
    3. Clear visual hierarchy with appropriate headings, spacing, and typography
    4. Color-coding for different intensity levels 
    5. Proper semantic HTML5 structure
    6. Basic CSS styling included in a <style> tag in the document head

    ## Input Content
    Season Plan: {season_plan_task}
    Two-Week Plan: {weekly_plan_task}

    Include design elements such as:
    - A header section with the athlete's name and training period
    - A visual representation of the season plan phases
    - Day-by-day sections for the two-week plan
    - Consistent formatting for workout details
    - Appropriate use of color to indicate intensity levels

    Return the complete HTML document.
  expected_output: >
    A complete HTML document with proper styling and structure that presents both the
    season plan and two-week training plan in an integrated, visually appealing format.
  output_file: stuff/weekly_plans/formatted.html
  agent: formatter_agent
  max_retries: 10
```

## Code Changes Required

1. **services/ai/ai_settings.py**
   - Add SEASON_PLANNER to AgentRole enum

2. **services/ai/flows/weekly_plan/weekly_plan_flow.py**
   - Update WeeklyPlanState to include season_plan field
   - Add season planner agent, task, and crew methods to WeeklyPlanCrew
   - Update the task context chains to properly pass information between tasks
   - Modify WeeklyPlanFlow to include season planning step
   - Update date calculations to cover two weeks

3. **services/ai/flows/weekly_plan/config/agents.yaml**
   - Add season_planner_agent configuration

4. **services/ai/flows/weekly_plan/config/tasks.yaml**
   - Add season_plan_task configuration
   - Update weekly_plan_task to generate a two-week plan
   - Update formatter_task to handle both plans

## Benefits of This Approach

1. **Simplicity**: No need for separate commands, cache management, or invalidation logic
2. **Efficiency**: Proper use of task contexts eliminates redundant passing of data
3. **Consistency**: Season plan is always current with latest competition schedule
4. **User Experience**: Users get both a high-level overview and detailed near-term plan in one view

## Implementation Timeline

| Task | Estimated Time |
|------|----------------|
| Update AI settings with new role | 0.5 day |
| Create season planner agent and task configs | 1 day |
| Update weekly plan flow | 2 days |
| Modify formatter for combined output | 1 day |
| Testing and refinement | 1.5 days |
| **Total** | **6 days** |