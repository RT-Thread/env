"""Evaluate WebUI launch requirements against the current workspace."""

import glob
import os


def evaluate_launch_requirements(workspace, requirements):
    """Return a JSON-friendly diagnosis for a manifest requirement tree."""
    if requirements is None:
        return {
            'satisfied': True,
            'message': '',
            'tree': None,
        }

    result = _evaluate_node(os.path.abspath(workspace), requirements)
    return {
        'satisfied': result['satisfied'],
        'message': result['message'],
        'tree': result['tree'],
    }


def _evaluate_node(workspace, node):
    if 'type' in node:
        return _evaluate_path(workspace, node['type'], node['pattern'])
    if 'all' in node:
        return _evaluate_group(workspace, 'all', node['all'])
    if 'any' in node:
        return _evaluate_group(workspace, 'any', node['any'])
    return _evaluate_not(workspace, node['not'])


def _evaluate_path(workspace, kind, pattern):
    matches = []
    for candidate in glob.iglob(os.path.join(workspace, *pattern.split('/')), recursive=True):
        if kind == 'file' and not os.path.isfile(candidate):
            continue
        if kind == 'directory' and not os.path.isdir(candidate):
            continue
        relative = os.path.relpath(candidate, workspace).replace(os.sep, '/')
        if relative not in matches:
            matches.append(relative)
    matches.sort()
    satisfied = bool(matches)
    noun = 'file' if kind == 'file' else 'directory'
    message = '%s matching %s %s' % (
        noun,
        repr(pattern),
        'found' if satisfied else 'not found',
    )
    return {
        'satisfied': satisfied,
        'message': message,
        'tree': {
            'type': kind,
            'pattern': pattern,
            'satisfied': satisfied,
            'matches': matches,
            'message': message,
        },
    }


def _evaluate_group(workspace, operator, children):
    results = [_evaluate_node(workspace, child) for child in children]
    satisfied = all(item['satisfied'] for item in results) if operator == 'all' else any(
        item['satisfied'] for item in results
    )
    if operator == 'all':
        message = 'all requirements satisfied' if satisfied else 'one or more requirements are not satisfied'
    else:
        message = 'at least one requirement satisfied' if satisfied else 'none of the alternatives are satisfied'
    return {
        'satisfied': satisfied,
        'message': message,
        'tree': {
            'operator': operator,
            'satisfied': satisfied,
            'children': [item['tree'] for item in results],
            'message': message,
        },
    }


def _evaluate_not(workspace, child):
    result = _evaluate_node(workspace, child)
    satisfied = not result['satisfied']
    message = 'requirement is excluded' if satisfied else 'excluded requirement is present'
    return {
        'satisfied': satisfied,
        'message': message,
        'tree': {
            'operator': 'not',
            'satisfied': satisfied,
            'children': [result['tree']],
            'message': message,
        },
    }
