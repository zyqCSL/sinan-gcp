import argparse
import json
import logging
import math
import subprocess
import sys
import threading
import time
import socket
from pathlib import Path

import docker


def docker_stack_rm(stack_name):
    docker_stack_rm = subprocess.Popen(
        ['docker', 'stack', 'rm', stack_name],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    docker_stack_rm.wait()
    # outs, errs = docker_stack_deploy.communicate()
    # print(outs, errs)

    # docker stack ps social-network-swarm -q
    rm_finish = False
    while not rm_finish:
        docker_stack_ps = subprocess.Popen(
            ['docker', 'stack', 'ps', stack_name, '-q'],
            universal_newlines=True,
            stdout=subprocess.PIPE,
        )
        outs, errs = docker_stack_ps.communicate()
        if not outs:
            rm_finish = True
        else:
            time.sleep(5)


# -----------------------------------------------------------------------
# miscs
# -----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
client = docker.DockerClient(base_url='unix://var/run/docker.sock')
api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

services_list = ["jaeger", "nginx-web-server", "compose-post-service", "compose-post-redis", "text-service",
                 "user-service", "user-memcached", "user-mongodb", "media-service", "unique-id-service",
                 "url-shorten-service", "user-mention-service", "post-storage-service", "post-storage-memcached",
                 "post-storage-mongodb", "user-timeline-service", "user-timeline-redis", "user-timeline-mongodb",
                 "write-home-timeline-service", "write-home-timeline-rabbitmq", "write-user-timeline-service",
                 "write-user-timeline-rabbitmq", "home-timeline-service", "home-timeline-redis", "social-graph-service",
                 "social-graph-redis", "social-graph-mongodb"]

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--instances', dest='instances_n', type=int, required=True)
parser.add_argument('--replica', dest='replica', type=int, required=True)
parser.add_argument('--instance-name', dest='instance_name',
                    type=str, required=True)
parser.add_argument('--username', dest='username', type=str, required=True)
parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--compose-file', dest='compose_file',
                    type=str, required=True)
parser.add_argument('--background', dest='background', action='store_true')

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
# gcloud
args = parser.parse_args()
instances_n = args.instances_n
instance_name = args.instance_name
username = args.username
stack_name = args.stack_name
compose_file = args.compose_file
replica = args.replica
# exp
background = args.background
service_config_path = Path.home() / 'sinan-gcp' / 'config' / 'service_config.json'

# -----------------------------------------------------------------------
# service config
# -----------------------------------------------------------------------
service_config = {
    "nginx-web-server": {"replica": replica, "node": ""},
    "compose-post-service": {"replica": replica, "node": ""},
    "compose-post-redis": {"replica": replica, "node": ""},
    "text-service": {"replica": replica, "node": ""},
    "user-service": {"replica": replica, "node": ""},
    "user-memcached": {"replica": replica, "node": ""},
    "user-mongodb": {"replica": replica, "node": ""},
    "media-service": {"replica": replica, "node": ""},
    "unique-id-service": {"replica": replica, "node": ""},
    "url-shorten-service": {"replica": replica, "node": ""},
    "user-mention-service": {"replica": replica, "node": ""},
    "post-storage-service": {"replica": replica, "node": ""},
    "post-storage-memcached": {"replica": replica, "node": ""},
    "post-storage-mongodb": {"replica": replica, "node": ""},
    "user-timeline-service": {"replica": replica, "node": ""},
    "user-timeline-redis": {"replica": replica, "node": ""},
    "user-timeline-mongodb": {"replica": replica, "node": ""},
    "write-home-timeline-service": {"replica": replica, "node": ""},
    "write-home-timeline-rabbitmq": {"replica": replica, "node": ""},
    "write-user-timeline-service": {"replica": replica, "node": ""},
    "write-user-timeline-rabbitmq": {"replica": replica, "node": ""},
    "home-timeline-service": {"replica": replica, "node": ""},
    "home-timeline-redis": {"replica": replica, "node": ""},
    "social-graph-service": {"replica": replica, "node": ""},
    "social-graph-redis": {"replica": replica, "node": ""},
    "social-graph-mongodb": {"replica": replica, "node": ""},
    "jaeger": {"replica": 1, "node": ""}
}

# -----------------------------------------------------------------------
# set up docker-swarm
# -----------------------------------------------------------------------
_stdout = None
_stderr = None
if background:
    _stdout = subprocess.DEVNULL
    _stderr = subprocess.DEVNULL

hostname = socket.gethostname()
assert(hostname == instance_name + '-0')

cmd = 'docker swarm init'
subprocess.run(cmd, shell=True, stdout=_stdout)

cmd = 'docker swarm join-token worker'
worker_join_cmd = subprocess.check_output(cmd, shell=True, stderr=_stderr).decode(
    'utf-8').strip().splitlines()[2].lstrip()

# print(worker_join_cmd)
for worker_i in range(1, instances_n):
    worker_instance_name = instance_name + '-' + str(worker_i)
    cmd = 'ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' + username + '@' + \
        worker_instance_name + ' \"' + worker_join_cmd + '\"'
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)

# -----------------------------------------------------------------------
# update node labels
# -----------------------------------------------------------------------
for node_i in range(0, instances_n):
    node_name = instance_name + '-' + str(node_i)
    cmd = 'docker node update --label-add service=' + services_list[node_i] + \
        ' ' + node_name
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)
    service_config[services_list[node_i]]['node'] = node_name

with open(str(service_config_path), 'w+') as f:
    json.dump(service_config, f)

# -----------------------------------------------------------------------
# deploy services (social-network)
# -----------------------------------------------------------------------
docker_stack_rm(stack_name)
time.sleep(5)
cmd = 'docker stack deploy --compose-file ' + \
    str(Path.home() / 'sinan-gcp' / 'benchmarks' /
        'social-network' / compose_file) + ' ' + stack_name
subprocess.run(cmd, shell=True, stdout=_stdout,
               stderr=_stderr)

# -----------------------------------------------------------------------
# wait for services to converge
# -----------------------------------------------------------------------
logging.info('wait for services to converge')
converged = False
while converged is not True:
    for service in client.services.list():
        cmd = 'docker service ls --format \'{{.Replicas}}\' --filter \'id=' + \
            service.id + '\''
        out = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, shell=True, universal_newlines=True).strip()
        actual = int(out.split('/')[0])
        desired = int(out.split('/')[1])
        converged = actual == desired
        if not converged:
            break
    time.sleep(5)
logging.info('services converged')

# -----------------------------------------------------------------------
# warm up databases
# -----------------------------------------------------------------------
logging.info('init social graph')
cmd = 'python3 /home/' + username + '/sinan-gcp/benchmarks/' + \
      'social-network/scripts/setup_social_graph_init_data.py' + \
      ' /home/' + username + '/sinan-gcp/benchmarks/' + \
      'social-network/datasets/social-graph/socfb-Reed98/socfb-Reed98.mtx'
subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)
logging.info('init social graph finished')
