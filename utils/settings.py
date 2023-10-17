from typing import Any, Optional


class Option:
    def __init__(self):
        self.owner: Optional[Settings] = None
        self.name: Optional[str] = None
        self.attr_name: Optional[str] = None

    def __set_name__(self, owner, name):
        self.owner = owner
        self.name = name
        self.attr_name = f"_{name}"

    def __get__(self, instance, owner):
        if hasattr(instance, self.attr_name):
            return getattr(instance, self.attr_name)
        if instance.master is not None:
            return getattr(instance.master, self.attr_name)


    def __set__(self, instance, value):
        ...

    def __delete__(self, instance):
        ...

class Settings:
    test = Option()

    def __init__(self, master: "Settings" = None):
        self.master = master
