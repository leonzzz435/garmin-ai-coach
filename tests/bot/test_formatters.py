import pytest
from bot.formatters import escape_markdown, format_and_send_report

class TestMarkdownEscaping:
    """Tests for Markdown escaping functionality."""

    def test_escape_basic_characters(self):
        """Test escaping of basic special characters."""
        test_cases = [
            ('Hello_world', 'Hello\\_world'),
            ('(test)', '\\(test\\)'),
            ('[bracket]', '\\[bracket\\]'),
            ('test.com', 'test\\.com'),
            ('100!', '100\\!'),
            ('a+b=c', 'a\\+b\\=c'),
            ('|pipe|', '\\|pipe\\|'),
            ('~tilde~', '\\~tilde\\~'),
            ('`code`', '\\`code\\`'),
            ('>{quote}', '\\>{quote}'),
            ('#{hash}', '\\#{hash}'),
            ('{curly}', '\\{curly\\}'),
        ]
        
        for input_text, expected in test_cases:
            assert escape_markdown(input_text) == expected

    def test_escape_multiple_characters(self):
        """Test escaping of multiple special characters in one string."""
        input_text = "Hello_world! (Check) [this] out..."
        expected = "Hello\\_world\\! \\(Check\\) \\[this\\] out\\.\\.\\."
        assert escape_markdown(input_text) == expected

    def test_escape_backslash(self):
        """Test escaping of backslashes."""
        test_cases = [
            ('\\', '\\\\'),
            ('\\test\\', '\\\\test\\\\'),
            ('\\[test]\\', '\\\\\\[test\\]\\\\'),
        ]
        
        for input_text, expected in test_cases:
            assert escape_markdown(input_text) == expected

    def test_preserve_asterisks(self):
        """Test that asterisks are preserved for bold formatting."""
        test_cases = [
            ('*bold*', '*bold*'),
            ('**very bold**', '**very bold**'),
            ('*bold_text*', '*bold\\_text*'),
        ]
        
        for input_text, expected in test_cases:
            assert escape_markdown(input_text) == expected

    def test_escape_mixed_formatting(self):
        """Test escaping with mixed markdown formatting."""
        input_text = "*bold* _italic_ `code` [link](url)"
        expected = "*bold* \\_italic\\_ \\`code\\` \\[link\\]\\(url\\)"
        assert escape_markdown(input_text) == expected

    def test_escape_empty_string(self):
        """Test escaping empty string."""
        assert escape_markdown("") == ""

    def test_escape_special_sequences(self):
        """Test escaping of special character sequences."""
        test_cases = [
            ('\\n', '\\\\n'),  # Literal backslash + n
            ('\\t', '\\\\t'),  # Literal backslash + t
            ('\\r', '\\\\r'),  # Literal backslash + r
        ]
        
        for input_text, expected in test_cases:
            assert escape_markdown(input_text) == expected

class TestReportFormatting:
    """Tests for report formatting and splitting functionality."""

    def test_short_report(self):
        """Test formatting of a short report that doesn't need splitting."""
        report = "Short report with some *bold* text and [links](url)."
        chunks = format_and_send_report(report)
        
        assert len(chunks) == 1
        assert chunks[0] == "Short report with some *bold* text and \\[links\\]\\(url\\)\\."

    def test_long_report_splitting(self):
        """Test splitting of long reports."""
        # Create a report longer than 4000 characters
        long_report = "Test " * 1000  # 5000 characters
        chunks = format_and_send_report(long_report)
        
        assert len(chunks) == 2  # Should be split into 2 chunks
        assert len(chunks[0]) <= 4000
        assert len(chunks[1]) <= 4000
        assert chunks[0] + chunks[1] == escape_markdown(long_report)

    def test_exact_chunk_size(self):
        """Test report with exactly 4000 characters."""
        exact_report = "x" * 4000
        chunks = format_and_send_report(exact_report)
        
        assert len(chunks) == 1
        assert len(chunks[0]) == 4000

    def test_special_chars_at_chunk_boundary(self):
        """Test splitting with special characters at chunk boundaries."""
        # Create a report that will have special characters near the 4000-char boundary
        base_report = "x" * 3995  # Leave room for special sequence
        special_sequence = "[test]"
        report = base_report + special_sequence
        
        chunks = format_and_send_report(report)
        
        # Verify the special sequence wasn't split incorrectly
        assert all('\\[' not in chunk[:-2] for chunk in chunks)  # No partial escapes
        assert all('\\]' not in chunk[0:2] for chunk in chunks)  # No partial escapes

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        report = "Unicode test: 🏃‍♂️ 🚴 🏊‍♂️ 💪 with some *bold* text"
        chunks = format_and_send_report(report)
        
        assert len(chunks) == 1
        assert "🏃‍♂️" in chunks[0]
        assert "🚴" in chunks[0]
        assert "*bold*" in chunks[0]

    def test_newlines_and_whitespace(self):
        """Test handling of newlines and whitespace."""
        report = "Line 1\nLine 2\n\nLine 4\t\tTabbed"
        chunks = format_and_send_report(report)
        
        assert len(chunks) == 1
        assert "Line 1" in chunks[0]
        assert "Line 2" in chunks[0]
        assert "Line 4" in chunks[0]
        assert "Tabbed" in chunks[0]

    @pytest.mark.parametrize("length", [3999, 4000, 4001, 7999, 8000, 8001])
    def test_various_lengths(self, length):
        """Test reports of various lengths near chunk boundaries."""
        report = "x" * length
        chunks = format_and_send_report(report)
        
        # Verify all chunks are within limits
        assert all(len(chunk) <= 4000 for chunk in chunks)
        # Verify no content is lost
        assert ''.join(chunks) == report

    def test_empty_report(self):
        """Test handling of empty report."""
        chunks = format_and_send_report("")
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_markdown_table(self):
        """Test handling of markdown tables."""
        table = (
            "| Header 1 | Header 2 |\n"
            "|----------|----------|\n"
            "| Cell 1   | Cell 2   |"
        )
        chunks = format_and_send_report(table)
        
        assert len(chunks) == 1
        # Verify pipe characters are escaped
        assert "\\|" in chunks[0]
        # Verify dashes in table separator are escaped
        assert "\\-" in chunks[0]
