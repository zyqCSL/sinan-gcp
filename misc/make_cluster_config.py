# assume docker version >= 1.13
import sys
import os
import argparse
import logging
from pathlib import Path
import json
import math
# from socket import SOCK_STREAM, socket, AF_INET, SOL_SOCKET, SO_REUSEADDR

from pathlib import Path
sys.path.append(str(Path.cwd()))

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
# parser.add_argument('--cpus', dest='cpus', type=int, required=True)
# parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--cluster-config', dest='cluster_config', type=str, required=True)
parser.add_argument('--replica-cpus', dest='replica_cpus', type=int, default=8)

# data collection parameters
# TODO: add argument parsing here

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# todo: currently assumes all vm instances have the same #cpus
# MaxCpus = args.cpus
# StackName = args.stack_name
cluster_config_path = Path.cwd() / '..' / 'config' / args.cluster_config.strip()
replica_cpus = args.replica_cpus
# scale_factor = args.scale_factor
# cpu_percent = args.cpu_percent

service_config = {
    "nginx-thrift":         {'max_replica': 8, 'max_replicas_per_node': 4, 'max_cpus': 16},
    "compose-post-service": {'max_replica': 4, 'max_cpus': 4},
    "compose-post-redis":   {'max_replica': 1, 'max_cpus': 4},
    "text-service":         {'max_replica': 4, 'max_cpus': 4},
    "text-filter-service":  {'max_replica': 4, 'max_cpus': 4},
    "user-service":         {'max_replica': 4, 'max_cpus': 4},
    "user-memcached":       {'max_replica': 1, 'max_cpus': 4},
    "user-mongodb":         {'max_replica': 1, 'max_cpus': 4},
    "media-service":        {'max_replica': 4, 'max_cpus': 4},
    "media-filter-service": {'max_replica': 16, 'max_replicas_per_node': 1, 'max_cpus': 256},
    "unique-id-service":    {'max_replica': 1, 'max_cpus': 4},
    "url-shorten-service":  {'max_replica': 4, 'max_cpus': 4},
    "user-mention-service": {'max_replica': 4, 'max_cpus': 4},
    # "post-storage-service": {'max_replica': 1, 'max_cpus': 16},
    "post-storage-service": {'max_replica': 8, 'max_replicas_per_node': 4, 'max_cpus': 32},
    "post-storage-memcached":   {'max_replica': 1, 'max_cpus': 4},
    "post-storage-mongodb":     {'max_replica': 1, 'max_cpus': 4},
    "user-timeline-service":    {'max_replica': 4, 'max_cpus': 4},
    "user-timeline-redis":      {'max_replica': 1, 'max_cpus': 4},
    "user-timeline-mongodb":    {'max_replica': 1, 'max_cpus': 4},
    "write-home-timeline-service":  {'max_replica': 4, 'max_cpus': 4},
    "write-home-timeline-rabbitmq": {'max_replica': 4, 'max_cpus': 4},
    "write-user-timeline-service":  {'max_replica': 4, 'max_cpus': 4},
    "write-user-timeline-rabbitmq": {'max_replica': 4, 'max_cpus': 4},
    "home-timeline-service":    {'max_replica': 4, 'max_cpus': 16},
    "home-timeline-redis":      {'max_replica': 1, 'max_cpus': 4},
    "social-graph-service":     {'max_replica': 4, 'max_cpus': 4},
    "social-graph-redis":   {'max_replica': 1, 'max_cpus': 4},
    "social-graph-mongodb": {'max_replica': 1, 'max_cpus': 4}
    # "jaeger": {"replica": 1}
}

scalable_service = [
    "nginx-thrift",
    "compose-post-service",
    "text-service",
    "text-filter-service",
    "user-service",
    "media-service",
    "unique-id-service",
    "url-shorten-service",
    "user-mention-service",
    # "post-storage-service",   # performance bug when deploying post-storage-service with docker routing mesh
    "user-timeline-service",
    "write-home-timeline-service",
    "write-home-timeline-rabbitmq",
    "write-user-timeline-service",
    "write-user-timeline-rabbitmq",
    "home-timeline-service",
    "social-graph-service"
]

for service in service_config:
    service_config[service]['replica'] = service_config[service]['max_replica']
    if 'max_replicas_per_node' not in service_config[service]:
        service_config[service]['max_replicas_per_node'] = service_config[service]['max_replica']
    # service_config[service]['replica_cpus'] = replica_cpus
    if 'max_cpus' not in service_config[service]:
        service_config[service]['max_cpus'] = replica_cpus * service_config[service]['max_replica']

    service_config[service]['node'] = service_config[service]['max_replica'] // service_config[service]['max_replicas_per_node']
    service_config[service]['node_cpus'] = service_config[service]['max_cpus'] // service_config[service]['node']
    service_config[service]['cpus'] = service_config[service]['max_cpus']

node_config = {}
node_config['node-0'] = {}
node_config['node-0']['cpus'] = 16
node_config['node-0']['label'] = 'service=master'
node_id = 1
for service in service_config:
    for k in range(0, service_config[service]['node']):
        node_name = 'node-'+str(node_id)
        assert node_name not in node_config
        node_id += 1
        node_config[node_name] = {}
        node_config[node_name]['cpus'] = service_config[service]['node_cpus']
        node_config[node_name]['label'] = 'service=' + str(service)

cluster_config = {}
cluster_config['nodes'] = node_config
cluster_config['host_node'] = 'node-0'
cluster_config['service'] = service_config
cluster_config['scalable_service'] = scalable_service
cluster_config['replica_cpus'] = replica_cpus

with open(str(cluster_config_path), 'w+') as f:
	json.dump(cluster_config, f, indent=4, sort_keys=True)