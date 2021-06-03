from flask import Flask
import api.Controller as Controller
import logging as logger
import threading
logger.basicConfig(level="DEBUG")

flaskAppInstance = Flask(__name__)
controlInstance = None


@flaskAppInstance.route('/')
def connection_test():
    return 'Flask app is accessible.'

# Create instance of threaded SDN controller


def threaded_controller():
    logger.debug('Threaded controller initialized')
    controlInstance = Controller.SDNController()


# Start application by creating SDNc thread and the listening with Flask
if __name__ == '__main__':
    logger.debug('Starting the application')
    from api import *
    control_thread = threading.Thread(target=threaded_controller)
    control_thread.start()

    # Remove listening on all ports 0.0.0.0 in production
    flaskAppInstance.run(host="0.0.0.0", port=9002, debug=False, use_reloader=False)
