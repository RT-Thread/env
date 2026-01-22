# -*- coding: utf-8 -*-
"""Minimal utilities for project generation."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PathUtils:
    @staticmethod
    def make_relative(origin: str, dest: str) -> str:
        origin = os.path.abspath(origin).replace('\\', '/')
        dest = os.path.abspath(dest).replace('\\', '/')

        origin_parts = PathUtils._split_all(os.path.normcase(origin))
        dest_parts = PathUtils._split_all(dest)

        if origin_parts[0] != os.path.normcase(dest_parts[0]):
            return dest

        index = 0
        for origin_seg, dest_seg in zip(origin_parts, dest_parts):
            if origin_seg != os.path.normcase(dest_seg):
                break
            index += 1

        segments = [os.pardir] * (len(origin_parts) - index)
        segments += dest_parts[index:]
        if not segments:
            return os.curdir
        return os.path.join(*segments)

    @staticmethod
    def _split_all(path: str) -> list:
        parts = []
        while path not in (os.curdir, os.pardir):
            prev = path
            path, child = os.path.split(prev)
            if path == prev:
                break
            parts.append(child)
        parts.append(path)
        parts.reverse()
        return parts


@dataclass(frozen=True)
class XmlUtils:
    @staticmethod
    def indent(elem, level: int = 0) -> None:
        indent_str = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent_str + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent_str
            for child in elem:
                XmlUtils.indent(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent_str
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent_str


def _make_path_relative(origin: str, dest: str) -> str:
    return PathUtils.make_relative(origin, dest)


def xml_indent(elem, level: int = 0) -> None:
    XmlUtils.indent(elem, level)
