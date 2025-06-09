"""
User prompts for LangChain agents defining specialized analysis tasks.
These prompts contain the specific task instructions and requirements.
"""

class UserPrompts:
    """User prompts that define specific tasks and their requirements."""
    
    METRICS_ANALYSIS = """Analyze historical training metrics to identify patterns and trends in the athlete's data.

## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals.

Input Data:
```json
{data}
```

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Analysis Context:
```
{analysis_context}
```

IMPORTANT: Only analyze the data that is actually present in the input!

CONTEXT INTEGRATION: If analysis context is provided, use it to interpret the data more accurately.

Your task is to:
1. Analyze training load trends over time to identify patterns
2. Examine fitness metrics progression if that data is available
3. Evaluate training status data to understand the athlete's current fitness state
4. Connect these metrics to upcoming competition dates
5. Identify potential performance opportunities or risks
6. Create practical recommendations based strictly on the available data

DO NOT speculate about metrics that aren't in the data. Focus on factual analysis.

Communicate with precise clarity and focus on making complex data easily understandable. Include a Metrics Readiness Score (0-100) with a clear explanation of how it was calculated using only the available metrics.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""

    ACTIVITY_DATA_EXTRACTION = """Your task is to objectively describe the athlete's recent training activities, transforming raw data into structured, factual summaries.

Input Data:
```json
{data}
```

Your task is to:
1. Extract key metrics from each activity (date, type, duration, distance)
2. Describe each lap's effort (pace/power/HR) objectively using tables
3. Summarize zone distribution with percentages in a consistent format
4. Present data in a structured, accessible format
5. STRICTLY AVOID any interpretation, coaching advice, or speculation

FORMATTING REQUIREMENTS:
- Use consistent formatting for all activities
- Present lap data in tables with columns for distance, duration, pace/power, heart rate
- Use bullet points for key metrics
- Include zone distribution tables for each activity
- Maintain consistent units (km/miles, min/km, watts, etc.)

STRICT PROHIBITION AGAINST INTERPRETATION:
- Do NOT evaluate if workouts were "good" or "bad"
- Do NOT speculate about athlete's feelings or sensations
- Do NOT suggest improvements or modifications
- Do NOT draw conclusions about fitness or readiness
- Do NOT compare workouts to each other qualitatively

Format each activity using this template:

# Activity: [Date - Type]

## Overview
* Duration: [time]
* Distance: [distance]
* Elevation Gain: [elevation]
* Average Heart Rate: [HR]
* Average Pace/Power: [pace/power]

## Lap Details
| Lap | Distance | Duration | Avg Pace | Avg HR | Max HR |
|-----|----------|----------|----------|--------|--------|
| 1   | x.x km   | mm:ss    | x:xx/km  | xxx    | xxx    |
| 2   | x.x km   | mm:ss    | x:xx/km  | xxx    | xxx    |

Repeat this format for each activity, organizing them chronologically from newest to oldest."""

    ACTIVITY_INTERPRETATION = """Your task is to interpret structured activity summaries to identify patterns and provide guidance.

Activity Summary Data:
{activity_summary}

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Analysis Context:
```
{analysis_context}
```

IMPORTANT: Only analyze the data that is actually present in the activity summaries!

CONTEXT INTEGRATION: If analysis context is provided, use it to interpret the data more accurately.

Your task is to:
1. Analyze the structured activity summaries
2. Identify clear patterns in workout execution and training progression
3. Evaluate pacing strategies based on the objective data provided
4. Analyze session progression based on factual evidence
5. Create a quality assessment using only available metrics

DO NOT speculate beyond what is evident in the activity data. Avoid making claims about:
- Physiological adaptations you cannot directly observe
- Internal sensations during workouts
- Metabolic processes not measured in the data
- Technical form issues not evident in the pace/power/HR metrics

IMPORTANT: Your analysis will be directly used by other agents to create comprehensive analysis.

Structure your response to include two clearly distinguished sections:

1. "HISTORICAL TRAINING SUMMARY" - Include a compact table showing only the most recent 10 days of completed training with:
   - Dates (most recent first)
   - Actual workout types performed
   - Actual durations
   - Actual intensity levels observed
   - Execution quality scores

Communicate with passionate precision and laser-like clarity. Include an Activity Quality Score (0-100) with a concise explanation of how you calculated it using only the available metrics from the activity summaries.

Format your response as a structured markdown document with clear sections and bullet points where appropriate."""

    PHYSIOLOGY_ANALYSIS = """Analyze the athlete's physiological data to assess recovery status and adaptation state.

## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals.

Input Data:
```json
{data}
```

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Analysis Context:
```
{analysis_context}
```

IMPORTANT: Only analyze the data that is actually present in the input!

