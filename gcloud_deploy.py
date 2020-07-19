import argparse
import json
import logging
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.append(str(Path.cwd() / 'src'))
from docker_swarm_util import *

def scp(source, target, identity_file, quiet=False):
    _stdout = sys.stdout
    _stderr = sys.stderr
    if quiet:
        _stdout = subprocess.DEVNULL
        _stderr = subprocess.DEVNULL
    cmd = 'scp -r -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ' + \
        '-i ' + str(identity_file) + ' ' + str(source) + ' ' + str(target)
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)


def rsync(source, target, identity_file, quiet=False):
    _stdout = sys.stdout
    _stderr = sys.stderr
    if quiet:
        _stdout = subprocess.DEVNULL
        _stderr = subprocess.DEVNULL
    cmd = 'rsync -arz --info=progress2 -e ' + \
        '\"ssh -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ' + \
        '-i ' + str(identity_file) + '\" ' + \
        str(source) + ' ' + str(target)
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)


def ssh(destination, cmd, identity_file, quiet=False):
    _stdout = sys.stdout
    _stderr = sys.stderr
    if quiet:
        _stdout = subprocess.DEVNULL
        _stderr = subprocess.DEVNULL
    cmd = 'ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' + \
        '-i ' + str(identity_file) + ' ' + \
        str(destination) + ' \"' + cmd + '\"'
    if not quiet:
        print("ssh cmd = " + cmd)
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)


def create_sinan_instance(instance_name, zone, startup_script_path, public_key_path,
                          cpus, memory, disk, accelerator,
                          external_ips, internal_ips,
                          quiet=False):
    _stdout = sys.stdout
    _stderr = sys.stderr
    if quiet:
        _stdout = subprocess.DEVNULL
        _stderr = subprocess.DEVNULL
    if accelerator == None:
        cmd = 'gcloud compute instances create ' + instance_name + \
            ' --zone=' + zone + \
            ' --image-family=ubuntu-1804-lts' + \
            ' --image-project=ubuntu-os-cloud' + \
            ' --boot-disk-size=' + disk + \
            ' --boot-disk-type=pd-standard' + \
            ' --metadata-from-file startup-script=' + str(startup_script_path) + \
            ',ssh-keys=' + str(public_key_path) + \
            ' --custom-cpu=' + str(cpus) + \
            ' --custom-memory=' + str(memory)
    else:
        cmd = 'gcloud compute instances create ' + instance_name + \
            ' --zone=' + zone + \
            ' --image-family=ubuntu-1804-lts' + \
            ' --image-project=ubuntu-os-cloud' + \
            ' --accelerator type=' + accelerator + ',count=1' + \
            ' --maintenance-policy TERMINATE --restart-on-failure' \
            ' --boot-disk-size=' + disk + \
            ' --boot-disk-type=pd-standard' + \
            ' --metadata-from-file startup-script=' + str(startup_script_path) + \
            ',ssh-keys=' + str(public_key_path) + \
            ' --custom-cpu=' + str(cpus) + \
            ' --custom-memory=' + str(memory)
        # ' --tags=expose-slave-port'
    subprocess.run(cmd, shell=True, stdout=_stdout, stderr=_stderr)
    logging.info("gcloud create done")
    # -----------------------------------------------------------------------
    # get external ip
    # -----------------------------------------------------------------------
    success = False

    cmd = 'gcloud compute instances describe ' + instance_name + \
        ' --zone=' + zone + \
        ' --format=\'get(networkInterfaces[0].accessConfigs[0].natIP)\''
    external_ip = subprocess.check_output(
        cmd, shell=True).decode("utf-8").strip()
    external_ips[instance_name] = external_ip

    cmd = 'gcloud compute instances describe ' + instance_name + \
        ' --zone=' + zone + \
        ' --format=\'get(networkInterfaces[0].networkIP)\''
    internal_ip = subprocess.check_output(
        cmd, shell=True).decode("utf-8").strip()
    internal_ips[instance_name] = internal_ip


    # -----------------------------------------------------------------------
    # wait for startup script to finish
    # -----------------------------------------------------------------------
    logging.info('waiting for ' + instance_name + ' startup to finish')
    while True:
        try:
            res = subprocess.check_output('ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
                                          '-i ' + str(rsa_private_key) + ' ' +
                                          username + '@' + external_ip +
                                          ' \'if [ -f /home/'+username +
                                          '/startup_finished ]; then echo yes; else echo no; fi\'',
                                          shell=True, stderr=_stderr).decode("utf-8").strip()
        except:
            logging.warning(instance_name + ' ssh error')
            res = ""

        if res == "yes":
            break
        time.sleep(30)
    # -----------------------------------------------------------------------
    # scp generated private key to gce instance
    # -----------------------------------------------------------------------
    # logging.info('scp private key')
    scp(source='~/sinan-gcp/keys/id_rsa',
        target=username+'@'+external_ip+':~/.ssh/id_rsa',
        identity_file=str(rsa_private_key), quiet=quiet)
    # -----------------------------------------------------------------------
    # set ssh files/directories privileges
    # -----------------------------------------------------------------------
    # logging.info('set .ssh files privileges')
    ssh(destination=username+'@'+external_ip,
        cmd='sudo chmod 700 ~/.ssh',
        identity_file=rsa_private_key, quiet=quiet)
    ssh(destination=username+'@'+external_ip,
        cmd='sudo chmod 600 ~/.ssh/id_rsa',
        identity_file=rsa_private_key, quiet=quiet)
    ssh(destination=username+'@'+external_ip,
        cmd='sudo chmod 600 ~/.ssh/authorized_keys',
        identity_file=rsa_private_key, quiet=quiet)
    ssh(destination=username+'@'+external_ip,
        cmd='sudo chown -R '+username+':'+username+' ~/.ssh',
        identity_file=rsa_private_key, quiet=quiet)
    # -----------------------------------------------------------------------
    # rsync sinan-gcp
    # -----------------------------------------------------------------------
    # rsync(source='~/sinan-gcp/',
    #       target=username+'@'+external_ip+':~/sinan-gcp',
    #       identity_file=rsa_private_key, quiet=quiet)

    logging.info(instance_name + ' startup finished')


