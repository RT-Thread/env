import os

DefaultEnvironment(tools=[])

env = Environment(tools = ['mingw', 'rt_env'], toolpath=['#/env/site_tools'])
objs = env.ApplySetting('.vscode/project.json')

env.BuildTarget(objs)
