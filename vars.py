# -*- coding:utf-8 -*-
import sys

env_vars = {}

def Export(var):
    f = sys._getframe(1).f_locals
    env_vars[var] = f[var]

def Import(var):
    return env_vars[var]
