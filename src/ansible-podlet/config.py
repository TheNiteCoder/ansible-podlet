
from tomlkit import dumps, parse, table
from typing import Union
from pathlib import Path


class Config:
    _doc: table

    def __init__(self):
        self._doc = None

    def read(self, filepath: Union[str, Path]):
        with open(filepath, 'rt') as f:
            self._doc = parse(f.read())

    def write(self, filepath: Union[str, Path]):
        with open(filepath, 'wt') as f:
            f.write(dumps(self._doc))

    def volume_rewrites(self, container_name: str):
        if not self._doc:
            return {}
        if ('container' in self._doc
                and container_name in self._doc['container']
                and 'volumes' in self._doc['container'][container_name]):
            return self._doc['container'][container_name]['volumes']
        return {}

    def env_file(self):
        if not self._doc:
            return None
        if ('general' in self._doc
                and 'env_file' in self._doc['general']):
            return self._doc['general']['env_file']
        return None

    def name_change(self, container_name: str):
        if not self._doc:
            return None
        if ('container' in self._doc
                and container_name in self._doc['container']
                and 'name' in self._doc['container'][container_name]):
            return self._doc['container'][container_name]['name']
        return None
