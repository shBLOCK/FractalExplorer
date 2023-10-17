from .transformation import Transformation
from .fractal import Fractal


class FractalView:
    def __init__(self, fractal: Fractal, name: str, view: Transformation):
        self.name = name
        self.view = view
        self.fractal = fractal

    def dumpJson(self) -> dict:
        return {
            "name": self.name,
            "view": self.view.dumpJson()
        }

    @classmethod
    def loadJson(cls, dat: dict):
        return cls(dat["name"], Transformation.loadJson(dat["view"]))
