"""Read generated .config files and render the existing C header format."""


def read_config(filename):
    with open(filename, 'r', encoding='utf-8') as source:
        return [line.lstrip(' ').rstrip('\r\n') for line in source]


def iter_settings(lines):
    for line in lines:
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        if separator:
            yield name, value


def find_setting(lines, name, default=None):
    return next((value for key, value in iter_settings(lines) if key == name), default)


def unquote(value):
    if value.startswith('"'):
        value = value[1:]
    if value.endswith('"'):
        value = value[:-1]
    return value


def is_package_metadata(name):
    return isinstance(name, str) and name.startswith('PKG_') and name.endswith(('_PATH', '_VER'))


def write_header(lines, filename, guard, includes=()):
    with open(filename, 'w', encoding='utf-8') as output:
        output.write('#ifndef %s\n#define %s\n\n' % (guard, guard))
        empty_line = True
        for line in lines:
            if not line:
                continue
            if line.startswith('#'):
                if line == '#':
                    if not empty_line:
                        output.write('\n')
                        empty_line = True
                    continue
                if not line.startswith('# CONFIG_'):
                    output.write('/*%s */\n' % line[1:])
                empty_line = False
                continue

            empty_line = False
            name, separator, value = line.partition('=')
            if not separator:
                continue
            if name.startswith('CONFIG_'):
                name = name[7:]
            if is_package_metadata(name):
                continue
            output.write('#define %s%s\n' % (name, '' if value == 'y' else ' ' + value))

        for include in includes:
            output.write('#include "%s"\n' % include)
        output.write('\n#endif\n')
