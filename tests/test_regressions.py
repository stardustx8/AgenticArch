import unittest
from reference.core import validate_advice

class ScoreRegressionTests(unittest.TestCase):
    def check(self, scores, selected):
        return validate_advice(dict(schema_version=1,request_id='r',state_digest='a'*64,
            ordered_options=['luna_low','luna_high'],scores=scores,selected=selected,
            calibration='uncalibrated',provenance=dict(model_revision='rev',
            tokenizer_revision='rev',backend='synthetic',prompt_version='1')),
            request_id='r',state_digest='a'*64,ordered_options=['luna_low','luna_high'])
    def test_bad_sum(self):
        with self.assertRaises(ValueError):self.check(dict(luna_low=.2,luna_high=.6),'luna_high')
    def test_unknown_choice(self):
        with self.assertRaises(ValueError):self.check(dict(luna_low=.4,luna_high=.6),'UNKNOWN')
