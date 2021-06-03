import logging as logger
import pulp
import json
import os
import subprocess
from pulp import LpMaximize, LpProblem, LpStatus, lpSum, LpVariable


class Optimizer():
    def __init__(self):

        # Läs in qos_req
        logger.warning('Optimizer INIT method')

        # Ladda på med margin vid inläsning
        self.qos_metrics = {
            "gold": {"qos_fails": 0, "margin": 0.0},
            "silver": {"qos_fails": 0, "margin": 0.0},
            "bronze": {"qos_fails": 0, "margin": 0.0}
        }

        self.qos_req = ''
        self.lowest_bw = 5
        self.total_bw = 100

        try:
            # Load QoS requirements from file
            config_file = 'api/qos-req.json'
            f = open(config_file, "r")
            self.qos_req = json.loads(f.read())
            logger.debug("QoS requirements read from JSON file...")
        except:
            current_dir = os.getcwd()
            logger.error("Could not find qos-req.json file in " + current_dir)
            logger.warning("Backup QoS requirements loaded...")

            # Backup QoS requirements if JSON loading fails
            self.qos_req = {
                "gold": {"qos_priority": 10, "max_pkt_loss": 1E-2, "min_margin": 0.05, "max_margin": 0.20},
                "silver": {"qos_priority": 20, "max_pkt_loss": 1E-2, "min_margin": 0.05, "max_margin": 0.10},
                "bronze": {"qos_priority": 30, "max_pkt_loss": 1E-2, "min_margin": 0.05, "max_margin": 0.15}
            }

        GOLD_MARGIN = subprocess.check_output('echo $GOLD_MARGIN', shell=True).decode('utf-8').strip()
        SILVER_MARGIN = subprocess.check_output('echo $SILVER_MARGIN', shell=True).decode('utf-8').strip()
        BRONZE_MARGIN = subprocess.check_output('echo $BRONZE_MARGIN', shell=True).decode('utf-8').strip()

        # Set margins from YAML file and env vars
        if GOLD_MARGIN != '' and SILVER_MARGIN != '' and BRONZE_MARGIN != '':
            self.qos_metrics['gold']['margin'] = float(GOLD_MARGIN)
            self.qos_metrics['silver']['margin'] = float(SILVER_MARGIN)
            self.qos_metrics['bronze']['margin'] = float(BRONZE_MARGIN)
        else:
            # Set qos_metrics margin to min_margin defined in the QoS requirements
            self.qos_metrics['gold']['margin'] = self.qos_req['gold']['min_margin']
            self.qos_metrics['silver']['margin'] = self.qos_req['silver']['min_margin']
            self.qos_metrics['bronze']['margin'] = self.qos_req['bronze']['min_margin']

    def optimize_network(self, system_metrics):

        # STEPS TO MAKE MORE COMPLEX

        # 1 Add margin calculation based on qos_upholding few time steps back
        # 2 Use data from multple time steps

        logger.warning('In optimizer class...')

        # Check if QoS for packet loss is upheld, if not increase margin for that interface
        # for interface, metrics_list in self.qos_metrics.items():
        #     logger.debug('')
        #     current_pkt_loss = system_metrics['network'][interface]['packet_loss'][0]
        #     max_pkt_loss = self.qos_req[interface]['max_pkt_loss']

        #     logger.debug(str('Current margin for ' + interface + ':').ljust(40) + str(metrics_list['margin']))
        #     logger.debug('')
        #     logger.debug(str('Current pkt_loss for ' + interface + ':').ljust(40) + str(system_metrics['network'][interface]['packet_loss'][0]))
        #     logger.debug(str('Max_allowed_pkt_loss for ').ljust(40) + str(self.qos_req[interface]['max_pkt_loss']))

        #     # Check if QoS requirement for packet_loss is broken
        #     if current_pkt_loss > max_pkt_loss:
        #         logger.debug('More loss than allowed!')

        #         # Is current margin lower than max margin, increase with 5%
        #         if self.qos_metrics[interface]['margin'] < self.qos_req[interface]['max_margin']:
        #             self.qos_metrics[interface]['margin'] = round(self.qos_metrics[interface]['margin'] + 0.05, 3)

        #     # If packet loss qos is not broken, is it above min_margin and can be decreased
        #     elif self.qos_metrics[interface]['margin'] > self.qos_req[interface]['min_margin']:
        #         self.qos_metrics[interface]['margin'] = round(self.qos_metrics[interface]['margin'] - 0.01, 3)

        model = LpProblem(name="bandwidth-optimizing", sense=LpMaximize)

        current_demand = []

        # Read current bandwidth demand from system_metrics and add margin from qos_metrics, for each interface
        for interface, _ in system_metrics['network'].items():
            interface_demand = round(system_metrics['network'][interface]['tx_bw'][0]*(1+self.qos_metrics[interface]['margin'])/1E6, 3)

            # If more than two values in bw vector and increasing add derivate to demand
            if (len(system_metrics['network'][interface]['tx_bw']) > 1):
                bw_increase = round((system_metrics['network'][interface]['tx_bw'][0] - system_metrics['network'][interface]['tx_bw'][1])/1E6, 3)
                if bw_increase > 0:  # How much increase is needed to add derivate
                    interface_demand += bw_increase

            current_demand.append(interface_demand)
            logger.debug(str("Demanded w/ margin " + interface + ':').ljust(25) + str(interface_demand))
            logger.debug(str("Demanded " + interface + ':').ljust(25) + str(round(system_metrics['network'][interface]['tx_bw'][0], 3)))

        # x1, x2 and x3 are continuous non-negative variables.
        x1 = LpVariable(name="x1", lowBound=0, upBound=current_demand[0], cat='Continous')  # gold
        x2 = LpVariable(name="x2", lowBound=0, upBound=current_demand[1], cat='Continous')  # silver
        x3 = LpVariable(name="x3", lowBound=0, upBound=current_demand[2], cat='Continous')  # bronze

        # Non-GBR can suffer package loss under congestion
        # x1 5QI: 69 Mission Critical delay sensative signaling, latency 60ms, prio 5, package loss 1E-6
        # x2 5QI: 3 Real Time Gaming/V2X, latency 50 ms, prio 30, packet loss 1E-3
        # x3 5QI: 6, Video (Buffered) NETFLIX, latency 300 ms, prio 60, packet loss 1E-6

        prio_x1 = 4-self.qos_req['gold']['qos_priority']
        prio_x2 = 4-self.qos_req['silver']['qos_priority']
        prio_x3 = 4-self.qos_req['bronze']['qos_priority']

        # Add the constraints to the model
        model += (x1 + x2 + x3 <= self.total_bw, "Bandwidth")

        # Add goal function
        model += lpSum([prio_x1*x1, prio_x2*x2, prio_x3*x3])

        # Solve the problem, uses CBC solver, message is off
        status = model.solve(pulp.get_solver('PULP_CBC_CMD', msg=False))

        # Logg result from optimization
        for var in model.variables():
            logger.info(str(var.name)+':'+str(var.value()))

        new_config = {
            "metadata": {},
            "interfaces": {
                "gold": {
                    "bandwidth": 120,
                    "burst": 10,
                    "margin": 0.1
                },
                "silver": {
                    "bandwidth": 140,
                    "burst": 20,
                    "margin": 0.1
                },
                "bronze": {
                    "bandwidth": 200,
                    "burst": 30,
                    "margin": 0.1
                }
            }
        }

        interfaces = ['gold', 'silver', 'bronze']
        for i, interface in enumerate(interfaces):
            new_bw = max(model.variables()[i].value(), self.lowest_bw)
            new_burst = new_bw/10
            new_margin = self.qos_metrics[interface]['margin']

            new_config['interfaces'][interface]['bandwidth'] = new_bw
            new_config['interfaces'][interface]['burst'] = new_burst
            new_config['interfaces'][interface]['margin'] = new_margin
            logger.warning(str('New ' + interface + ' bw setting was: ').ljust(25) + str(new_bw))
            logger.warning(str('New ' + interface + ' burst setting was: ').ljust(25) + str(new_burst))

        return new_config, self.qos_metrics