CONTEXT INTEGRATION: If analysis context is provided, use it to interpret the data more accurately.

Your task is to:
1. Interpret heart rate variability patterns to assess the athlete's recovery status
2. Analyze available sleep data (duration, quality) if present
3. Evaluate stress scores and their trends
4. Track resting heart rate patterns as an indicator of fatigue and adaptation
5. Identify potential signs of overtraining based on these objective metrics
6. Suggest optimal recovery strategies based on the data available

DO NOT speculate about data that isn't present.
Communicate with calm wisdom and occasional metaphors drawn from both scientific background and cultural heritage. Include a Physiology Readiness Score (0-100) with a clear explanation of how it was calculated using only the available data.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""

    SYNTHESIS_ANALYSIS = """Synthesize the pattern analyses from metrics, activities, and physiology to create a comprehensive understanding of {athlete_name}'s historical training patterns and responses.

Metrics Analysis:
```markdown
{metrics_result}
```

Activity Interpretation:
```markdown
{activity_result}
```

Physiology Analysis:
```markdown
{physiology_result}
```

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Style Guide:
```markdown
{style_guide}
```

IMPORTANT: Focus on facts and evidence from the input analyses!

Your task is to:
1. Integrate key insights from the metrics, activity and physiology reports
2. Identify clear connections between the athlete's training loads and physiological responses
3. Recognize patterns in workout execution and performance outcomes
4. Provide actionable insights based only on evidence from the data
5. Create a focused synthesis that prioritizes the most important findings
6. Avoid speculative language and stick to patterns clearly visible in the data

FOCUS ON PRESENTATION:
- Use a clear executive summary at the beginning
- Present key performance indicators in table format when possible
- Organize information with concise headings and bullet points
- Keep recommendations brief and actionable
- Use visual separation between sections for better readability

Communicate with thoughtful clarity and make complex relationships immediately understandable.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""

    HTML_FORMATTING = """Transform the provided content into a beautiful, functional HTML document.

Analysis Content:
{synthesis_result}

REQUIREMENTS:
- Create information architecture optimized for athletic contexts
- Develop visual systems that intuitively communicate training relationships
- Design responsive layouts that work seamlessly across all devices
- Apply color theory to performance data visualization
- Implement typography systems optimized for various reading contexts

## CRITICAL: Interactive Plot Integration System

The content contains special **[PLOT:plot_id]** references that will be automatically replaced with interactive Plotly visualizations AFTER your HTML conversion. Understanding this system is crucial for your design:

**How Plot Resolution Works:**
1. You preserve [PLOT:plot_id] references exactly as written
2. After HTML generation, each reference gets replaced with a complete interactive plot
3. These become full-width, responsive Plotly charts with hover interactions, zoom, and controls

**Design Implications for You:**
- **Spacing**: Leave appropriate vertical margin around plot references (they become ~400-800px tall)
- **Responsive Design**: Plots auto-resize, so ensure your container CSS accommodates this
- **Content Flow**: Treat plot references as major content blocks, not inline elements
- **Typography**: Use compelling lead-in text before plots and descriptive follow-up text after
- **Visual Hierarchy**: These will be significant visual elements, so design section breaks accordingly

**What You Should Do:**
- Keep ALL [PLOT:plot_id] references EXACTLY as they appear
- Design your CSS to provide proper spacing and flow around where plots will appear
- Consider plots as primary visual elements in your information hierarchy
- Ensure your responsive design works with large embedded charts

Content Organization Process:
1. Include all important content (key insights, scores, recommendations, and supporting details)
2. Create a well-structured HTML document with appropriate organization
3. Use clean, readable CSS that enhances the presentation AND accommodates plot insertion
4. Present information in a logical, coherent manner with plots as focal points
5. Use design elements that enhance understanding and engagement
6. Ensure all metrics, scores, and their context are preserved
7. Implement your "contextual information hierarchy" concept that reveals different levels of detail
8. Design spacing and layout that will work beautifully with interactive plots

Style Guidelines:
- Use emojis thoughtfully to enhance key content:
  • 🎯 for goals and key points
  • 📊 for metrics
  • 🔍 for analysis
  • 💡 for tips

HTML Best Practices:
- Use appropriate CSS classes and styles for consistent presentation
- Create clean, well-structured markup
- Balance text content with helpful visual elements
- Use effective selectors and styling approaches
- Create a final HTML document that makes athletes instantly understand what matters most

Return ONLY the complete HTML document without any markdown code blocks or explanations."""

    # Weekly Planning Prompts
    SEASON_PLANNING = """Based on the athlete's competition schedule, create a high-level season plan covering the next 12-24 weeks.

## IMPORTANT: Output Context
This plan will be passed to a weekly planning agent and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other coaching professionals.

