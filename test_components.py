import tempfile, unittest
from tracking import IOUTracker, iou
from speed import SpeedEstimator
from storage import Storage

class ComponentTests(unittest.TestCase):
    def test_iou_and_tracking(self):
        self.assertGreater(iou((0,0,10,10),(2,2,10,10)),.5)
        t=IOUTracker(); a=t.update([type("D",(),{"bbox":(0,0,10,10)})()],0)
        b=t.update([type("D",(),{"bbox":(1,0,11,10)})()],1)
        self.assertEqual(a[0].track_id,b[0].track_id)
    def test_speed(self):
        self.assertAlmostEqual(SpeedEstimator(100).kmh((0,0),(100,0),1),3.6)
    def test_storage_path(self):
        self.assertTrue(Storage(tempfile.mkdtemp()).root.exists())
if __name__=="__main__": unittest.main()
