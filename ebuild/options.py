# -*- coding: utf-8 -*-
"""SCons option registry for the build system."""

from dataclasses import dataclass
from typing import List, Optional

from SCons.Script import AddOption


@dataclass(frozen=True)
class OptionSpec:
    flags: List[str]
    dest: str
    help: str
    action: Optional[str] = None
    opt_type: Optional[str] = None
    default: Optional[object] = None

    def apply(self) -> None:
        kwargs = {
            'dest': self.dest,
            'help': self.help,
        }
        if self.action:
            kwargs['action'] = self.action
        if self.opt_type:
            kwargs['type'] = self.opt_type
        if self.default is not None:
            kwargs['default'] = self.default
        AddOption(*self.flags, **kwargs)


class OptionRegistry:
    def __init__(self, specs: List[OptionSpec]) -> None:
        self.specs = specs
        self._registered = False

    def register(self) -> None:
        if self._registered:
            return
        for spec in self.specs:
            spec.apply()
        self._registered = True


_DEFAULT_SPECS = [
    OptionSpec(['--target'], 'target', 'set target project: mdk/mdk4/mdk5/cmake/vscode', opt_type='string'),
    OptionSpec(['--menuconfig'], 'menuconfig', 'open menuconfig for the project', action='store_true', default=False),
    OptionSpec(['--attach'], 'attach', 'view attachconfig or apply attach item', opt_type='string'),
    OptionSpec(['--verbose'], 'verbose', 'show full command lines', action='store_true', default=False),
    OptionSpec(['--cross-compile'], 'cross-compile', 'set CROSS_COMPILE prefix', opt_type='string'),
    OptionSpec(['--cpu'], 'cpu', 'set target CPU', opt_type='string'),
    OptionSpec(['--fpu'], 'fpu', 'set target FPU', opt_type='string'),
    OptionSpec(['--float-abi'], 'float-abi', 'set float ABI', opt_type='string'),
]

_REGISTRY = OptionRegistry(_DEFAULT_SPECS)


def AddOptions() -> None:
    _REGISTRY.register()
