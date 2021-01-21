# Docker version 19.03.11, Ubuntu 18.04
import sys
import os
import subprocess
import threading
import time
import numpy as np
import json
import math
import random
import argparse
import logging
from pathlib import Path
import copy

sys.path.append(str(Path.cwd() / 'src'))
from docker_swarm_util import *
# from socket import SOCK_STREAM, socket, AF_INET, SOL_SOCKET, SO_REUSEADDR

random.seed(time.time())
# -----------------------------------------------------------------------
# miscs
# -----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
					format='%(asctime)s %(levelname)s: %(message)s', 
					datefmt='%Y-%m-%d %H:%M:%S')

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
# parser.add_argument('--cpus', dest='cpus', type=int, required=True)
# parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--user-name', dest='user_name', type=str, default='mingyulianggce')
parser.add_argument('--setup-swarm', dest='setup_swarm', action='store_true')
parser.add_argument('--deploy', dest='deploy', action='store_true')
parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--benchmark', dest='benchmark', type=str, default='socialNetwork-ml-swarm')
parser.add_argument('--compose-file', dest='compose_file', type=str, default='docker-compose-swarm-gcp.yml')
parser.add_argument('--deploy-config', dest='deploy_config', type=str, required=True)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# todo: currently assumes all vm instances have the same #cpus
# MaxCpus = args.cpus
Username = args.user_name
Deploy = args.deploy
SetupSwarm = args.setup_swarm
Stackname = args.stack_name
Benchmark = args.benchmark
BenchmarkDir =  Path.cwd() / 'benchmarks' / args.benchmark
ComposeFile = BenchmarkDir / args.compose_file
DeployConfig = Path.cwd() / 'config' / args.deploy_config.strip()


# -----------------------------------------------------------------------
# service & server configuration
# -----------------------------------------------------------------------
Servers = {}
HostServer = ''
with open('/proc/sys/kernel/hostname', 'r') as f:
	HostServer = f.read().replace('\n', '')

ReplicaCpus = 0
Services = []
ScalableServices = []
ServiceConfig = {}
ServiceReplicaStates = {} # states for controlling scaling out/in
ServiceInitConfig = {} # inital configuration of services
ServiceReplicaStates = {}
with open(str(DeployConfig), 'r') as f:
	config_info = json.load(f)
	ReplicaCpus = config_info['replica_cpus']
	Servers = config_info['nodes']
	for node in Servers:
		assert 'cpus' in Servers[node]
		# assert 'label' in Servers[node]	# docker swarm tag of the node
	ServiceConfig = config_info['service']
	ScalableServices = config_info['scalable_service']
	Services = list(ServiceConfig.keys())
	for service in Services:
		assert 'max_replica' in ServiceConfig[service]
		assert 'max_cpus' in ServiceConfig[service]
		# cpu cycle limit
		if 'cpus' not in ServiceConfig[service]:
			ServiceConfig[service]['cpus'] = ServiceConfig[service]['max_cpus']
		if 'replica' not in ServiceConfig[service]:
			ServiceReplicaStates[service] = 1
		else:
			# ServiceConfig[service]['replica'] only used for initialization
			ServiceReplicaStates[service] = ServiceConfig[service]['replica']
		# cpu limit assigned to each replica
		ServiceConfig[service]['replica_cpus'] = ServiceConfig[service]['cpus']/ServiceConfig[service]['replica']
		# assert ServiceConfig[service]['replica_cpus'] <= ReplicaCpus
	ServiceInitConfig = copy.deepcopy(ServiceConfig)

def main():
	global SetupSwarm
	global Deploy

	global BenchmarkDir
	global Benchmark
	global Stackname
	global ComposeFile

	global Stackname
	global Username

	if SetupSwarm:
		# establish docker swarm
		worker_nodes = list(Servers.keys())
		worker_nodes.remove(HostServer)
		print('host: ', HostServer)
		assert HostServer not in worker_nodes
		setup_swarm(username=Username, worker_nodes=worker_nodes)
		# label nodes
		for server in Servers:
			if 'label' in Servers[server]:
				update_node_label(server, Servers[server]['label'])
	
	if Deploy:
		converged = False
		while not converged:
			docker_stack_rm(stack_name=Stackname)
			converged = docker_stack_deploy(stack_name=Stackname, benchmark=Benchmark,
				benchmark_dir=BenchmarkDir, compose_file=ComposeFile)	# deploy benchmark

if __name__ == '__main__':
	main()
