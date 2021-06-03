from flask_restful import Resource
import logging as logger
from .Metrics import Metrics
import requests


class GetMetrics(Resource):

    def get(self, taskId):
        logger.debug("Inside get method of taskById")

        m = Metrics()
        return_message = ''

        if(taskId == '5'):
            return_message = m.get_data(pod_name='sdnc')
        elif(taskId == '3'):
            return_message = m.get_prom_data()
            return_message = {"Total bandwidth transmitted (net1)": str(return_message[0]), "Total bandwidth received (net1)": str(return_message[1])}
            logger.debug("Total bandwidth was [t, r]: " + str(return_message))
        else:
            return_message = m.get_nodes()

        return return_message, 200

    def post(self, taskId):
        logger.debug("Inside post method of GetMetrics")

        return {"message": "Happy Friday!"}, 200
