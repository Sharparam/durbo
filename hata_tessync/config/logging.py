import logging
import logging.config
import toml

DEFAULT_LOG_CONFIG_PATH = 'logging.toml'


def setup_logging(config=None):
    if not config:
        config = DEFAULT_LOG_CONFIG_PATH

    if not isinstance(config, dict):
        config = toml.load(config)

    config = config.get('logging', config)

    logging.config.dictConfig(config)
