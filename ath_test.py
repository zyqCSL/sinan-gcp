import subprocess
import logging
import time
from pathlib import Path


# -----------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------
def docker_image_build(node_name, benchmark_dir, name_tag, prune=False):
    if prune:
        cmd = "ssh zz586@" + node_name + " \"docker container prune --force\" &&\n"
        cmd += "ssh zz586@" + node_name + " \"docker image prune --force\" &&\n"
        cmd += "ssh zz586@" + node_name + \
            " \"docker image rm " + name_tag + "\""
        docker_image_prune = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE)
        docker_image_prune.wait()

    cmd = "ssh zz586@" + node_name + " \"cd " + str(benchmark_dir) + \
        " && docker build -f ./Dockerfile -t " + name_tag + " .\""
    docker_image_build = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE)
    docker_image_build.wait()


def run_wrk2(wrk2,  lua_script, nginx_ip,
             dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
             num_threads=10, num_conns=300, duration=10, reqs_per_sec=6000,
             logging=False):
    _stdout = subprocess.DEVNULL
    if logging:
        _stdout = subprocess.PIPE
    wrk2_proc = subprocess.Popen(
        [wrk2,
         '-L',
         '-D', dist,
         #  '-P', '0',
         '-p', str(tail),
         '-r', str(tail_resolution),
         '-S', str(stats_rate),
         '-i', str(tail_report_interval),
         '-t', str(num_threads),
         '-c', str(num_conns),
         '-d', str(duration) + 's',
         '-s', lua_script,
         nginx_ip,
         '-R', str(reqs_per_sec)],
        stdout=_stdout,
        bufsize=1,
        universal_newlines=True
    )
    return wrk2_proc


logging.basicConfig(
    level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
benchmark_dir = Path.home() / 'sinan-gcp' / 'benchmarks' / 'social-network'
compose_file_path = benchmark_dir / 'docker-compose-swarm.yml'
stack_name = 'social-network-ml-swarm'
image_name = 'yz2297/social-network-ml-swarm'
node_name = 'ath-1'
python = '/home/zz586/.pyenv/versions/3.6.9/bin/python'
wrk2 = Path.home() / 'sinan-gcp' / 'utils' / 'wrk2' / 'wrk'

# -----------------------------------------------------------------------
# build image
# -----------------------------------------------------------------------
cmd = "ssh zz586@" + node_name + " \"cd " + str(benchmark_dir) + \
    " && docker build -f ./Dockerfile -t " + image_name + " .\""
logging.info('build docker image')
docker_image_build = subprocess.Popen(
    cmd, shell=True, stdout=subprocess.PIPE)
docker_image_build.wait()
logging.info('docker image built')

# -----------------------------------------------------------------------
# Deploy social network stack
# -----------------------------------------------------------------------
logging.info('deploy docker stack')
docker_stack_deploy = subprocess.Popen(
    ["docker", "stack", "deploy",
     "--compose-file", compose_file_path,
     "--prune",
     stack_name],
    stdout=subprocess.PIPE
)
docker_stack_deploy.wait()
time.sleep(30)

# -----------------------------------------------------------------------
# Init social graph
# -----------------------------------------------------------------------
logging.info('init social graph')
init_social_graph = subprocess.Popen(
    [python,
     str(benchmark_dir / 'scripts' / 'init_social_graph.py'),
     str(benchmark_dir / 'datasets' / 'social-graph' /
         'socfb-Reed98' / 'socfb-Reed98.mtx'),
     'http://ath-1.ece.cornell.edu:8080'],
    stdout=subprocess.DEVNULL)
init_social_graph.wait()
logging.info('social graph initialized')


# -----------------------------------------------------------------------
# warmup
# -----------------------------------------------------------------------
logging.info("warm up")
wrk2_proc = run_wrk2(wrk2=wrk2,
                     lua_script=str(
                         benchmark_dir / 'wrk2' / 'scripts' / 'social-network' / 'mixed-workload.lua'),
                     nginx_ip='http://ath-1.ece.cornell.edu:8080',
                     dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
                     num_threads=10, num_conns=300, duration=30, reqs_per_sec=1000,
                     logging=False)
wrk2_proc.wait()
time.sleep(10)

# -----------------------------------------------------------------------
# Run wrk2
# -----------------------------------------------------------------------
logging.info('run wrk2')
wrk2_proc = run_wrk2(wrk2=wrk2,
                     lua_script=str(
                         benchmark_dir / 'wrk2' / 'scripts' / 'social-network' / 'mixed-workload.lua'),
                     nginx_ip='http://ath-1.ece.cornell.edu:8080',
                     dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
                     num_threads=10, num_conns=300, duration=60, reqs_per_sec=1000,
                     logging=False)
wrk2_proc.wait()
