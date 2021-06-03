from kubernetes import client, config
import json
import logging as logger
import requests


class Metrics:
    # Configs can be set in Configuration class directly or using helper utility
    config.load_incluster_config()
    # config.load_kube_config()

    # List of current metrics being extracted, see cAdvisor for more
    query_list = ["container_network_receive_bytes_total",
                  "container_network_transmit_bytes_total", "container_cpu_system_seconds_total"]

    # Convert Prometheus (byte) type row from cAdvisor to JSON format
    def jsonize_row(self, resp_row):
        # last split on ' ' is to accomodate timestamp on VMs/K8s exp, not present in Minikube
        value = float(resp_row.split('} ')[1].split(' ')[0])
        json_ready = '{"' + resp_row.split('{')[1].split('}')[0].replace(
            '=', '":').replace(',', ',"').replace('",', '\",') + '}'
        json_ready = json_ready.split('}')[0] + ',"value":' + str(value) + '}'
        json_ready = '{"' + 'metric":"' + \
            resp_row.split('{')[0] + '",' + json_ready.split('{')[1]

        return json.loads(json_ready)

    # Make JSON format to dataframe format
    def json_to_frame(self, container_list, dropping=None):
        pretty_frame = []

        if len(container_list) > 0:
            columns = list(container_list[0])
        else:
            return -1

        for json_obj in container_list:
            temp = []
            for c in columns:
                temp.append(json_obj.get(c))

            pretty_frame.append(temp)

        return pretty_frame

    # Get all Kubernetes nodes
    def get_nodes(self):
        ac = client.api_client.ApiClient()

        # Get node data and parse out metadata and name
        node_list = json.loads(ac.call_api(
            '/api/v1/nodes', 'GET', auth_settings=['BearerToken'], _preload_content=False)[0].data)
        node_names = []

        for node in node_list.get('items'):
            node_names.append(node.get('metadata').get('name'))

        return node_names

    # Get all Kubernetes namespaces
    def get_namespaces(self):
        ac = client.api_client.ApiClient()

        # Get node data and parse out metadata and name
        namespace_list = json.loads(ac.call_api(
            '/api/v1/namespaces', 'GET', auth_settings=['BearerToken'], _preload_content=False)[0].data)
        namespaces = []

        for namespace in namespace_list.get('items'):
            namespaces.append(namespace.get('metadata').get('name'))

        return namespaces

    # Get data resource from Kubernetes cAdvisor, if specfic pod_name (or part of) provide pod_name
    # Returns array with a JSON objects for all pods with matching name for all nodes in cluster
    def get_data(self, pod_name=None):

        pod_name = pod_name

        # extract all data with the api_client
        ac = client.api_client.ApiClient()

        node_names = self.get_nodes()
        response = []

        # Iterate over nodes and get cAdvisor data, extend response
        for name in node_names:
            req = ac.call_api(f'/api/v1/nodes/{name}/proxy/metrics/cadvisor', 'GET', auth_settings=[
                              'BearerToken'], response_type='json', _preload_content=False)
            # 0 index is for HTTP response
            response.extend(req[0].data.decode('utf-8').split('\n'))

        # count to avoid first two HELP and TYPE rows of resource
        count = 0
        resp_typed = []

        # pick out subset matching query type
        for i, r in enumerate(response):
            if i < 2:
                continue

            if any(subQuery in r for subQuery in self.query_list):
                if count < 2:
                    count += 1
                    continue
                else:
                    resp_typed.append(r)
                    count += 1
            else:
                count = 0  # reset count to handle multiple node response

        all_containers_json = []
        select_containers_json = []

        logger.debug("The number of rows were: " + str(len(resp_typed)))

        # make new array with JSON objects
        for resp_row in resp_typed:
            js = self.jsonize_row(resp_row)

            # don't add pods without an image
            if js.get('image') == "":
                continue
            else:
                all_containers_json.append(js)
                if pod_name is not None and pod_name in js.get('name'):
                    select_containers_json.append(js)

        if pod_name is not None:
            return select_containers_json
        else:
            return all_containers_json

    def get_prom_data(self):

        pod_list_transmit = self.get_prom_response(
            'container_network_transmit_bytes_total', namespace='default', node='minikube', interface='eth0', rate=True, window='60s')
        pod_list_receive = self.get_prom_response(
            'container_network_receive_bytes_total', namespace='default', node='minikube', interface='eth0', rate=True, window='60s')
        logger.debug("Number of pods: " + str(len(pod_list_transmit)))

        node_ns_bw_sum_t = 0
        node_ns_bw_sum_r = 0
        pod_count = 0

        for pod_count, pod in enumerate(pod_list_transmit):
            node_ns_bw_sum_t = node_ns_bw_sum_t + float(pod['value'][1])
            node_ns_bw_sum_r = node_ns_bw_sum_r + \
                float(pod_list_receive[pod_count]['value'][1])

        # convert to from bytes to MBit
        node_ns_bw_sum_t = 8*node_ns_bw_sum_t/1048576
        node_ns_bw_sum_r = 8*node_ns_bw_sum_r/1048576

        logger.debug('Total bandwidth transmitter: ' +
                     str(node_ns_bw_sum_t) + ' Mbit/s')
        logger.debug('Total bandwidth received: ' +
                     str(node_ns_bw_sum_r) + ' Mbit/s')
        return [node_ns_bw_sum_t, node_ns_bw_sum_r]

    def get_prom_response(self, query, namespace=None, node=None, interface=None, rate=False, window='20s', res='1s', averaging=False):
        ac = client.api_client.ApiClient()

        # Get ip adress for Prometheus service
        prom_svc_host = None
        prom_svc_port = '9090'

        services = json.loads(ac.call_api('/api/v1/services', 'GET',
                              auth_settings=['BearerToken'], _preload_content=False)[0].data)
        svc_list = services['items']

        for svc in svc_list:
            if svc['metadata']['name'] == 'prometheus-kube-prometheus-prometheus':
                prom_svc_host = svc['spec']['clusterIP']

        logger.debug(prom_svc_host+':'+prom_svc_port)

        #prom_query = 'rate(container_network_transmit_bytes_total{namespace="default", interface="eth0"}[60m])'
        # prom_svc_host = 'localhost' ### TEMP OVERRIDE OUTSIDE OF CLUSTER

        # id=~"/kubepods.+" for minikube does not work with Postman
        prom_query = query
        param = '{id!~"/docker/.%2B"}'

        if (namespace != None) and (interface != None):
            param = '{'+'namespace="' + namespace + '",'+'id!~"/docker/.%2B",'+'interface="' + interface + '"}'

        prom_query = prom_query + param

        if rate:
            prom_query = 'rate('+prom_query+'['+window+':'+res+'])'

        if averaging:
            prom_query = 'avg_over_time(' + prom_query + '[15s:1s])'

        prom_svc_url = 'http://'+prom_svc_host+':' + \
            prom_svc_port+'/api/v1/query?query='+prom_query
        logger.debug("The prom_svc_url was: " + str(prom_svc_url))
        response = json.loads(requests.get(prom_svc_url).content)
        #logger.debug("Response from Prometheus:" + str(response))
        return response['data']['result']

    def get_ovs_metrics(self):

        # Static IP adress and port to get OVS metrics
        ovs_agent_host = '20.20.0.105'
        ovs_agent_port = '9002'
        ovs_url = 'http://'+ovs_agent_host+':'+ovs_agent_port+'/api/connect'

        ## NON-DUMMY
        response = json.loads(requests.get(ovs_url).content)

        ## DUMMY
        # response = {"interfaces":{
        #     "gold":{"tx_bytes": 1, "tx_packets": 2},
        #     "silver":{"tx_bytes": 3, "tx_packets": 4},
        #     "bronze":{"tx_bytes": 5, "tx_packets": 6}
        # }
        # }
        return response
