import argparse
import json
import logging
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

# -----------------------------------------------------------------------
# miscs
# -----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
client = docker.DockerClient(base_url='unix://var/run/docker.sock')
api_client = docker.APIClient(base_url='unix://var/run/docker.sock')
stack_name = 'social-network-ml-swarm'
service_config_path = Path.home() / 'sinan-gcp' / 'config' / 'service_config.json'
sinan_slave_path = Path.home() / 'sinan-gcp' / 'config' / 'service_config.json'
sinan_master_path = Path.home() / 'sinan-gcp' / 'config' / 'service_config.json'

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--cpus', dest='cpus', type=int, required=True)
parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--min-rps', dest='min_rps', type=int, required=True)
parser.add_argument('--max-rps', dest='max_rps', type=int, required=True)
parser.add_argument('--max-cpus', dest='max_cpus', type=int, required=True)
parser.add_argument('--rps-step', dest='rps_step', type=int, required=True)
parser.add_argument('--exp-time', dest='exp_time', type=int, required=True)
parser.add_argument('--slave-port', dest='slave_port', type=int, required=True)
parser.add_argument('--cluster-config', dest='cluster_config', type=str, required=True)
parser.add_argument('--username', dest='username', type=str, required=True)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
cpus = args.cpus
stack_name = args.stack_name
min_rps = args.min_rps
max_rps = args.max_rps
rps_step = args.rps_step
exp_time = args.exp_time
max_cpus = args.cpus
slave_port = args.slave_port
cluster_config = args.cluster_config
username = args.username

# -----------------------------------------------------------------------
# service configuration
# -----------------------------------------------------------------------
services = []
service_config = {}
node_service_map = {}
with open(service_config_path, 'r') as f:
    service_config = json.load(f)
    services = list(service_config.keys())
    for s in services:
        service_config[s]['cpus'] = max_cpus
        node_service_map[service_config[s]['node']] = s

# -----------------------------------------------------------------------
# run experiment
# -----------------------------------------------------------------------

# start slaves on workers
slave_procs = []
for node in list(node_service_map.keys()):
    slave_cmd = 'python3 /home/' + username + '/sinan-gcp/scripts/sinan/' + \
        'sinan_tracegen_slave_gcp.py --max-cpus ' + str(max_cpus) 
    cmd = 'ssh ' + username + '@' + node + '\'' + slave_cmd + '\''
    p = subprocess.Popen(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)
    slave_procs.append(p)

master_cmd = 'python3 /home/' + username + '/sinan-gcp/scripts/sinan/' + \
        'sinan_tracegen_master_gcp.py --max-cpus ' + str(max_cpus) 
subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)
logging.info('init social graph finished')