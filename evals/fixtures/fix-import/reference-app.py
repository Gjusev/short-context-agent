import json


def load(path):
    with open(path) as fh:
        return json.load(fh)
