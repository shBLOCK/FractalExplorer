from typing import List, Optional

from .func import FractalFunction
from .view import FractalView
from .transformation import Transformation


class Fractal:
    def __init__(self, name: str, func: FractalFunction, main_view: Optional[FractalView] = None):
        self.name = name
        self.func = func
        self.main_view = main_view or FractalView(self, "main", Transformation())
        self._views_except_main: List[FractalView] = []

    @property
    def views(self):
        """ Get all views including the main view, the main view is always the first element. """
        return (self.main_view, *self._views_except_main)

    def dumpJson(self) -> dict:
        return {
            "name": self.name,
            "func": self.func.dumpJson(),
            "views": [v.dumpJson() for v in self.views]
        }

    @classmethod
    def loadJson(cls, dat: dict):
        obj = cls(
            dat["name"],
            FractalFunction.loadJson(dat["func"])
        )
        obj._views_except_main = [FractalView.loadJson(v) for v in dat["views"]]
        for v in obj._views_except_main:
            v.fractal = obj
        obj.main_view = obj._views_except_main.pop(0)
        return obj
