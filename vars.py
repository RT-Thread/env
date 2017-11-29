import sys

vars = {}

def Export(var):
    f = sys._getframe(1).f_locals
    vars[var] = f[var]

def Import(var):
    return vars[var]
