from pygame import Vector2


class Transformation:
    def __init__(self, translation: Vector2 = None, scale: float = None):
        self.translation = translation or Vector2()
        self.scale = scale or 1

    def transform(self, ndr: Vector2, aspect_ratio: float):
        """ Transform NDR to fractal coordinates. """
        return Vector2(ndr.x * aspect_ratio, ndr.y) * self.scale + self.translation

    def inverseTransform(self, pos: Vector2, aspect_ratio: float):
        """ Transform fractal coordinates to NDR. """
        ndr = (pos - self.translation) / self.scale
        ndr.x /= aspect_ratio
        ndr.y /= -1
        return ndr

    def dumpJson(self) -> dict:
        return {
            "translation": (*self.translation,),
            "scale": self.scale
        }

    @classmethod
    def loadJson(cls, dat: dict):
        return cls(Vector2(*dat["translation"]), dat["scale"])
