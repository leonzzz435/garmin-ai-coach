import unittest
from unittest.mock import Mock

from services.ai.langgraph.utils.message_utils import extract_text_content


class TestExtractTextContent(unittest.TestCase):

    def test_claude_with_thinking_blocks(self):
        mock_response = Mock()
        mock_response.content = [
            {
                'signature': 'EqUOCkYICBgCKkAIK...',
                'thinking': 'The user wants me to...',
                'type': 'thinking'
            },
            {
                'type': 'text',
                'text': '<!DOCTYPE html>\n<html>Clean HTML content</html>'
            }
        ]
        mock_response.content_blocks = [
            {'type': 'reasoning', 'reasoning': 'The user wants me to...'},
            {'type': 'text', 'text': '<!DOCTYPE html>\n<html>Clean HTML content</html>'}
        ]
        
        result = extract_text_content(mock_response)
        
        self.assertIn('<!DOCTYPE html>', result)
        self.assertIn('Clean HTML content', result)
        self.assertNotIn('thinking', result)
        self.assertNotIn('signature', result)
        self.assertNotIn('The user wants me to', result)

    def test_openai_with_reasoning_blocks(self):
        mock_response = Mock()
        mock_response.content = [
            {
                'id': 'rs_06204b6cd863...',
                'summary': [],
                'type': 'reasoning'
            },
            {
                'type': 'text',
                'text': '<!DOCTYPE html>\n<html>Clean HTML content</html>'
            }
        ]
        mock_response.content_blocks = [
            {'type': 'reasoning', 'id': 'rs_06204b6cd863...'},
            {'type': 'text', 'text': '<!DOCTYPE html>\n<html>Clean HTML content</html>'}
        ]
        
        result = extract_text_content(mock_response)
        
        self.assertIn('<!DOCTYPE html>', result)
        self.assertIn('Clean HTML content', result)
        self.assertNotIn('reasoning', result)
        self.assertNotIn('rs_06204b6cd863', result)

    def test_plain_string_response(self):
        mock_response = Mock()
        mock_response.content = '<!DOCTYPE html>\n<html>Simple response</html>'
        
        result = extract_text_content(mock_response)
        
        self.assertEqual(result, '<!DOCTYPE html>\n<html>Simple response</html>')

    def test_content_blocks_with_multiple_text_blocks(self):
        mock_response = Mock()
        mock_response.content = [
            {'type': 'text', 'text': 'Part 1 '},
            {'type': 'thinking', 'thinking': 'Some internal thought'},
            {'type': 'text', 'text': 'Part 2'}
        ]
        mock_response.content_blocks = [
            {'type': 'text', 'text': 'Part 1 '},
            {'type': 'reasoning', 'reasoning': 'Some internal thought'},
            {'type': 'text', 'text': 'Part 2'}
        ]
        
        result = extract_text_content(mock_response)
        
        self.assertEqual(result, 'Part 1 Part 2')
        self.assertNotIn('internal thought', result)

    def test_response_without_content_blocks_attribute(self):
        mock_response = Mock(spec=['content'])  # Only has content, no content_blocks
        mock_response.content = [
            {'type': 'thinking', 'thinking': 'Should be filtered'},
            {'type': 'text', 'text': 'Visible text'}
        ]
        
        result = extract_text_content(mock_response)
        
        self.assertEqual(result, 'Visible text')
        self.assertNotIn('Should be filtered', result)

    def test_response_content_blocks_raises_exception(self):
        mock_response = Mock()
        mock_response.content_blocks = Mock(side_effect=Exception("Block parsing error"))
        mock_response.content = [
            {'type': 'text', 'text': 'Fallback text'}
        ]
        
        result = extract_text_content(mock_response)
        
        self.assertEqual(result, 'Fallback text')

    def test_empty_content(self):
        mock_response = Mock()
        mock_response.content = []
        mock_response.content_blocks = []
        
        result = extract_text_content(mock_response)
        
        self.assertEqual(result, '[]')

    def test_raw_string_without_response_object(self):
        result = extract_text_content("Just a plain string")
        
        self.assertEqual(result, "Just a plain string")


if __name__ == '__main__':
    unittest.main()