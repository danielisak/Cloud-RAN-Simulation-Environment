import time
import subprocess
import flask
from flask import Flask
from flask import request
import logging as logger
import json

logger.basicConfig(level="DEBUG")

agentInstance = Flask(__name__)


@agentInstance.route('/')
def connection_test():
    return 'OVS agent is accessible!'


@agentInstance.route('/api/connect', methods=['POST', 'GET'])
def connect():
    # the code below is executed if the request method
    # was GET or the credentials were invalid
    # if request.method()
    if request.method == 'POST':
        reconfigure_ovs(request.get_json())
        return flask.Response(), 200
    elif request.method == 'GET':
        return get_ovs_metrics(), 200


def reconfigure_ovs(config_file):
    config_list = config_file

    # config_file = './ovs_reconfig.json'
    # f = open(config_file, "r")
    # config_list = json.loads(f.read())

    # Load new bandwidth limits and convert Mbit to Kbit
    try:
        gold_bw = int(config_list['interfaces']['gold']['bandwidth']*1000)
        silver_bw = int(config_list['interfaces']['silver']['bandwidth']*1000)
        bronze_bw = int(config_list['interfaces']['bronze']['bandwidth']*1000)

        gold_burst = int(config_list['interfaces']['gold']['burst']*1000)
        silver_burst = int(config_list['interfaces']['silver']['burst']*1000)
        bronze_burst = int(config_list['interfaces']['bronze']['burst']*1000)
    except:
        logger.debug('JSON format of config file does not match')

    gold_call = 'ovs-vsctl set interface enp0s10 ingress_policing_rate=' + str(gold_bw)
    silver_call = 'ovs-vsctl set interface enp0s9 ingress_policing_rate=' + str(silver_bw)
    bronze_call = 'ovs-vsctl set interface enp0s8 ingress_policing_rate=' + str(bronze_bw)

    gold_call_burst = 'ovs-vsctl set interface enp0s10 ingress_policing_burst=' + str(gold_burst)
    silver_call_burst = 'ovs-vsctl set interface enp0s9 ingress_policing_burst=' + str(silver_burst)
    bronze_call_burst = 'ovs-vsctl set interface enp0s8 ingress_policing_burst=' + str(bronze_burst)

    subprocess.call(gold_call, shell=True)
    subprocess.call(silver_call, shell=True)
    subprocess.call(bronze_call, shell=True)

    subprocess.call(gold_call_burst, shell=True)
    subprocess.call(silver_call_burst, shell=True)
    subprocess.call(bronze_call_burst, shell=True)


# def get_ovs_metrics():
#     # get metrics from OVS
#     # takes out rx_bytes from OVS metrics
#     def parse_dump(key, metrics_dump):
#         return int(list(filter(lambda a: key in a, metrics_dump.split()))[
#             0].split('=')[1][:-1])

#     try:
#         gold_metrics = subprocess.check_output(
#             'ovs-ofctl dump-ports OVS-1 enp0s10', shell=True).decode('utf-8')
#         silver_metrics = subprocess.check_output(
#             'ovs-ofctl dump-ports OVS-1 enp0s9', shell=True).decode('utf-8')
#         bronze_metrics = subprocess.check_output(
#             'ovs-ofctl dump-ports OVS-1 enp0s8', shell=True).decode('utf-8')
#     except:
#         logger.debug('OVS metrics dump failed')
#         return -1 ## NON-DUMMY

#     ## NON-DUMMY
#     g_rx_bytes = parse_dump('bytes', gold_metrics)
#     g_rx_pkts = parse_dump('pkts', gold_metrics)
#     s_rx_bytes = parse_dump('bytes', silver_metrics)
#     s_rx_pkts = parse_dump('pkts', silver_metrics)
#     b_rx_bytes = parse_dump('bytes', bronze_metrics)
#     b_rx_pkts = parse_dump('pkts', bronze_metrics)

#     ## DUMMY
#     # g_rx_bytes = 1
#     # g_rx_pkts = 2
#     # s_rx_bytes = 3
#     # s_rx_pkts = 4
#     # b_rx_bytes = 5
#     # b_rx_pkts = 6

#     metrics = {"interfaces": {}}

#     metrics['interfaces']['gold'] = {
#         "tx_bytes": g_rx_bytes, "tx_packets": g_rx_pkts}
#     metrics['interfaces']['silver'] = {
#         "tx_bytes": s_rx_bytes, "tx_packets": s_rx_pkts}
#     metrics['interfaces']['bronze'] = {
#         "tx_bytes": b_rx_bytes, "tx_packets": b_rx_pkts}

#     return metrics

# Get OVS metric through command-line and split out bytes and packets for all interfaces, return dict with OVS metrics.
def get_ovs_metrics():

    # Extract metrics from OVS per interface and specify metric with metric_index, return output
    def extract_metrics(interface, metric):
        metric_index = 0
        output = ''
        command = 'ip -s link show ' + interface

        # Choose metric_index based on metric parameter
        if metric == 'bytes':
            metric_index = 6
        elif metric == 'packets':
            metric_index = 7

        # Try subprocess call to ip link show, if it fails return -1
        try:
            output = int((subprocess.check_output(command, shell=True)).decode('utf-8').split('RX:')[1].split()[metric_index])
        except:
            logger.error('OVS metric fetch of metric "' + metric + '" failed for interface "' + interface + '" failed.')
            return -1

        return output

    # returns incoming and outgoing packets of each interface of the OVS
    g_rx_pkts = extract_metrics('gveth1', 'packets')  # packets rx received by iperf-endpoint
    g_tx_pkts = extract_metrics('enp0s10', 'packets')  # packets tx sent from iperf-pods
    g_rx_bytes = extract_metrics('gveth1', 'bytes')  # bytes received by iperf-endpoint, IMPORTANT
    g_tx_bytes = extract_metrics('enp0s10', 'bytes')  # bytes sent from iperf-pods

    s_rx_pkts = extract_metrics('sveth1', 'packets')
    s_tx_pkts = extract_metrics('enp0s9', 'packets')
    s_rx_bytes = extract_metrics('sveth1', 'bytes')
    s_tx_bytes = extract_metrics('enp0s9', 'bytes')

    b_rx_pkts = extract_metrics('bveth1', 'packets')
    b_tx_pkts = extract_metrics('enp0s8', 'packets')
    b_rx_bytes = extract_metrics('bveth1', 'bytes')
    b_tx_bytes = extract_metrics('enp0s8', 'bytes')

    metrics = {"ovs": {}}

    metrics['ovs']['gold'] = {
        "tx_bytes": g_tx_bytes, "rx_bytes": g_rx_bytes, "tx_packets": g_tx_pkts, "rx_packets": g_rx_pkts}
    metrics['ovs']['silver'] = {
        "tx_bytes": s_tx_bytes, "rx_bytes": s_rx_bytes, "tx_packets": s_tx_pkts, "rx_packets": s_rx_pkts}
    metrics['ovs']['bronze'] = {
        "tx_bytes": b_tx_bytes, "rx_bytes": b_rx_bytes, "tx_packets": b_tx_pkts, "rx_packets": b_rx_pkts}

    return metrics


if __name__ == '__main__':
    logger.debug('Starting the application')
    # Remove listening on all ports 0.0.0.0 in production
    agentInstance.run(host="0.0.0.0", port=9002,
                      debug=True, use_reloader=True)
