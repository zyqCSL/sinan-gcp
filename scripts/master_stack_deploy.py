import argparse
import logging
import math
import subprocess
import sys
import threading
import time
from pathlib import Path
import json

def docker_stack_rm(stack_name):
    docker_stack_rm = subprocess.Popen(
        ["docker", "stack", "rm", stack_name],
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
            ["docker", "stack", "ps", stack_name, "-q"],
            universal_newlines=True,
            stdout=subprocess.PIPE,
        )
        outs, errs = docker_stack_ps.communicate()
        if not outs:
            rm_finish = True
        else:
            time.sleep(5)


# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--instances', dest='instances_n', type=int, required=True)
parser.add_argument('--username', dest='username', type=str, required=True)
parser.add_argument('--instance-name', dest='instance_name',
                    type=str, required=True)
parser.add_argument("--master-internal-ip", dest="master_internal_ip",
                    type=str, required=True)
parser.add_argument("--internal-ip-json", dest="internal_json",
                    type=str, required=True)
parser.add_argument("--background", dest="background", action='store_true')

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
# gcloud
args = parser.parse_args()
instances_n = args.instances_n
instance_name = args.instance_name
username = args.username
master_internal_ip = args.master_internal_ip
internal_ip_json = args.internal_ip_json
# exp
background = args.background
internal_ips = json.loads(internal_ip_json)

# -----------------------------------------------------------------------
# set up docker-swarm
# -----------------------------------------------------------------------
with open("/proc/sys/kernel/hostname", "r") as f:
    hostname = f.readlines()[0].replace("\n", "")
    print(hostname)
    print(instance_name + "-0")
    assert(hostname == instance_name + "-0")

cmd = "docker swarm init"
subprocess.run(cmd, shell=True, stdout=sys.stdout)

cmd = "docker swarm join-token worker"
worker_join_cmd = subprocess.check_output(cmd, shell=True, stderr=sys.stderr).decode(
            "utf-8").strip().splitlines()[2].lstrip()

# print(worker_join_cmd)
for worker_i in range(1, instances_n):
    worker_instance_name = instance_name + "-" + str(worker_i)
    cmd = "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no " + username + "@" + \
        worker_instance_name + " \"" + worker_join_cmd + "\""
    subprocess.run(
        cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)

# -----------------------------------------------------------------------
# deploy services (social-network)
# -----------------------------------------------------------------------
docker_stack_rm("social_network_ml_swarm")
time.sleep(5)
compose_file = "/home/" + username + "/sinan_gcp/benchmarks/" + \
               "social-network/docker-compose-swarm.yml"
cmd = "docker stack deploy --compose-file " + compose_file + "  social_network_ml_swarm"
subprocess.run(cmd, shell=True, stdout=sys.stdout,
                       stderr=sys.stderr)

time.sleep(10)
# -----------------------------------------------------------------------
# check node on which nginx is running
# -----------------------------------------------------------------------
cmd = "docker service ps social_network_ml_swarm_nginx-web-server"
ps_result = subprocess.check_output(cmd, shell=True).decode('utf-8').splitlines()[1].split(" ")
nginx_node = [s for s in ps_result if s][3]
nginx_internal_addr = internal_ips[nginx_node]

# -----------------------------------------------------------------------
# warm up databases
# -----------------------------------------------------------------------
cmd = "python3 /home/" + username + "/sinan_gcp/benchmarks/" + \
      "social-network/scripts/setup_social_graph_init_data_sync.py" + \
      " --data-file /home/" + username + "/sinan_gcp/benchmarks/" + \
      "social-network/datasets/social-graph/socfb-Reed98/socfb-Reed98.mtx" + \
      " --nginx-addr " + nginx_internal_addr

subprocess.run(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)





