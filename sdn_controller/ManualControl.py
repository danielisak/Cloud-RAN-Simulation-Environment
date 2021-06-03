from flask_restful import Resource
import logging as logger
import app
import requests

class ManualControl(Resource):

    def get(self, command):
        logger.debug("Inside control method of manual control")
        
        c = app.get_controller()
        return_message = 'Came to get'

        if(command == '5'):
            return_message = c.configure_man()
        
        return return_message, 200

    def post(self, taskId):
        logger.debug("Inside post method of GetMetrics")

        return {"message" : "Happy Friday!"}, 200