## Athlete Information
- Name: {athlete_name}
- Current Date: {current_date}
- Upcoming Competitions: {competitions}

## Your Task
Create a high-level season plan that provides a framework for the next 12-24 weeks of training, leading up to key competitions. This should be concise yet informative, focusing on:

1. PLAN OVERVIEW: A brief summary of the season plan structure and progression
2. TRAINING PHASES: Define key training phases with approximate date ranges
3. PHASE DETAILS: For each phase, provide:
   - Primary focus and goals
   - Weekly volume targets (approximate)
   - Intensity distribution
   - Key workout types

KEEP THIS CONCISE! This is a high-level plan that will contextualize a more detailed two-week plan.

Format the response as a structured markdown document with clear headings and bullet points."""

    WEEKLY_PLANNING = """Based on your season plan and the athlete's specific requirements, create a detailed 14-day training plan.

## Season Plan Context
```markdown
{season_plan}
```

## Athlete Information
- Name: {athlete_name}
- Current Date: {current_date}
- Upcoming Two Weeks: {week_dates}
- Upcoming Competitions: {competitions}
- Custom User Instructions: {planning_context}

## Available Analysis
You have access to detailed analysis data to inform your training decisions:

Metrics Analysis:
```markdown
{metrics_analysis}
```

Activity Analysis:
```markdown
{activity_analysis}
```

Physiology Analysis:
```markdown
{physiology_analysis}
```

Use this analysis data to assess the athlete's current training readiness, physiological status, and recent training patterns when creating your plan.

## Training Zones
IMPORTANT: Before creating the training plan, establish appropriate training intensity zones based on any physiological metrics available in the athlete's context (such as LTHR, FTP, max HR, etc.).

Using your expertise as Coach Thorsson, define sport-specific zones (running, cycling, etc.) that align with standard training methodology. Include these defined zones at the beginning of your plan in a clear reference table.

These zones will be the foundation for all intensity prescriptions in your workouts and ensure consistency throughout the training plan.

## Your Task
IMPORTANT: Create a concrete, practical 14-day training plan that:
1. Aligns with the current phase in your season plan
2. Adapts to the athlete's current Training Readiness Score
3. Provides an appropriate balance of workload and recovery

For each day of the two-week period, provide:

1. DAY & DATE: The day of the week and date
2. DAILY READINESS: Practical, measurable ways to assess readiness
3. WORKOUT TYPE: Clear workout type (e.g., Easy Run, Interval Session, Long Ride)
4. PURPOSE: The concrete purpose of this workout
5. STRUCTURE: A streamlined breakdown of the workout including:
   - Main sets with intensities and durations
   - Key workout parameters
6. INTENSITY GUIDANCE: Target zones, effort levels, or pace guidelines
7. ADAPTATION OPTIONS: Brief options for adjusting based on readiness

Begin with a concise overview of how this two-week block fits within the current training phase from your season plan.

IMPORTANT: Keep workout details more concise than in a one-week plan, focusing on the most important elements while maintaining enough detail for execution.

Focus on creating workouts that are:
- Specific but concise (key parameters only)
- Practical and executable
- Adaptable with options
- Connected to both immediate objectives and larger season goals

Use the following essential style guidelines:
- Use clear headings and subheadings
- Include emojis for key sections (🎯 for goals, 💪 for workouts, ⚡ for intensity, 🔄 for recovery)
- Use bullet points for clarity
- Include intensity guidance in bold
- Provide clear adaptation options for each workout"""

    WEEKLY_PLAN_HTML_FORMATTING = """Transform both the season plan and two-week training plan from markdown format into a professional HTML document.

## Season Plan Content
```markdown
{season_plan}
```

## Two-Week Plan Content
```markdown
{weekly_plan}
```

## Your Task
Convert the markdown content into a complete HTML document with the following features:

1. A clean, responsive design that works well on both desktop and mobile
2. Clear visual hierarchy with appropriate headings, spacing, and typography
3. Color-coding for different intensity levels (easy/recovery = green, moderate = yellow, high intensity = orange/red)
4. Proper semantic HTML5 structure
5. Basic CSS styling included in a <style> tag in the document head
6. A professional, athlete-focused aesthetic

The HTML should be a complete document including <!DOCTYPE html>, <html>, <head>, and <body> tags. Include appropriate meta tags for responsive design.

Design elements to include:
- A header section with the athlete's name and training period
- Two clearly separated sections:
  1. A high-level season plan overview at the top
  2. The detailed two-week plan below
- A visual representation of the season plan phases
- Day-by-day sections for the two-week plan
- Consistent formatting for workout details
- Appropriate use of color to indicate intensity levels

Return ONLY the complete HTML document without any markdown code blocks or explanations."""