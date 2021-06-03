from .Metrics import Metrics
from .Optimizer import Optimizer
import logging as logger
import time
import threading
import datetime
import os
import subprocess
import json
import functools
import math
import requests


class SDNController:

    def controlling(self):

        while(True):
            # Thread sleep is control frequency
            time.sleep(self.control_interval)

            # Collect metrics and act with observe()
            self.observe()

            if self.DEBUG:
                logger.debug('In control loop...')
                logger.debug('Time: ' + str(datetime.datetime.now()))
                logger.debug('Current thread: ' + str(threading.currentThread().getName()))

    def __init__(self):

        self.DEBUG = False
        # Load config file for OVS
        config_file = './ovs_reconfig.json'
        f = open(config_file, "r")

        self.ovs_configuration = json.loads(f.read())
        self.stored_values = 6

        SDNC_CONTROL_INTERVAL = subprocess.check_output('echo $SDNC_CONTROL_INTERVAL', shell=True).decode('utf-8').strip()

        # Set SDNC control interval from environment variable
        if SDNC_CONTROL_INTERVAL != '':
            self.control_interval = int(SDNC_CONTROL_INTERVAL)
        else:
            self.control_interval = 10

        # NON-DUMMY
        # Send config from file to OVS agent
        self.send_config_to_agent(self.ovs_configuration)

        # Create instance of metrics, save nodes, define interface names
        self.m = Metrics()
        self.optimizer = Optimizer()
        self.nodes = self.m.get_nodes()
        self.interface_names = ['enp0s8', 'enp0s9', 'enp0s10']

        if self.DEBUG:
            logger.debug(self.nodes)

        # Intialize database
        self.observe(start=True)

        # Start control loop
        self.controlling()

    def send_config_to_agent(self, config_dict):

        # Static IP adress and port to set OVS configuration through agent
        ovs_agent_host = '20.20.0.105'
        ovs_agent_port = '9002'
        ovs_url = 'http://'+ovs_agent_host+':'+ovs_agent_port+'/api/connect'

        # POST config to OVS with request
        response = requests.post(ovs_url, json=config_dict)

        # if self.DEBUG:
        #     logger.debug("OVS reconfigure request response:" + str(response))

    def init_database(self):
        self.current_metrics = {
            "ovs": {
                "gold": {"tx_bytes": [0], "rx_bytes": [0], "tx_packets": [0], "rx_packets": [0]},
                "silver": {"tx_bytes": [0], "rx_bytes": [0], "tx_packets": [0], "rx_packets": [0]},
                "bronze": {"tx_bytes": [0], "rx_bytes": [0], "tx_packets": [0], "rx_packets": [0]}
            },
            "network": {
                "gold": {"tx_bw": [0], "rx_bw": [0], 'packet_drop': [0], 'packet_loss': [0]},
                "silver": {"tx_bw": [0], "rx_bw": [0], 'packet_drop': [0], 'packet_loss': [0]},
                "bronze": {"tx_bw": [0], "rx_bw": [0], 'packet_drop': [0], 'packet_loss': [0]}
            }
        }

        self.start_metrics = {
            'ovs': {
                'gold': {
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'tx_packets': 0,
                    'rx_packets': 0
                },
                'silver': {
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'tx_packets': 0,
                    'rx_packets': 0
                },
                'bronze': {
                    'tx_bytes': 0,
                    'rx_bytes': 0,
                    'tx_packets': 0,
                    'rx_packets': 0
                }
            }
        }

        self.last_config = {
            "metadata": {},
            "interfaces": {
                "gold": {
                    "bandwidth": 5,
                    "burst": 1,
                    "margin": 0.0
                },
                "silver": {
                    "bandwidth": 5,
                    "burst": 1,
                    "margin": 0.0
                },
                "bronze": {
                    "bandwidth": 5,
                    "burst": 30,
                    "margin": 0.0
                }
            }
        }

    def observe(self, start=False):
        # Get transmitted network bytes per interface from OVS
        new_metrics = self.m.get_ovs_metrics()
        logger.debug('The return from m.get_ovs_metrics was: ' + str(new_metrics))

        self.update_database(new_metrics, start)
        self.call_optimizer()

        if self.DEBUG:
            self.pretty_logger(ugly_metrics=self.current_metrics)

    # Updates datebase of ovs and calls functions to calculate bandwidth and package drop
    # Takes in new_metrics frame received from ovg_agent and start boolean value to initiate database
    def update_database(self, new_metrics, start=False):
        # Select ovs-metrics from frame, legacy...
        source = 'ovs'
        interface_dict = new_metrics[source]

        if start:
            self.init_database()
            if self.DEBUG:
                logger.info('Database initialized.')

        # Iterate over each interface of new 'OVS-metrics' and insert new metric in to vector of current_metrics
        for interface, metric_dict in interface_dict.items():
            # Iterate over each metric
            for metric, _ in metric_dict.items():
                # If start is passsed, init start_metrics and do not subtract initial value
                if start:

                    new_metric = new_metrics[source][interface][metric]
                    self.start_metrics[source][interface][metric] = new_metric
                # If not start, subtract values stored in start_metrics matrix and insert into current_metrics
                else:
                    new_metric = new_metrics[source][interface][metric]-self.start_metrics[source][interface][metric]
                    self.current_metrics[source][interface][metric].insert(0, new_metric)

                # If number of stored values exceed the number specified in __init__, pop oldest
                if len(self.current_metrics[source][interface][metric]) > self.stored_values:
                    self.current_metrics[source][interface][metric].pop()

        # Call function to calculate OVS bandwidth
        if not start:
            self.calculate_ovs_bw(new_metrics)
            self.calculate_packet_drops()

    # Calculate OVS bandwidth by subtracting bytes on ingress interface between two time steps
    def calculate_ovs_bw(self, new_metrics):
        # Check that there are old values for bytes before bw calculation
        if len(self.current_metrics['ovs']['gold']['rx_bytes']) < 2:
            logger.error('Less than 2 values in OVS bytes list. Bandwidth cannot be calculated.')
            return

        # Extract current bandwidth by trafic direction and interface
        def extract_bw(trafic_direction, interface):
            new_bytes = new_metrics['ovs'][interface][trafic_direction] - self.start_metrics['ovs'][interface][trafic_direction]
            prev_bytes = self.current_metrics['ovs'][interface][trafic_direction][1]
            current_bw = round((new_bytes - prev_bytes)/self.control_interval*8, 2)
            return current_bw

        # Iterate over each interface and call method above
        for interface, metric_dict in new_metrics['ovs'].items():
            self.current_metrics['network'][interface]['rx_bw'].insert(0, extract_bw('rx_bytes', interface))
            self.current_metrics['network'][interface]['tx_bw'].insert(0, extract_bw('tx_bytes', interface))

            # if number of stored values exceed the number specified in __init__, pop oldest
            if len(self.current_metrics['network'][interface]['tx_bw']) > self.stored_values:
                self.current_metrics['network'][interface]['tx_bw'].pop()
                self.current_metrics['network'][interface]['rx_bw'].pop()

    # Calculate packet drop and packet drop rate by subtracting packets recieved on ingress interface of OVS
    # with packets sent on OVS egress interface (in direction of iperf server)

    def calculate_packet_drops(self):
        # Check that there are at least to values for tx_packets
        if len(self.current_metrics['ovs']['gold']['tx_packets']) < 2:
            logger.error('Less than 2 values in OVS packets list. Packet loss cannot be calculated.')
            return

        # Iterate over each interface, extract packets for tx and rx, calculate new_total_dropped
        for interface, _ in self.current_metrics['ovs'].items():
            tx_packets = self.current_metrics['ovs'][interface]['tx_packets'][0]
            rx_packets = self.current_metrics['ovs'][interface]['rx_packets'][0]
            new_total_dropped = tx_packets - rx_packets

            tx_packets_last_itr = self.current_metrics['ovs'][interface]['tx_packets'][0] - self.current_metrics['ovs'][interface]['tx_packets'][1]
            rx_packets_last_itr = self.current_metrics['ovs'][interface]['rx_packets'][0] - self.current_metrics['ovs'][interface]['rx_packets'][1]

            alt_dropped_last_itr = abs(tx_packets_last_itr - rx_packets_last_itr)

            no_packets_sent = (tx_packets_last_itr == 0)
            negative_fluct = (new_total_dropped < self.current_metrics['network'][interface]['packet_drop'][0])

            # Avoid negative packet drops and negative total packets dropped caused by rx_packets for router solliciation and other router functions
            if no_packets_sent:
                too_small_packet_change = False
            else:
                too_small_packet_change = (alt_dropped_last_itr/tx_packets_last_itr < 1E-3)

            if no_packets_sent or negative_fluct or too_small_packet_change:
                new_total_dropped = self.current_metrics['network'][interface]['packet_drop'][0]

            # Insert packet drop into current_metrics
            self.current_metrics['network'][interface]['packet_drop'].insert(0, new_total_dropped)

            # Calculate drop rate by dividing dropped packets last iteration by those sent
            last_total_dropped = self.current_metrics['network'][interface]['packet_drop'][1]
            dropped_last_itr = new_total_dropped - last_total_dropped
            sent_last_itr = tx_packets - self.current_metrics['ovs'][interface]['tx_packets'][1]

            # Drop rate is rounded to 3 decimals, to handle QoS requirements w/ packet drop requirements less than 1E-2
            if sent_last_itr != 0:
                drop_rate = round(dropped_last_itr/sent_last_itr, 3)
            else:
                drop_rate = 0

            self.current_metrics['network'][interface]['packet_loss'].insert(0, drop_rate)

            # if number of stored values exceed the number specified in __init__, pop oldest
            if len(self.current_metrics['network'][interface]['packet_drop']) > self.stored_values:
                self.current_metrics['network'][interface]['packet_drop'].pop()
                self.current_metrics['network'][interface]['packet_loss'].pop()

    # Algorithm for optimizing network bandwidth usage, uses currents metrics and outputs config file
    def call_optimizer(self):
        if self.DEBUG:
            logger.debug("In optimizer function...")
            #logger.info("In optimizer the current metrics were: \n" + str(self.current_metrics))

        new_config, qos_metrics = self.optimizer.optimize_network(self.current_metrics)

        # Write input and output from optimizer to CSV-file
        self.write_csv(self.current_metrics, new_config, qos_metrics)
        # NON-DUMMY
        self.send_config_to_agent(new_config)

    # Converts ugly metrics in JSON format to readable logger prints
    def pretty_logger(self, ugly_metrics):
        start_pad = 10
        mid_pad = 25

        for source, interfaces in ugly_metrics.items():
            print_labels = source.capitalize().ljust(start_pad)
            for interface_name, metrics_list in interfaces.items():
                for metric_name, metric in metrics_list.items():
                    print_labels += metric_name.ljust(25)
                break
            logger.info(print_labels)
            logger.info(''.ljust(4*mid_pad, '-'))

            for interface_name, metrics_list in interfaces.items():
                print_metrics = ''
                print_metrics += interface_name.ljust(start_pad)
                print_list = interface_name.ljust(start_pad)

                row_list = [[]]
                row = 0
                rows_to_print = 1

                for metric_name, metric in metrics_list.items():
                    max_number = 0
                    row_list.append(list(metric))

                max_stored_values = max(list(map(lambda a: len(a), row_list)))
                max_number_of_param = len(row_list)
                cols = max_number_of_param
                rows = max_stored_values
                mat = [0]*rows

                # Create matrix
                for i in range(rows):
                    mat[i] = [0]*cols

                # Transpose metrics from row_list and store in mat
                for i in range(0, len(row_list)):
                    for j, num in enumerate(row_list[i]):
                        mat[j][i] = num

                # Iterate over transposed metrics and add to print_list
                for i in range(len(mat)):
                    for j in range(1, len(mat[0])):
                        print_list += str(mat[i][j]).ljust(25)

                    logger.info(print_list)
                    print_list = str('['+str(i+1)+']').ljust(10)
                print_list = ''
                logger.info(''.ljust(4*mid_pad, '.'))

            logger.info('\n')

    # Write CSV file from optimize_network() with input system metrics and output new_config
    def write_csv(self, system_metrics, new_config, qos_metrics):

        # Create arrays to store labels and data
        labels = []
        data = []

        # For each metric except packet_drop in system_metrics, append to labels and data arrays
        for interface, interface_list in system_metrics['network'].items():
            for metric_name, metrics_list in interface_list.items():
                # If the next metric is packet_drop sneak in rx_packets from ovs metrics before
                if metric_name == 'packet_drop':
                    labels.append(interface[0]+'_rx_pkts')
                    data.append(system_metrics['ovs'][interface]['rx_packets'][0])
                    # continue

                if 'packet' in metric_name:
                    metric_name = metric_name.replace('packet', 'pkt')

                labels.append(interface[0]+'_'+metric_name)
                data.append(metrics_list[0])

            # Append margin from qos_metrics in optimize_network()
            labels.append(interface[0]+'_'+'margin')
            data.append(qos_metrics[interface]['margin'])

        # For each metric in last _config, append to labels and data arrays
        for interface, interface_list in system_metrics['network'].items():
            labels.append(interface+'_'+'bandwidth')
            labels.append(interface+'_'+'margin')
            labels.append(interface+'_'+'burst')
            data.append(self.last_config['interfaces'][interface]['bandwidth'])
            data.append(self.last_config['interfaces'][interface]['margin'])
            data.append(self.last_config['interfaces'][interface]['burst'])

        label_str = ''
        data_str = ''
        to_scale = ['g_tx_bw', 'g_rx_bw', 's_tx_bw', 's_rx_bw', 'b_tx_bw', 'b_rx_bw']

        # Create on string for each data row
        for i, label in enumerate(labels):
            label_str += label + ','

            # Rescale bandwidth data to Mbit
            if label in to_scale:
                data_str += str(round(float(data[i])/1E6, 3)) + ','
            else:
                data_str += str(data[i]) + ','

        # If no txt file exists, create one and print labels at top
        if len(list(filter(lambda a: 'csv' in a, os.listdir()))) < 1:
            f = open("sdn_logs.csv", "a")
            now = datetime.datetime.now()
            current_time = now.strftime("%D:%H:%M:%S")
            title = 'SDN controller,' + str(current_time)
            time_stamp = 'start_time_sec,' + str(round(time.time()))
            f.write(time_stamp + os.linesep)
            f.write(title + os.linesep)
            f.write(label_str + 'time' + os.linesep)
            f.close()

        # Read start_time at top of csv-file and calculate time since run started
        f = open("sdn_logs.csv", "r")
        start_time = int(f.readline().split(',')[1].strip())
        data_str += str(round(time.time()-start_time))
        f.close()

        # Open csv log-file and print data
        f = open("sdn_logs.csv", "a")
        f.write(data_str + os.linesep)
        f.close()

        # Write over last_config, to be able to compare what was given
        self.last_config = new_config

        # open and read the file after the appending:
        # f = open("sdn_logs.csv", "r")
        # print(f.read())
