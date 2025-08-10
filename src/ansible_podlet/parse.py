from collections import defaultdict, OrderedDict


class MultiKeyConfig:
    def __init__(self):
        self._data = defaultdict(lambda: defaultdict(list))
        self._current_section = None

    def data(self) -> dict:
        return self._data

    def read(self, filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    self._current_section = line[1:-1]
                elif '=' in line and self._current_section is not None:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    self._data[self._current_section][key].append(val)

    def write(self, filepath):
        with open(filepath, 'wt') as f:
            for section in self._data.keys():
                f.write(f"[{section}]\n")
                for key in self._data[section].keys():
                    for item in self._data[section][key]:
                        f.write(f"{key}={item}\n")
                f.write("\n")

    def getlist(self, section, key):
        return self._data.get(section, {}).get(key, [])

    def get(self, section, key):
        values = self.getlist(section, key)
        return values[-1] if values else None

    def sections(self):
        return list(self._data.keys())

    def items(self, section):
        return dict(self._data[section])
