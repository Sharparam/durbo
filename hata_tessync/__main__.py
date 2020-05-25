import asyncio
import code
import logging

from .syncer import Syncer
from .config.logging import setup_logging

setup_logging()
log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


async def main():
    log.info('Starting up')
    syncer = Syncer('config.toml')
    # code.interact(local=dict(globals(), **locals()))

if __name__ == '__main__':
    log.debug('__name__ is __main__, running main function')
    loop.run_until_complete(main())
