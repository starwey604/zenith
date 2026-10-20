"""Check the new candidate's packaging arithmetic and sequencing constraints."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from axial_feed import dimensions,frame


class AxialFeederTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads((ROOT/'config.json').read_text())
        cls.c=next(c for c in cls.cfg['candidates'] if c['id']=='axial5')
        cls.d=dimensions(cls.c,cls.cfg)

    def test_last_ball_fully_driven_to_wheel_handoff(self):
        d=self.d
        self.assertAlmostEqual(d['stroke_mm'],124.75)
        self.assertAlmostEqual(d['end_face_x_mm']+self.cfg['ball_diameter_mm']/2,-8)
        self.assertLess(d['unloaded_wheel_first_contact_ball_x_mm'],-8)
        # It remains behind the wheel-axis plane; the pusher is not a launcher.
        self.assertLess(d['end_face_x_mm'],0)

    def test_two_stages_fit_and_retract_clear_of_rotor(self):
        d=self.d
        self.assertGreaterEqual(d['remaining_overlap_mm'],25)
        self.assertAlmostEqual(2*d['each_stage_extension_mm'],d['stroke_mm'])
        self.assertGreaterEqual(d['retracted_tip_to_rear_cover_mm'],4)
        self.assertLess(math.hypot(16,16),28) # Stage-one square passes rear aperture.
        self.assertGreater(d['gate_clearance_when_open_mm'],0)

    def test_no_indexing_with_pusher_or_open_gate(self):
        samples=[frame(i/10,self.c,self.cfg) for i in range(1001)]
        for f in samples:
            if f['stroke_mm']>1e-8:
                self.assertFalse(f['indexing_allowed'])
                self.assertAlmostEqual(f['gate_open_fraction'],1)
            if f['indexing_allowed']:
                self.assertTrue(f['pusher_home'])
                self.assertTrue(f['gate_closed'])
        for a,b in zip(samples,samples[1:]):
            if abs(a['rotor_angle_deg']-b['rotor_angle_deg'])>1e-9:
                self.assertTrue(a['indexing_allowed'])
                self.assertTrue(b['indexing_allowed'])

    def test_contact_path_continuous_and_single_ball(self):
        samples=[frame(i/10,self.c,self.cfg) for i in range(1001)]
        for a,b in zip(samples,samples[1:]):
            self.assertLess(abs(a['stroke_mm']-b['stroke_mm']),2)
        for f in samples:
            if f['phase'] in (2,3) and f['ball_center_x_mm']>-120:
                self.assertAlmostEqual(f['ball_center_x_mm']-self.cfg['ball_diameter_mm']/2,self.d['home_face_x_mm']+f['stroke_mm'])
        self.assertFalse(frame(90,self.c,self.cfg)['ball_present'])
        self.assertEqual(frame(100,self.c,self.cfg)['stroke_mm'],0)


if __name__=='__main__':unittest.main()
