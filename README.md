# Cloud-RAN-Simulation-Environment
This is a Cloud RAN simulation environment for dynamic bandwidth control, developed as part of a master thesis at Lunds Tekniska Högskola. The preparations necessary to run the simulation environment can be found below. For an in-depth description of the functionality and architecture of the setup, the thesis report is available at [LINK]. 

## Virtual Machine Setup
Four virtual machines based on Ubuntu are needed to run the environment setup. In the original setup, VirtualBox was used. When the VMs are up and running, networking settings need to be configured to allow for three vLANs between the VMs. This is to allow for each traffic class to be separated on different vLANs. This can be done in the networking settings via the VirtualBox GUI.

Furthermore a netplan has to be created on the virtual machines to specify which network interface should be assigned to each traffic class. 

Finally a CRD in Kubernetes has to be created for each traffic class. In the CRD one has to specify the range for the subnet for that traffic class. Example:

gold =  30.30.0.1 to 30.30.30.30
silver =  29.29.0.1 to 29.29.29.29
bronze =  28.28.0.1 to 28.28.28.28

## Open vSwitch (OVS)
In VM4, install the latest OVS version.
Configure the OVS to handle three separate veth-pairs, one for each traffic class.

### Example commands:

cmd: ip link add [veth_0] type veth peer name [veth_1] 

cmd: ip link set [veth_0] up

cmd: ip link set [veth_1] up

cmd: ovs-vsctl add-port [ovs_name] [veth_0] 

cmd: ip a add [IP_dest_address] dev [veth_1] 


This enables you to direct the traffic to the specified [IP_dest_address]. In this simulation environment these are set to:

gold = 30.30.30.30/16 

silver = 29.29.29.29/16

bronze = 28.28.28.28/16 


## Running the Simulation
1. Run the simulation_scripts/iperf-server-script.py with one of the Use Case YAML files as an argument. The YAML files are located in the simulation folder. Alternatively write your own YAML files for a customized traffic flow. Do this on the same VM you installed the OVS.
2. Start up the ovs_agent/ovs_agent.py on the same VM you installed the OVS.
3. Deploy the SDN controller through yaml_files/sdnc-deployment.yaml on VM1.
4. Run the simulation_scripts/simulation.py with the same Use Case YAML as in step one as an argument. Do this on VM1. 

## Retrieving the simulation results
To obtain the simulation data recorded by the SDN controller you need to copy the CSV file inside the pod to your virtual machine file system.
An example command for this would be 

cmd: kubectl cp [name_of_sdnc_pod]:[dest_file_path] [dest_file_name]


## Cleaning up
After each simulation run, the simulation_scripts/iperf-killer.py on VM4 to remove all iPerf server instances.

#### Credit
Regarding how to create Kubernetes jobs, we would like to thank Carlos Rolo for well explained examples and tutorial through:
https://blog.pythian.com/how-to-create-kubernetes-jobs-with-python/
