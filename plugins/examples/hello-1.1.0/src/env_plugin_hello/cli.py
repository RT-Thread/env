import json


def health_check():
    return 0


def main(argv, context):
    if '--json' in argv:
        print(
            json.dumps(
                {
                    'plugin': context.plugin_id,
                    'version': context.plugin_version,
                    'workspace': context.workspace.root,
                },
                sort_keys=True,
            )
        )
    else:
        print('Env plugin hello 1.1.0')
        print('Workspace: %s' % context.workspace.root)
    return 0
