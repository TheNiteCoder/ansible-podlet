
from argparse import ArgumentParser
from pathlib import Path
import shutil
import subprocess
from ansible_podlet.parse import MultiKeyConfig
from ansible_podlet.config import Config
import traceback
from typing import Optional, List


def get_role_directory_path(arg_path: Optional[str]) -> Optional[Path]:
    if arg_path is not None:
        arg_path = Path(arg_path)
        if arg_path.exists():
            return arg_path
    path = Path("./roles")
    if path.exists():
        return path
    return None


def run_rename(config: Config, service_name: str, containers: List[Path]):
    checked = containers[:]
    for to_check in checked:
        original_name = to_check.stem
        original_filename = to_check.stem + ".service"
        name_change = config.name_change(to_check.stem)
        if name_change is None:
            continue
        if name_change == '<auto>':
            name_change = f'{service_name}-{original_name}.container'
        if not name_change.endswith('.container'):
            name_change += '.container'
        containers = list(filter(lambda x: x is not to_check, containers))
        new_file = to_check.parent / name_change
        new_service_file = new_file.parent / f'{new_file.stem}.service'
        shutil.move(to_check, new_file)
        # Rename in files
        print(f'{original_filename} => {new_service_file.name}')
        for path in containers:
            quadlet = MultiKeyConfig()
            quadlet.read(path)
            requires = quadlet.get('Unit', 'Requires')
            if requires is not None:
                print(f'{requires}')
                requires = requires.split()
                requires = [new_service_file.name if c ==
                            str(original_filename) else c for c in requires]
                quadlet.data()['Unit']['Requires'] = [' '.join(requires)]
            after = quadlet.get('Unit', 'After')
            if after is not None:
                print(f'{after}')
                after = after.split()
                after = [new_service_file.name if c ==
                         str(original_filename) else c for c in after]
                quadlet.data()['Unit']['After'] = [' '.join(after)]
            quadlet.write(path)

        # add new file back in
        containers.append(new_file)


def generate_main():
    parser = ArgumentParser('dnalet-generate')
    parser.add_argument('docker_compose',
                        help='Docker Compose File to Convert')
    # args = parser.parse_args()


def fix_quadlet(config: Config, env_file_path: Path, quadlet_path: Path):
    # Move Environment Variables
    quadlet = MultiKeyConfig()
    quadlet.read(quadlet_path)
    variables = quadlet.getlist('Container', 'Environment')
    if 'Environment' in quadlet.data()['Container']:
        del quadlet.data()['Container']['Environment']
    with open(env_file_path, 'a') as f:
        for var in variables:
            f.write(f"\n# Variables from {str(quadlet_path.stem)}\n")
            f.write(f"{var}\n")
    # Rewrite Volumes
    print(quadlet_path.stem)
    rewrites = config.volume_rewrites(quadlet_path.stem)
    for idx, item in enumerate(quadlet.getlist('Container', 'Volume')):
        host_path, existing_container_path = item.split(':')
        for container_path in rewrites.keys():
            host_path = rewrites[container_path]
            host_path, flags = host_path.split(':')
            if existing_container_path == container_path:
                quadlet.data()['Container']['Volume'][idx] = f'{
                    host_path}:{container_path}:{flags}'

    new_env_file_path = config.env_file()
    if new_env_file_path is None:
        raise RuntimeError('general.env_file not specified')
    quadlet.data()['Container']['EnvironmentFile'] = [f'{new_env_file_path}']

    quadlet.write(quadlet_path)


def gen_config(quadlet_path: Path):
    quadlet_config = MultiKeyConfig()
    quadlet_config.read(quadlet_path)
    print(f'[container.{quadlet_path.stem}.volumes]')
    for volume in quadlet_config.getlist('Container', 'Volume'):
        host_path, container_path = volume.split(':')
        print(f'"{container_path}" = "{host_path}"')
    print('')


def main():
    parser = ArgumentParser('dnalet')
    parser.add_argument('compose_file', help='Compose File to Convert')
    parser.add_argument('--env-file', help='Env File to include')
    parser.add_argument('--service-name', help='Service name')
    parser.add_argument('--roles', help='Roles Directory')
    parser.add_argument('--output', help='Output Directory')
    parser.add_argument('--generate-config',
                        help='Generate Config', action='store_true')
    args = parser.parse_args()

    config_file = Config()
    config_file.read('dnalet.toml')

    output_path = None
    roles_path = get_role_directory_path(args.roles)
    if args.output:
        output_path = Path(args.output)
    elif roles_path and args.service_name:
        output_path = roles_path / args.service_name / 'templates'
    else:
        raise RuntimeError(
            # pylint: disable-next=line-too-long
            'no output directory specified either use --roles or --output or run next to ./roles with --service-name')

    try:
        build_dir = Path('/tmp/dnalet/build')
        if build_dir.is_dir():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)

        cmd = ['podlet', '--file',
               str(build_dir), 'compose',
               str(args.compose_file)]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise RuntimeError(f"failed to run podlet: {cmd}")

        new_env_file = build_dir / '.env'
        if args.env_file:
            shutil.copy(str(args.env_file), str(new_env_file))

        if not output_path.exists():
            output_path.mkdir(parents=True)

        network_file = build_dir / f"{args.service_name}.network"
        network_quadlet = MultiKeyConfig()
        network_quadlet.data()['Unit']['Description'] = [
            f'Network for {args.service_name}']
        network_quadlet.data()['Network']['Label'] = [
            f'app={args.service_name}']
        network_quadlet.write(network_file)
        for entry in build_dir.iterdir():
            if entry.is_file() and entry.suffix == ".container":
                if args.generate_config:
                    gen_config(entry)
                else:
                    fix_quadlet(config_file, new_env_file, entry)
                    # Inject network
                    quadlet = MultiKeyConfig()
                    quadlet.read(entry)
                    quadlet.data()['Container']['Network'] = [
                        f'{args.service_name}.network']
                    quadlet.data()['Service']['TimeoutStartSec'] = [900]
                    quadlet.write(entry)

        containers = list(filter(lambda x: x.suffix ==
                                 ".container", list(build_dir.iterdir())))
        run_rename(config_file, args.service_name, containers)

        for file in build_dir.iterdir():
            shutil.copy(file, output_path / file.name)
    except BaseException:
        traceback.print_exc()
    finally:
        if build_dir.exists() and build_dir.is_dir():
            shutil.rmtree(build_dir)
