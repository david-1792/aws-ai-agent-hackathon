import logging

from sana.main import app

logging.basicConfig(level=logging.INFO)
logging.getLogger('bedrock_agentcore').setLevel(logging.WARNING)
logging.getLogger('strands').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('mcp').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info('Starting the Sana application...')
    app.run()
    logger.info('Sana application stopped.')