# def create_sinan_firewall_rule(slave_port, source_ranges='0.0.0.0/0', target_tags='expose-slave-port'):
#     cmd = 'gcloud compute firewall-rules create ' + \
#           'rule-expose-slave-' + str(slave_port) + \
#           ' --source-ranges ' + source_ranges + \
#           ' --target-tags ' + target_tags + \
#           ' --allow tcp:' + str(slave_port)

#     subprocess.run(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)
#     logging.info("gcloud firewall rule created")


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
# -----------------------------------------------------------------------
# miscs parameters
# -----------------------------------------------------------------------
zone = 'us-central1-a'

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--username', dest='username', type=str, required=True)
parser.add_argument('--init-gcloud', dest='init_gcloud', action='store_true')
parser.add_argument('--background', dest='background', action='store_true')

parser.add_argument('--deploy-config', dest='deploy_config',
                    type=str, required=True)
parser.add_argument('--gpu-config', dest='gpu_config',
                    type=str, required=True)
parser.add_argument('--mab-config', dest='mab_config', type=str, required=True)
parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
# parser.add_argument('--compose-file', dest='compose_file', type=str, required=True)
parser.add_argument('--min-users', dest='min_users', type=int, required=True)
parser.add_argument('--max-users', dest='max_users', type=int, required=True)
parser.add_argument('--users-step', dest='users_step', type=int, required=True)
parser.add_argument('--exp-time', dest='exp_time', type=int, required=True)
parser.add_argument('--measure-interval', dest='measure_interval', type=int, default=1)
parser.add_argument('--slave-port', dest='slave_port', type=int, default=40011)
parser.add_argument('--gpu-port', dest='gpu_port', type=int, default=40010)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
username = args.username
stack_name = args.stack_name
# compose_file = args.compose_file
init_gcloud = args.init_gcloud
background = args.background
deploy_config_path = Path.cwd() / 'config' / args.deploy_config
gpu_config_path = Path.cwd() / 'config' / args.gpu_config


deploy_config = args.deploy_config
gpu_config = args.gpu_config
mab_config = args.mab_config
min_users = args.min_users
max_users = args.max_users
users_step = args.users_step
exp_time = args.exp_time
measure_interval = args.measure_interval
slave_port = args.slave_port
gpu_port = args.gpu_port

