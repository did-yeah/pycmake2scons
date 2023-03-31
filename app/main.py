import logging
from pathlib import Path

import app.core.log_config
import app.util.scan

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    logger.info("start of main")
    src_path = Path("C:\\Users\\src")
    T = app.util.scan.toscons(src_path)
    T.scan()
    T.write_in_SconsScript()
