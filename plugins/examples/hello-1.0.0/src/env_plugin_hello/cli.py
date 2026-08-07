def health_check():
    return 0


def main(argv, context):
    print('Env plugin hello 1.0.0')
    print('User: %s' % context.display_name)
    print('Workspace: %s' % context.workspace.root)
    if argv:
        print('Arguments: %s' % ' '.join(argv))
    return 0
