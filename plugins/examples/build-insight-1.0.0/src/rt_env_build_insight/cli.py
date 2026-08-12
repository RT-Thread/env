def health_check():
    return 0


def main(argv, context):
    print("Build Insight 1.0.0")
    print("Workspace: %s" % context.workspace.root)
    return 0
