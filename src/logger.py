'''
MCLabs Wiki RAG - API Logging

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
import os
import logging

'''
LOGGER SETUP
'''
class MCL_Logger():

	@staticmethod
	def setup_logger():
		'''
		# Logger Setup

		Sets up the logger for the API module.
		'''

		api_logger = logging.getLogger("MCL_API_Logger")
		api_logger.setLevel(logging.DEBUG)

		# Create console handler with environmental variable level
		console_handler = logging.StreamHandler()
		logging_level = getattr(logging, os.getenv("API_LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)
		console_handler.setLevel(logging_level)

		# Create formatter and add to handler
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
		console_handler.setFormatter(formatter)

		# Add handler to logger
		api_logger.addHandler(console_handler)

		return api_logger