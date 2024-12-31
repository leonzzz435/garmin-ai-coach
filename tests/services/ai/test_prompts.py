import pytest
from services.ai.prompts import (
    system,
    data_extraction_prompt_01,
    data_extraction_prompt_02,
    training_generation_prompt,
    workout_system,
    workout_generation_prompt,
    advanced_thinking_prompt
)

class TestSystemPrompts:
    """Tests for system prompts."""

    def test_system_prompt_content(self):
        """Test that system prompt contains all required elements."""
        assert "professional" in system
        assert "exercise physiology" in system
        assert "sports science" in system
        assert "training patterns" in system
        assert "🏃‍♂️" in system  # running emoji
        assert "🚴" in system    # cycling emoji
        assert "🏊‍♂️" in system  # swimming emoji

    def test_workout_system_prompt_content(self):
        """Test that workout system prompt contains all required elements."""
        assert "professional" in workout_system
        assert "multisport training" in workout_system
        assert "exercise physiology" in workout_system
        assert "training load" in workout_system
        assert "🏊‍♂️" in workout_system  # swim emoji
        assert "🚴" in workout_system    # bike emoji
        assert "🏃‍♂️" in workout_system  # run emoji
        assert "💪" in workout_system    # strength emoji

class TestDataExtractionPrompts:
    """Tests for data extraction prompts."""

    def test_data_extraction_prompt_01_formatting(self):
        """Test formatting of data extraction prompt 01."""
        sample_data = "Sample athlete data"
        formatted_prompt = data_extraction_prompt_01 % sample_data
        
        assert "Recent Training Sessions" in formatted_prompt
        assert "Sample athlete data" in formatted_prompt
        assert "```athletes_data.md" in formatted_prompt
        assert "Activity Type" in formatted_prompt

    def test_data_extraction_prompt_02_formatting(self):
        """Test formatting of data extraction prompt 02."""
        sample_data = "Sample metrics data"
        formatted_prompt = data_extraction_prompt_02 % sample_data
        
        assert "Training load" in formatted_prompt
        assert "Recovery" in formatted_prompt
        assert "Sample metrics data" in formatted_prompt
        assert "```additional_info.md" in formatted_prompt
        assert "💪" in formatted_prompt  # Training load emoji
        assert "😴" in formatted_prompt  # Recovery emoji
        assert "🔋" in formatted_prompt  # Stress levels emoji
        assert "❤️" in formatted_prompt  # Heart rate emoji
        assert "🎯" in formatted_prompt  # Fitness indicators emoji

class TestTrainingPlanPrompts:
    """Tests for training plan generation prompts."""

    def test_training_generation_prompt_formatting(self):
        """Test formatting of training plan generation prompt."""
        athlete_info = "Sample athlete info"
        report = "Sample report"
        formatted_prompt = training_generation_prompt % (athlete_info, report)
        
        assert "Athletes Information.md" in formatted_prompt
        assert "Last 3 weeks - Athlete Report.md" in formatted_prompt
        assert "Sample athlete info" in formatted_prompt
        assert "Sample report" in formatted_prompt
        assert "2024/11/14" in formatted_prompt
        assert "2024/11/24" in formatted_prompt
        assert "Notion database" in formatted_prompt

    def test_training_prompt_required_fields(self):
        """Test that training prompt includes all required fields."""
        assert "Date:" in training_generation_prompt
        assert "Activity:" in training_generation_prompt
        assert "Duration:" in training_generation_prompt
        assert "Intensity:" in training_generation_prompt
        assert "Description:" in training_generation_prompt
        assert "Tags:" in training_generation_prompt
        assert "Athlete Notes:" in training_generation_prompt
        assert "Completed:" in training_generation_prompt

class TestWorkoutPrompts:
    """Tests for workout generation prompts."""

    def test_workout_generation_prompt_formatting(self):
        """Test formatting of workout generation prompt."""
        athlete_data = "Sample athlete data"
        formatted_prompt = workout_generation_prompt % athlete_data
        
        assert "```athlete_data.md" in formatted_prompt
        assert "Sample athlete data" in formatted_prompt
        assert "🏊‍♂️ **SWIM WORKOUT**" in formatted_prompt
        assert "🚴 **BIKE WORKOUT**" in formatted_prompt
        assert "🏃‍♂️ **RUN WORKOUT**" in formatted_prompt
        assert "💪 **STRENGTH WORKOUT**" in formatted_prompt

    def test_workout_prompt_structure(self):
        """Test that workout prompt includes all required sections."""
        assert "Duration:" in workout_generation_prompt
        assert "Focus:" in workout_generation_prompt
        assert "Structure:" in workout_generation_prompt
        assert "Warm-up:" in workout_generation_prompt
        assert "Main set:" in workout_generation_prompt
        assert "Cool-down:" in workout_generation_prompt
        assert "Tips:" in workout_generation_prompt

class TestAdvancedThinkingPrompt:
    """Tests for advanced thinking prompt."""

    def test_advanced_thinking_prompt_content(self):
        """Test that advanced thinking prompt contains all required elements."""
        assert "<step>" in advanced_thinking_prompt
        assert "<count>" in advanced_thinking_prompt
        assert "<reflection>" in advanced_thinking_prompt
        assert "<reward>" in advanced_thinking_prompt
        assert "<thinking>" in advanced_thinking_prompt
        assert "<answer>" in advanced_thinking_prompt
        assert "0.8+" in advanced_thinking_prompt
        assert "0.5-0.7" in advanced_thinking_prompt
        assert "Below 0.5" in advanced_thinking_prompt

    def test_advanced_thinking_steps(self):
        """Test that advanced thinking prompt includes all required steps."""
        steps = [
            "verification step",
            "counting or enumeration tasks",
            "common pitfalls",
            "question your initial results",
            "visual aids",
            "reflect on how they influenced"
        ]
        for step in steps:
            assert step in advanced_thinking_prompt

class TestEdgeCases:
    """Tests for edge cases in prompt handling."""

    def test_empty_data_formatting(self):
        """Test formatting prompts with empty data."""
        empty_data = ""
        
        # All these should work without raising exceptions
        data_extraction_prompt_01 % empty_data
        data_extraction_prompt_02 % empty_data
        workout_generation_prompt % empty_data
        training_generation_prompt % (empty_data, empty_data)

    def test_special_characters_formatting(self):
        """Test formatting prompts with special characters."""
        special_chars = "!@#$%^&*()\n\t"
        
        # All these should work without raising exceptions
        data_extraction_prompt_01 % special_chars
        data_extraction_prompt_02 % special_chars
        workout_generation_prompt % special_chars
        training_generation_prompt % (special_chars, special_chars)

    def test_unicode_characters_formatting(self):
        """Test formatting prompts with unicode characters."""
        unicode_chars = "🏃‍♂️🚴🏊‍♂️💪😴🔋❤️🎯"
        
        # All these should work without raising exceptions
        data_extraction_prompt_01 % unicode_chars
        data_extraction_prompt_02 % unicode_chars
        workout_generation_prompt % unicode_chars
        training_generation_prompt % (unicode_chars, unicode_chars)
