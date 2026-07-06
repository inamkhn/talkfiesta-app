import unittest
import string
import difflib

class TestKeyIssues(unittest.TestCase):
    def test_pronunciation_similarity(self):
        # Match test case
        target = "ubiquitous"
        transcript = "ubiquitous"
        normalized_target = target.lower().strip().translate(str.maketrans("", "", string.punctuation))
        normalized_transcript = transcript.lower().strip().translate(str.maketrans("", "", string.punctuation))
        
        self.assertEqual(normalized_target, normalized_transcript)
        
        # Substring match test case
        target2 = "ubiquitous"
        transcript2 = "the word ubiquitous was said"
        normalized_target2 = target2.lower().strip().translate(str.maketrans("", "", string.punctuation))
        normalized_transcript2 = transcript2.lower().strip().translate(str.maketrans("", "", string.punctuation))
        
        self.assertTrue(normalized_target2 in normalized_transcript2)
        
        # Typos similarity ratio calculation
        target3 = "apple"
        transcript3 = "aple"
        normalized_target3 = target3.lower().strip().translate(str.maketrans("", "", string.punctuation))
        normalized_transcript3 = transcript3.lower().strip().translate(str.maketrans("", "", string.punctuation))
        
        matcher = difflib.SequenceMatcher(None, normalized_target3, normalized_transcript3)
        score = int(matcher.ratio() * 100)
        self.assertGreater(score, 70)
        self.assertLess(score, 100)

if __name__ == "__main__":
    unittest.main()
