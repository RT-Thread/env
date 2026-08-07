def main(argv, context):
    try:
        from env.plugins.epack.cli import main as epack_main
    except ImportError:
        from plugins.epack.cli import main as epack_main
    return epack_main(argv, context)
