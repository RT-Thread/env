import json
import os
import shutil
import zipfile

from plugins.epack.builder import build_project


TEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(TEST_ROOT, 'examples')
BUNDLED = os.path.join(TEST_ROOT, 'bundled')


def build_example(version, output, backend_format=None):
    project = os.path.join(EXAMPLES, 'hello-' + version)
    return build_project(project, output_directory=output, backend_format=backend_format)


def build_epack_plugin(output):
    return build_project(os.path.join(BUNDLED, 'epack'), output_directory=output)


def copy_project(source, destination):
    shutil.copytree(source, destination)
    return destination


def update_manifest(project, update):
    path = os.path.join(project, 'manifest.json')
    with open(path, 'r', encoding='utf-8') as source:
        manifest = json.load(source)
    update(manifest)
    with open(path, 'w', encoding='utf-8') as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write('\n')


def rewrite_zip(source, target, transform):
    with zipfile.ZipFile(source, 'r') as archive:
        files = dict((info.filename, archive.read(info)) for info in archive.infolist() if not info.is_dir())
    files = transform(files)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return target
