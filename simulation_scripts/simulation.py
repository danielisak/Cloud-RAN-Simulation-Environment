import hashlib
import string
import random
import logging
import yaml
import sys
import os
import time
from kubernetes import client, config, utils
import kubernetes.client
from kubernetes.client.rest import ApiException
import math
import json

# Set logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Setup K8 configs
config.load_kube_config()
configuration = kubernetes.client.Configuration()
api_instance = client.BatchV1Api()


def kube_delete_empty_pods(namespace='default', phase='Succeeded'):
    # The always needed object
    deleteoptions = client.V1DeleteOptions()
    # We need the api entry point for pods
    api_pods = client.CoreV1Api()
    # List the pods
    try:
        pods = api_pods.list_namespaced_pod(namespace,
                                            pretty=True,
                                            timeout_seconds=60)
    except ApiException as e:
        logging.error(
            "Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)

    for pod in pods.items:
        # logging.debug(pod)
        podname = pod.metadata.name
        try:
            if pod.status.phase == phase:
                api_response = api_pods.delete_namespaced_pod(
                    podname, namespace)  # , deleteoptions
                #logging.info("Pod: {} deleted!".format(podname))
                # logging.debug(api_response)
            # else:
            #    logging.info("Pod: {} still not done... Phase: {}".format(podname, pod.status.phase))
        except ApiException as e:
            logging.error(
                "Exception when calling CoreV1Api->delete_namespaced_pod: %s\n" % e)

    return


def kube_cleanup_finished_jobs(namespace='default', state='Finished'):
    deleteoptions = client.V1DeleteOptions()
    try:
        jobs = api_instance.list_namespaced_job(namespace,
                                                pretty=True,
                                                timeout_seconds=60)
        # print(jobs)
    except ApiException as e:
        print("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)

    # Now we have all the jobs, lets clean up
    # We are also logging the jobs we didn't clean up because they either failed or are still running
    for job in jobs.items:
        # logging.debug(job)
        jobname = job.metadata.name
        jobstatus = job.status.conditions
        if job.status.succeeded == 1:
            # Clean up Job
            #logging.info("Cleaning up Job: {}. Finished at: {}".format(jobname, job.status.completion_time))
            try:
                # What is at work here. Setting Grace Period to 0 means delete ASAP. Otherwise it defaults to
                # some value I can't find anywhere. Propagation policy makes the Garbage cleaning Async
                api_response = api_instance.delete_namespaced_job(jobname,
                                                                  namespace,
                                                                  grace_period_seconds=0,
                                                                  propagation_policy='Background')
                # deleteoptions,
                # logging.debug(api_response)
            except ApiException as e:
                print(
                    "Exception when calling BatchV1Api->delete_namespaced_job: %s\n" % e)
        else:
            if jobstatus is None and job.status.active == 1:
                jobstatus = 'active'
            #logging.info("Job: {} not cleaned up. Current status: {}".format(jobname, jobstatus))

    # Now that we have the jobs cleaned, let's clean the pods
    kube_delete_empty_pods(namespace)
    # And we are done!
    return


def kube_create_job_object(name, container_image, namespace="default", container_name="jobcontainer", env_vars={}, selected_node={}, qos_bridge=None):
    # Body is the object Body
    body = client.V1Job(api_version="batch/v1", kind="Job")
    # Body needs Metadata
    # Attention: Each JOB must have a different name!
    body.metadata = client.V1ObjectMeta(name=name)
    # And a Status
    body.status = client.V1JobStatus()
    # Now we start with the Template...
    template = client.V1PodTemplate()
    template.template = client.V1PodTemplateSpec()
    # Passing Arguments in Env:
    env_list = []
    for env_name, env_value in env_vars.items():
        env_list.append(client.V1EnvVar(name=env_name, value=env_value))
    container = client.V1Container(
        name=container_name, image=container_image, env=env_list, image_pull_policy='IfNotPresent')

    template.template.spec = client.V1PodSpec(
        containers=[container], restart_policy='Never', node_selector=selected_node)
    # Add connection to qos_bridge if specificied in job scheduler.
    if qos_bridge != None:
        template.template.metadata = client.V1ObjectMeta(namespace=namespace,
                                                         annotations={"k8s.v1.cni.cncf.io/networks": qos_bridge})

    # And finaly we can create our V1JobSpec!
    body.spec = client.V1JobSpec(
        ttl_seconds_after_finished=600, template=template.template)
    return body


def kube_test_credentials():
    try:
        api_response = api_instance.get_api_resources()
        # logging.info(api_response)
    except ApiException as e:
        print("Exception when calling API: %s\n" % e)


def kube_create_job(
        perf_name='perf-job', bandwidth='10', port='5201', perf_time='10', dest_ip='127.0.0.1', selected_node={},
        qos_bridge=None, namespace='default'):
    # Create the job definition
    container_image = "lidfeldt/iperfer:latest"
    name = perf_name  # id_generator()
    body = kube_create_job_object(
        name, container_image, namespace=namespace,
        env_vars={"VAR": "TESTING", "PERF_PORT": port, "PERF_BW": bandwidth, "PERF_TIME": perf_time, "PERF_DEST_IP": dest_ip},
        selected_node=selected_node, qos_bridge=qos_bridge)
    # print(body)

    try:
        api_response = api_instance.create_namespaced_job(
            namespace, body, pretty=True)
        # print(api_response)
    except ApiException as e:
        print("Exception when calling BatchV1Api->create_namespaced_job: %s\n" % e)
    return


def id_generator(size=5, chars=string.ascii_lowercase + string.digits):
    nmr = ['1', '2', '3', '4', '5']
    return 'perf-job-'+''.join(random.choice(chars) for _ in range(size))


def start_simulation():

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
        current_dir = os.getcwd()
        logging.error("Could find or read use case config-file '"+str(sys.argv[1])+"' in " + current_dir)
        exit()

    namespaces = ['gold', 'silver', 'bronze']

    # cleanup jobs from last simulation round
    for ns in namespaces:
        kube_cleanup_finished_jobs(namespace=ns)

    port_counter = 0

    # Iterate over frames, read config_list and start jobs, if frame is delay, call time.sleep()
    for frame, config_list in frames.items():
        if 'delay' in config_list.keys():
            print(str(config_list['delay']) + ' seconds delay.')
            time.sleep(int(config_list['delay']))
            continue
        # select VM configuration for each VM
        for vm, vm_config in config_list.items():

            # from VM config iterate over each interface and start the requested pods
            for ifc_nmr, interface in enumerate(list(vm_config['interfaces'].keys())):

                # create on new job for each requested iperf-pod (connection)
                for i in range(vm_config['interfaces'][interface]['nbr_of_pods']):
                    port = str(5201 + port_counter)
                    port_counter += 1

                    perf_name = 'iperf-' + vm + '-' + interface + '-port-' + port
                    perf_time = str(vm_config['interfaces']
                                    [interface]['perf_time'])
                    random_bw = str(math.floor(random.normalvariate(
                        vm_config['interfaces'][interface]['avg_bw'], vm_config['interfaces'][interface]['std_bw'])))
                    dest_ip = vm_config['interfaces'][interface]['perf_dest_ip']
                    selected_node = vm_config['metadata']['node_name']
                    selected_ns = interface

                    kube_create_job(perf_name=perf_name, namespace=selected_ns, port=port, perf_time=perf_time, bandwidth=random_bw,
                                    dest_ip=dest_ip, selected_node=selected_node, qos_bridge=vm_config['interfaces'][interface]['qos_bridge'])
                    print("The bandwidth was: " + str(random_bw))
                    print("The name was: " + perf_name)


if __name__ == '__main__':
    DEBUG_SIM = False
    start_simulation()
