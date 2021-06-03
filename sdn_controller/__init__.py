from flask_restful import Api

from app import flaskAppInstance
from .Task import Task
from .GetMetrics import GetMetrics
from .ManualControl import ManualControl
#from .SDNM2M import SDNM2M


restServer = Api(flaskAppInstance)

restServer.add_resource(Task,"/api/v1.0/task")
restServer.add_resource(ManualControl,"/api/v1.0/mancontrol/<string:command>")
restServer.add_resource(GetMetrics,"/api/v1.0/getmetrics/<string:taskId>")