# -----------------------------------------------------------------------
# ssh-keygen
# -----------------------------------------------------------------------
rsa_public_key = Path.home() / 'sinan-gcp' / 'keys' / 'id_rsa.pub'
rsa_private_key = Path.home() / 'sinan-gcp' / 'keys' / 'id_rsa'
if init_gcloud:
    logging.info('generate ssh keys')
    if rsa_private_key.exists():
        rsa_private_key.unlink()
    if rsa_public_key.exists():
        rsa_public_key.unlink()
    cmd = 'ssh-keygen -b 4096 -t rsa -f ~/sinan-gcp/keys/id_rsa -q -N "" -C ' + username
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    # gcloud public key format:
    # username:ssh-rsa ...
    with open(str(rsa_public_key), 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(username+':'+content)

# -----------------------------------------------------------------------
# gcloud compute instances create
# -----------------------------------------------------------------------
startup_script_path = Path.home() / 'sinan-gcp' / 'scripts' / 'startup.sh'
predictor_startup_script_path = Path.home() / 'sinan-gcp' / 'scripts' / 'predictor_startup.sh'
public_key_path = Path.home() / 'sinan-gcp' / 'keys' / 'id_rsa.pub'

external_ips = {}
internal_ips = {}
init_gcloud_threads = []
master_host = ''
if init_gcloud:
    logging.info('starting init_gcloud')
    with open(str(deploy_config_path), 'r') as f:
        json_config = json.load(f)
        node_config = json_config['nodes']
        master_host = json_config['host_node']
        for node_name in node_config:
            disk_size = '10GB'
            if node_name == master_host:
                disk_size = '40GB'
                
            t = threading.Thread(target=create_sinan_instance, kwargs={
                'instance_name': node_name,
                'zone': zone,
                'startup_script_path': startup_script_path,
                'public_key_path': public_key_path,
                'cpus': node_config[node_name]['cpus'],
                'memory': node_config[node_name]['cpus'],
                'disk': disk_size,
                'accelerator': None,
                'external_ips': external_ips,
                'internal_ips': internal_ips,
                'quiet': True
            })
            init_gcloud_threads.append(t)
            t.start()

    # create predictor instance
    with open(str(gpu_config_path), 'r') as f:
        json_config = json.load(f)
        node_name = json_config['host']
        cpus = json_config['cpus']
        accelerator = json_config['accelerator']
        if accelerator == '':
            accelerator = None
        if 'startup_script' in json_config:
            predictor_startup_script_path = Path.home() / 'sinan-gcp' / 'scripts' / json_config['startup_script']
        disk_size = '40GB'
        
        t = threading.Thread(target=create_sinan_instance, kwargs={
            'instance_name': node_name,
            'zone': zone,
            'startup_script_path': predictor_startup_script_path,
            'public_key_path': public_key_path,
            'cpus': cpus,
            'memory': cpus,
            'disk': disk_size,
            'accelerator': accelerator,
            'external_ips': external_ips,
            'internal_ips': internal_ips,
            'quiet': True
        })
        init_gcloud_threads.append(t)
        t.start()

    for t in init_gcloud_threads:
        t.join()
    logging.info('init_gcloud finished')

external_ip_path = Path.home() / 'sinan-gcp' / 'logs' / 'external_ip.json'
internal_ip_path = Path.home() / 'sinan-gcp' / 'logs' / 'internal_ip.json'
if init_gcloud:
    with open(str(external_ip_path), "w+") as f:
        json.dump(external_ips, f, indent=4, sort_keys=True)
    with open(str(internal_ip_path), "w+") as f:
        json.dump(internal_ips, f, indent=4, sort_keys=True)
else:
    with open(str(external_ip_path), 'r') as f:
        external_ips = json.load(f)
    with open(str(internal_ip_path), 'r') as f:
        internal_ips = json.load(f)

# -----------------------------------------------------------------------
# run exp
# -----------------------------------------------------------------------
master_run_exp_cmd = 'cd /home/' + username + '/sinan-gcp/;'
master_run_exp_cmd += 'python3 master_deploy_social.py' + \
    ' --user-name=' + username + \
    ' --stack-name=' + stack_name + \
    ' --max-users=' + str(max_users) + \
    ' --min-users=' + str(min_users) + \
    ' --users-step=' + str(users_step) + \
    ' --slave-port=' + str(slave_port) + \
    ' --exp-time=' + str(exp_time) + \
    ' --measure-interval=' + str(measure_interval) + \
    ' --slave-port=' + str(slave_port) + \
    ' --gpu-port=' + str(gpu_port) + \
    ' --deploy-config=' + str(deploy_config) + \
    ' --gpu-config=' + str(gpu_config) + \
    ' --mab-config=' + str(mab_config) + \
    ' --setup-swarm' + \
    ' --deploy'
    
assert master_host != ''
assert master_host in external_ips
ssh(destination=username+'@'+external_ips[master_host],
    cmd=master_run_exp_cmd,
    identity_file=str(rsa_private_key), quiet=False)
