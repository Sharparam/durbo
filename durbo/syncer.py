import toml

# TODO: ?


class Syncer:
    def __init__(self, config_path: str) -> None:
        self.config = toml.load(config_path)
