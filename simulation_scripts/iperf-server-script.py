import json
import subprocess
import os
import logging
import sys

try:
    # Check that configfile name is passed to simulation script
    if len(sys.argv) < 2:
        logging.error('Must pass use case to run simulation')
        exit()

    config_file = sys.argv[1]
    logging.debug('The use case was ' + str(sys.argv[1]))

    # Try reading configfile, if failed throw exception and exit.
    f = open(config_file, "r")
    frames = json.loads(f.read())
except:
    # If read fail, log error message and exit
    current_dir = os.getcwd()
    logging.error("Could find or read use case config-file '"+str(sys.argv[1])+"' in " + current_dir)
    exit()


port_counter = 0
start_port = 5201

# Iterate over frames, read config_list and start iperf-listening on ports, if frame is delay continue to next frame
for frame, config_list in frames.items():
    if 'delay' in config_list.keys():
        continue
    for vm, vm_config in config_list.items():
        print("VM:", vm)
        for interface, interface_config in vm_config['interfaces'].items():
            for i in range(vm_config['interfaces'][interface]['nbr_of_pods']):

                bind_ip = vm_config['interfaces'][interface]['perf_dest_ip']

                print('iperf-'+interface+'-port-'+str(5201+port_counter) +
                      ' to IP     ' + interface_config['perf_dest_ip'])
                command = 'iperf3 -s -p ' + str(start_port+port_counter) + ' -D -B ' + bind_ip
                subprocess.run(command, shell=True, universal_newlines=True)
                print('Executed ' + command)
                port_counter += 1
