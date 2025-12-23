# -*- coding: utf-8 -*-
"""Ebuild package entrypoint."""

from .system import BuildSystem, prepare


def PrepareBuilding(env, project_root=None, proj_config=None):
    return prepare(env, project_root, config_module=proj_config)


def DoBuilding(env, target, objs=None):
    build = getattr(env, '_BuildSystem', None) or BuildSystem.current()
    if not build:
        raise RuntimeError("BuildSystem not initialized.")
    return build.do_building(target, objs)


__all__ = ['BuildSystem', 'prepare', 'PrepareBuilding', 'DoBuilding']
