'''
MCLabs Common - Logging
'''

import os
import logging

class MCL_Logger():

	@staticmethod
	def setup_logger(logger_name: str):
		'''
		# Logger Setup

		Sets up the logger for a given module/service name.
		'''

		api_logger = logging.getLogger(logger_name)
		api_logger.setLevel(logging.DEBUG)

		# Create console handler with environmental variable level
		console_handler = logging.StreamHandler()
		logging_level = getattr(logging, os.getenv("API_LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)
		console_handler.setLevel(logging_level)

		# Create formatter and add to handler
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
		console_handler.setFormatter(formatter)

		# Add handler to logger if not already configured
		if not api_logger.handlers:
			api_logger.addHandler(console_handler)

		return api_logger
