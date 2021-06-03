# Cloud-RAN-Simulation-Environment
This is a cloud RAN simulation environment developed for dynamic bandwidth allocation as part of a master thesis. To run the simulation environment some preparations are necessary. For an in-depth description of the functionality and architecture of the setup, the thesis report is available at [LINK]. 

## Virtual Machine Setup
Four virtual machines are needed to run the environment setup. In the original setup, VirtualBox was used. The OVA files are located in the OVA folder.
When the VMs are up and running, networking settings need to be configured to allow for three separate vLANs between the VMs. 
TBU

## Open vSwitch
In VM4, install the latest OVS version.
Configure the OVS according to 
TBU

## Running the Simulation
1. Run the simulation_scripts/iperf-server-script.py with one of the Use Case yaml files as an argument, they are located in the simulation folder. Or write your own yaml files for a customized traffic flow. Do this on the same VM you installed the OVS.
2. Start up the ovs_agent/ovs_agent.py on the same VM you installed the OVS.
3. Deploy the SDN controller through yaml_files/sdnc-deployment.yaml on VM1.
4. Run the simulation_scripts/simulation.py with the same Use case yaml as in step one as an argument. Do this on any of VM1. 

## Retrieving the simulation results
To obtain the simulation data recorded by the SDN controller you need to copy the csv file inside the pod to your computer.
TBU

## Cleaning up
After each simulation run, the simulation_scripts/iperf-killer.py on VM4.

#### Credit
Regarding how to create Kubernetes jobs, we would like to thank Carlos Rolo for well explained examples and tutorial through:
https://blog.pythian.com/how-to-create-kubernetes-jobs-with-python/
