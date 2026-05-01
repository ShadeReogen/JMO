import json

VERSION = "alpha1.0"

_CONFIG_PATH = "config.json"
_data: dict = {}


def _load():
    global _data
    try:
        with open(_CONFIG_PATH) as f:
            _data = json.load(f)
    except Exception as e:
        print(f"[config] Failed to load: {e}")


def get(key, default=None):
    return _data.get(key, default)


def reload():
    _load()


_load()
