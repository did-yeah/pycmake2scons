import logging

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# add formatter to ch
ch.setFormatter(formatter)

app_logger = logging.getLogger("app")
app_logger.addHandler(ch)
app_logger.setLevel(logging.INFO)

main_logger = logging.getLogger("__main__")
main_logger.addHandler(ch)
main_logger.setLevel(logging.INFO)
