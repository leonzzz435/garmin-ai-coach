# Tele-Garmin Agent System Improvement Tasks

This document tracks tasks for improving the Tele-Garmin agent system to reduce hallucinations and produce more compact, accurate outputs.

## Architecture Modifications

### Split Activity Agent into Two Specialized Agents
- [x] Create `ActivityDataAgent` configuration in `services/ai/flows/analysis/config/agents.yaml` (Due: 2025-05-07)
- [x] Create `activity_data_task` in `services/ai/flows/analysis/config/tasks.yaml` with factual focus (Due: 2025-05-07)
- [x] Modify `ActivityInterpreterAgent` (former ActivityAgent) to consume structured data (Due: 2025-05-08)
- [x] Update `analysis_flow.py` to incorporate the two-stage process (Due: 2025-05-10)
- [x] Create intermediate storage for activity summaries (Due: 2025-05-10)

### Implement Compact Synthesis Agent
- [ ] Modify `SynthesisAgent` configuration for brevity in `agents.yaml` (Due: 2025-05-12)
- [ ] Update synthesis task in `tasks.yaml` to include strict output guidelines (Due: 2025-05-14)
- [ ] Implement templates for concise output formatting (Due: 2025-05-15)
- [ ] Add validation checks for output length in the flow implementation (Due: 2025-05-16)

## Agent Configuration Updates

### ActivityDataAgent Implementation
- [x] Define role and goal focusing on objectivity (Due: 2025-05-08)
- [x] Create backstory emphasizing factual precision (Due: 2025-05-08)
- [x] Add expertise areas in data extraction and structuring (Due: 2025-05-09)
- [x] Implement specific language constraints to prevent speculation (Due: 2025-05-09)

### ActivityInterpreterAgent Modifications
- [x] Update backstory to emphasize working from structured data (Due: 2025-05-10)
- [x] Refine expertise areas for pattern recognition (Due: 2025-05-10)
- [x] Add specific instructions for respecting objective boundaries (Due: 2025-05-11)

### CompactSynthesisAgent Improvements
- [ ] Modify backstory to emphasize brevity and factual precision (Due: 2025-05-12)
- [ ] Update expertise to include information distillation (Due: 2025-05-13)
- [ ] Add specific guidance on avoiding verbosity (Due: 2025-05-13)

## Task Configuration Improvements

### Activity Data Task
- [x] Create task description with strict factual focus (Due: 2025-05-14)
- [x] Implement structured format templates (Due: 2025-05-15)
- [x] Add specific prohibitions against interpretation (Due: 2025-05-15)
- [x] Create example output formats for consistent results (Due: 2025-05-16)

### Activity Interpreter Task
- [x] Modify task to consume activity summaries rather than raw data (Due: 2025-05-16)
- [x] Implement strict word limits for each section (Due: 2025-05-17)
- [x] Create guidance for generating actionable recommendations (Due: 2025-05-18)
- [x] Add format requirements for weekly planning guidance (Due: 2025-05-18)

### Compact Synthesis Task
- [ ] Update task with specific word limits per section (Due: 2025-05-19)
- [ ] Implement prohibited language guidance (Due: 2025-05-20)
- [ ] Create templates for structured output (Due: 2025-05-20)
- [ ] Add validation requirements for output formats (Due: 2025-05-21)

## Testing Plan

### Unit Testing
- [ ] Create test fixtures with sample activity data (Due: 2025-05-21)
- [ ] Implement tests for ActivityDataAgent output format (Due: 2025-05-22)
- [ ] Create tests for word limit compliance (Due: 2025-05-23)
- [ ] Implement hallucination detection tests (Due: 2025-05-24)

### Integration Testing
- [ ] Test complete analysis flow with new agent structure (Due: 2025-05-25)
- [ ] Validate data transfer between agents (Due: 2025-05-26)
- [ ] Test integration with weekly planning flow (Due: 2025-05-27)
- [ ] Measure end-to-end performance (Due: 2025-05-27)

### User Feedback
- [ ] Create survey for comparing old vs new outputs (Due: 2025-05-28)
- [ ] Collect feedback from test users (Due: 2025-06-02)
- [ ] Analyze satisfaction metrics (Due: 2025-06-03)
- [ ] Implement adjustments based on feedback (Due: 2025-06-04)

## Deployment

### Staged Rollout
- [ ] Deploy to development environment (Due: 2025-06-04)
- [ ] Release to beta testers (Due: 2025-06-06)
- [ ] Monitor metrics for hallucination reduction (Due: 2025-06-08)
- [ ] Full production deployment (Due: 2025-06-09)

## Success Metrics Tracking

### Hallucination Reduction
- [ ] Establish baseline measurement of current outputs (Due: 2025-05-10)
- [ ] Implement automated scanning for uncertainty markers (Due: 2025-05-20)
- [ ] Compare before/after metrics (Due: 2025-06-10)
- [ ] Document findings and improvements (Due: 2025-06-12)

### Output Compactness
- [ ] Measure baseline word counts (Due: 2025-05-10)
- [ ] Track word count reduction per section (Due: 2025-06-10)
- [ ] Create visualization of size improvements (Due: 2025-06-12)

## Post-Implementation Review
- [ ] Conduct team retrospective (Due: 2025-06-15)
- [ ] Document lessons learned (Due: 2025-06-17)
- [ ] Create recommendations for further improvements (Due: 2025-06-20)
- [ ] Update project documentation (Due: 2025-06-22)