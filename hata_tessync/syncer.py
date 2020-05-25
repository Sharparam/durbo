import toml

from fbchat import Client as FbClient


class Syncer:
    def __init__(self, config_path):
        self.config = toml.load(config_path)
