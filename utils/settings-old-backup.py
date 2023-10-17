from dataclasses import dataclass
from typing import Any

from utils.color_utils import Color, ColorGradient


@dataclass(slots=True)
class Option:
    default: Any

    def dumpJson(self, value):
        return value

    def loadJson(self, value):
        return value

@dataclass(slots=True)
class BoolOption(Option):
    default: bool

@dataclass(slots=True)
class FloatOption(Option):
    default: float

@dataclass(slots=True)
class IntOption(Option):
    default: int

@dataclass(slots=True)
class ColorOption(Option):
    default: Color

@dataclass(slots=True)
class GradientOption(Option):
    default: ColorGradient


class Settings:
    """ Overwrite _SETTINGS in subclasses to add settings options. """
    _SETTINGS: dict[str, Option] = {}

    def __init__(self, master_settings: "Settings" = None):
        assert len(self._SETTINGS) > 0

        self._master_settings = master_settings

        for name, opt in self._SETTINGS.items():
            setattr(self, f"_{name}", opt.default if master_settings is None else Ellipsis)

    def __getattr__(self, name):
        attr_name = f"_{name}"
        if not hasattr(self, attr_name):
            raise AttributeError(f"No option: '{name}' in '{type(self).__name__}'")

        attr = getattr(self, attr_name)
        if attr is Ellipsis:
            return self._master_settings.__getattr__(name)
        return attr

    def __setattr__(self, name, value):
        attr_name = f"_{name}"
        if not hasattr(self, attr_name):
            raise AttributeError(f"No option: '{name}' in '{type(self).__name__}'")

        setattr(self, attr_name, value)

    def __delattr__(self, name):
        attr_name = f"_{name}"
        if not hasattr(self, attr_name):
            raise AttributeError(f"No option: '{name}' in '{type(self).__name__}'")

        setattr(self, attr_name, Ellipsis)

    def dumpJson(self) -> dict:
        dat = {}
        for name,opt in self._SETTINGS.items():
            val = getattr(self, name)
            if val is Ellipsis:
                continue
            dat[name] = opt.dumpJson(val)
        return dat

    @classmethod
    def loadJson(cls, dat: dict):
        sts = cls()



class Test(Settings):
    _SETTINGS = {
        "a": BoolOption(default=False),
        "b": FloatOption(default=0),
    }

t = Test()
