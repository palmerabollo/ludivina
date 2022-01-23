import unittest
from utils import split_text


class TestSplitText(unittest.TestCase):
    def test_single_word(self):
        self.assertEquals(split_text('abc'), ['abc'])

    def test_spaces(self):
        self.assertEquals(split_text('abc def'), ['abc def'])
        self.assertEquals(split_text('abc  def'), ['abc def'])
        self.assertEquals(split_text('abc def '), ['abc def'])

    def test_multiple_lines(self):
        self.assertEquals(split_text('abc def', 3), ['abc', 'def'])
        self.assertEquals(split_text('abc def ', 3), ['abc', 'def'])
        self.assertEquals(split_text('abc def', 4), ['abc', 'def'])
        self.assertEquals(split_text('abc def', 5), ['abc', 'def'])
        self.assertEquals(split_text('abc def', 6), ['abc', 'def'])
        self.assertEquals(split_text('abc def', 7), ['abc def'])

    def test_long_words(self):
        self.assertEquals(split_text('abc def', 2), ['ab', 'de'])

    def test_line_breaks(self):
        self.assertEquals(split_text('abc\r\n\tdef'), ['abc def'])
