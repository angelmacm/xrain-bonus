import logging

# Create a logger
loggingInstance = logging.getLogger(__name__)
loggingInstance.setLevel(logging.DEBUG)  # Set the desired logging level

# Create a file handler
file_handler = logging.FileHandler("xrpl-claims.log")
file_handler.setLevel(logging.DEBUG)  # Set the desired logging level for the file

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set the desired logging level for the console

# Create a formatter and set it for both handlers
formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s: %(module)s\\%(funcName)s    %(message)s"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
loggingInstance.addHandler(file_handler)
loggingInstance.addHandler(console_handler)
