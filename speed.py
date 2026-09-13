import math
class SpeedEstimator:
    def __init__(self, pixels_per_meter=180.0):
        self.ppm=float(pixels_per_meter)
    def kmh(self, old_center, new_center, dt):
        if dt <= 0: return 0.0
        px=math.hypot(new_center[0]-old_center[0],new_center[1]-old_center[1])
        return px/self.ppm/dt*3.6
