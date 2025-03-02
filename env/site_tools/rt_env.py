import os
import json
import pprint
import sys

from SCons.Builder import Builder
from SCons.Action import Action
from SCons.Script import File
from SCons.Script import SConscript

def load_setting(project_json):
    # read .vscode/project.json
    try:
        data = open(project_json).read()
        j = json.loads(data)
    except:
        j = {}

    return j

def get_bsp_information(project_json):
    bsp_info = {}
    settings = load_setting(project_json)
    if 'RTT_ROOT' in settings and 'board' in settings:
        bsp_info['RTT_ROOT'] = os.path.abspath(settings['RTT_ROOT'])
        bsp_info['TOOLS_ROOT'] = os.path.join(bsp_info['RTT_ROOT'], 'tools')
        bsp_info['board'] = settings['board']
        bsp_info['BSP_ROOT'] = os.path.join(bsp_info['RTT_ROOT'], 'bsp', settings['board']['path'])
        if 'SDK_LIB' in settings:
            bsp_info['SDK_LIB'] = settings['SDK_LIB']
            if 'path' in bsp_info['SDK_LIB']:
                bsp_info['SDK_LIB']['path'] = bsp_info['SDK_LIB']['path'].replace('${RTT_ROOT}', bsp_info['RTT_ROOT'])

        # get components under bsp
        bsp_info['components'] = []
        list = os.listdir(bsp_info['BSP_ROOT'])
        for item in list:
            if os.path.isfile(os.path.join(bsp_info['BSP_ROOT'], item, 'SConscript')):
                # skip the group contains 'main.c'
                if os.path.isfile(os.path.join(bsp_info['BSP_ROOT'], item, 'main.c')):
                    continue
                else:
                    bsp_info['components'].append(os.path.join(bsp_info['BSP_ROOT'], item, 'SConscript'))

        # pprint.pprint(bsp_info['components'])

    return bsp_info

def build_variant_dir(name, prefix = None):
    name = name.removesuffix('/SConscript')
    name = name.removesuffix('\\SConscript')
    if prefix:
        name = 'build/' + prefix + '/' + os.path.basename(name)
    else:
        name = 'build/' + os.path.basename(name)

    return name

def apply_link_script(env, project_info):
    if 'board' in project_info and 'linker_script' in project_info['board']:
        if os.path.exists(project_info['board']['linker_script']):
            board_link_script = project_info['board']['linker_script']
        else:
            board_link_script = os.path.join(project_info['BSP_ROOT'], project_info['board']['linker_script'])

    link_flags = env['LINKFLAGS']
    parts = link_flags.split()
    try:
        index = parts.index('-T') 
        if index + 1 < len(parts):
            parts[index + 1] = board_link_script
    except ValueError:
        pass

    env['LINKFLAGS'] = ' '.join(parts)
    if env.GetDepend('RT_USING_SMART'):
        # use smart link.lds
        env['LINKFLAGS'] = env['LINKFLAGS'].replace('link.lds', 'link_smart.lds')

def apply_setting(env, project_json):
    project_info = get_bsp_information(project_json)

    RTT_ROOT = project_info['RTT_ROOT']

    sys.path = sys.path + [project_info['BSP_ROOT'], os.path.join(project_info['RTT_ROOT'], 'tools')]

    from building import PrepareBuilding
    import rtconfig

    env['CC']       = rtconfig.CC
    env['CFLAGS']   = rtconfig.CFLAGS
    env['CXX']      = rtconfig.CXX
    env['CXXFLAGS'] = rtconfig.CXXFLAGS
    env['AS']       = rtconfig.AS
    env['ASFLAGS']  = rtconfig.AFLAGS
    env['AR']       = rtconfig.AR
    env['ARFLAGS']  = '-rc',
    env['LINK']     = rtconfig.LINK
    env['LINKFLAGS']= rtconfig.LFLAGS

    env.PrependENVPath('PATH', rtconfig.EXEC_PATH)
    env['ASCOM'] = env['ASPPCOM']

    # export variables
    env.Export('env')
    env.Export('RTT_ROOT')
    env.Export('rtconfig')
    if 'SDK_LIB' in project_info:
        SDK_LIB = project_info['SDK_LIB']['path']
        SDK_LIB = os.path.abspath(SDK_LIB)
        env.Export('SDK_LIB')

    # prepare building environment
    objs = PrepareBuilding(env, RTT_ROOT)

    for item in project_info['components']:
        name = build_variant_dir(item)
        objs.extend(SConscript(item, variant_dir=name, duplicate=0))

    if 'SDK_LIB' in project_info:
        if 'components' in project_info['SDK_LIB']:
            sdk_path = SDK_LIB
            for item in project_info['SDK_LIB']['components']:
                item = os.path.join(sdk_path, item)
                name = build_variant_dir(item, 'sdk_libs')
                objs.extend(SConscript(item, variant_dir=name, duplicate=0))

    apply_link_script(env, project_info)

    return objs

def build_target(env, objs):
    from building import DoBuilding
    import rtconfig

    TARGET = 'rtthread.' + rtconfig.TARGET_EXT

    # make a building
    DoBuilding(TARGET, objs)
    return

def get_current_dir(env):
    conscript = File('SConscript')
    fn = conscript.rfile()
    path = os.path.dirname(fn.abspath)
    return path

def bridge(env):
    group   = []
    cwd     = get_current_dir(env)
    list    = os.listdir(cwd)

    for item in list:
        if os.path.isfile(os.path.join(cwd, item, 'SConscript')):
            group = group + SConscript(os.path.join(item, 'SConscript'))

    return group

def get_depend(env, depend):
    from building import GetDepend
    return GetDepend(depend)

def generate(env):
    env.AddMethod(bridge, 'Bridge')
    env.AddMethod(get_current_dir, 'GetCurrentDir')
    env.AddMethod(get_depend, 'GetDepend')
    env.AddMethod(apply_setting, 'ApplySetting')
    env.AddMethod(build_target, 'BuildTarget')

    return

def exists(env):
    return True
