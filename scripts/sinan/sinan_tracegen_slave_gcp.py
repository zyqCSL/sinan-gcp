import sys
import os
import socket
import subprocess
import time
import json
import argparse
import logging
from pathlib import Path

# slave is responsible for adjusting resources on each server
# collecting per-server information, including cpu, network & memory
# currently each VM instance only holds a single replica of a single service


# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
# parser.add_argument('--instance-name', dest='instance_name', type=str, required=True)
parser.add_argument('--cpus', dest='cpus', type=int, required=True)
# parser.add_argument('--max-memory', dest='max_memory',type=str, required=True)	# in MB
parser.add_argument('--server-port', dest='server_port',type=int, default=40011)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# global variables
# InstanceName = args.instance_name	
ServiceName  = ''
Cpus 	 = args.cpus
# MaxMemory 	 = args.max_memory
ServerPort   = args.server_port
MsgBuffer    = ''
CpuLimit 	 = Cpus

# container stats
Containers = []
ContainerStats = {}	# indexed by container names

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def clear_container_stats():
	global Containers
	global ContainerStats
	Containers = []
	ContainerStats = {}

def create_container_stats(container_name, container_id):
	global Containers
	global ContainerStats
	assert container_name not in Containers
	assert container_name not in ContainerStats
	Containers.append(container_name)
	ContainerStats[container_name] = {}
	ContainerStats[container_name]['id']   = container_id
	ContainerStats[container_name]['pids'] = []
	# variables below are cummulative
	ContainerStats[container_name]['rx_packets'] = 0
	ContainerStats[container_name]['rx_bytes'] = 0
	ContainerStats[container_name]['tx_packets'] = 0
	ContainerStats[container_name]['tx_bytes'] = 0
	ContainerStats[container_name]['page_faults'] = 0
	ContainerStats[container_name]['cpu_time'] = 0
	ContainerStats[container_name]['io_sectors'] = 0
	ContainerStats[container_name]['io_services'] = 0
	ContainerStats[container_name]['io_wait_time'] = 0

# used when previous container failed and a new one is rebooted
def reset_container_id_pids():
	logging.info('reset_container_id_pids')
	clear_container_stats()
	docker_ps()

def docker_ps():
	global ServiceName
	texts = subprocess.check_output('docker ps', shell=True, stderr=sys.stderr).decode(
			'utf-8').splitlines()
	for i in range(1, len(texts) - 1):
		c_name = [s for s in texts[i].split(' ') if s][-1]
		c_id = get_container_id(c_name)
		logging.info("docker ps container_name = %s, container_id = %s service = %s" %(c_name, c_id, ServiceName))
		assert ServiceName in c_name
		create_container_stats(c_name, c_id)
		get_container_pids(c_name)

def get_container_id(container_name):
	cmd = "docker inspect --format=\"{{.Id}}\" " + container_name
	container_id = subprocess.check_output(cmd, shell=True, stderr=sys.stderr).decode(
		'utf-8').replace('\n', '')
	return container_id

def get_container_pids(container_name):
	global ContainerStats
	assert container_name in ContainerStats
	cmd = "docker inspect -f \"{{ .State.Pid }}\" " + ContainerStats[container_name]['id']
	pid_strs = subprocess.check_output(cmd, shell=True, stderr=sys.stderr).decode(
		'utf-8').split('\n')
	for pid_str in pid_strs:
		if pid_str != '':
			ContainerStats[container_name]['pids'].append(pid_str)

def compute_mean(stat_dict):
	global Containers
	s = 0
	for c in ContainerStats:
		assert c in stat_dict
		s = s + stat_dict[c]
	return float(s)/len(Containers)

# Inter-|   Receive                                                |  Transmit
#  face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
#     lo:       0       0    0    0    0     0          0         0        0       0    0    0    0     0       0          0
#   eth0: 49916697477 44028473    0    0    0     0          0         0 84480565155 54746827    0    0    0     0       0          0

def get_network_usage():
	global Containers
	global ContainerStats

	rx_packets = {}
	rx_bytes   = {}
	tx_packets = {}
	tx_bytes   = {}

	ret_rx_packets = {}
	ret_rx_bytes   = {}
	ret_tx_packets = {}
	ret_tx_bytes   = {}

	while True:
		fail = False
		for container in Containers:
			rx_packets[container] = 0
			rx_bytes[container]   = 0
			tx_packets[container] = 0
			tx_bytes[container]   = 0

			for pid in ContainerStats[container]['pids']:
				pseudo_file = '/proc/' + str(pid) + '/net/dev'
				if not os.path.isfile(pseudo_file):
					fail = True
					break
				with open(pseudo_file, 'r') as f:
					lines = f.readlines()
					for line in lines:
						if 'Inter-|   Receive' in line or 'face |bytes    packets errs' in line:
							continue
						else:
							data = line.split(' ')
							data = [d for d in data if (d != '' and '#' not in d and ":" not in d)]
							rx_packets[container] += int(data[1])
							rx_bytes[container]   += int(data[0])
							tx_packets[container] += int(data[9])
							tx_bytes[container]   += int(data[8])

			if fail:
				break
			ret_rx_packets[container] = rx_packets[container] - ContainerStats[container]['rx_packets']
			ret_rx_bytes[container]   = rx_bytes[container]	- ContainerStats[container]['rx_bytes']
			ret_tx_packets[container] = tx_packets[container] - ContainerStats[container]['tx_packets']
			ret_tx_bytes[container]   = tx_bytes[container]	- ContainerStats[container]['tx_bytes']

			if ret_rx_packets[container] < 0:
				ret_rx_packets[container] = rx_packets[container]
			if ret_rx_bytes[container] < 0:
				ret_rx_bytes[container] = rx_bytes[container]
			if ret_tx_packets[container] < 0:
				ret_tx_packets[container] = tx_packets[container]
			if ret_tx_bytes[container] < 0:
				ret_tx_bytes[container] = tx_bytes[container]

			ContainerStats[container]['rx_packets'] = rx_packets[container]
			ContainerStats[container]['rx_bytes']   = rx_bytes[container]
			ContainerStats[container]['tx_packets'] = tx_packets[container]
			ContainerStats[container]['tx_bytes']   = tx_bytes[container]

		if not fail:
			break

		else:
			reset_container_id_pids()

	return compute_mean(ret_rx_packets), compute_mean(ret_rx_bytes), compute_mean(ret_tx_packets), compute_mean(ret_tx_bytes)

def get_memory_usage():
	global Containers
	global ContainerStats

	rss = {}	# resident set size, memory belonging to process, including heap & stack ...
	cache_memory = {}	# data stored on disk (like files) currently cached in memory
	page_faults  = {}

	for container in Containers:
		pseudo_file = '/sys/fs/cgroup/memory/docker/' + ContainerStats[container]['id'] + '/memory.stat'
		with open(pseudo_file, 'r') as f:
			lines = f.readlines()
			for line in lines:
				if 'total_cache' in line:
					cache_memory[container] = round(int(line.split(' ')[1])/(1024.0**2), 3)	# turn byte to mb
				elif 'total_rss' in line and 'total_rss_huge' not in line:
					rss[container] = round(int(line.split(' ')[1])/(1024.0**2), 3)
				elif 'total_pgfault' in line:
					pf = int(line.split(' ')[1])
					page_faults[container] = pf - ContainerStats[container]['page_faults']
					if page_faults[container] < 0:
						page_faults[container] = pf
					ContainerStats[container]['page_faults'] = pf

		assert rss[container] >= 0
		assert cache_memory[container] >= 0
		assert page_faults[container] >= 0

	return compute_mean(rss), compute_mean(cache_memory), compute_mean(page_faults)

# cpu time percentages used on behalf on the container
# mpstat gets information of total cpu usage including colated workloads
def get_docker_cpu_usage():
	global Containers
	global ContainerStats

	docker_cpu_time = {}
	while True:
		fail = False
		for container in Containers:
			pseudo_file = '/sys/fs/cgroup/cpuacct/docker/' + ContainerStats[container]['id'] + '/cpuacct.usage'
			if not os.path.isfile(pseudo_file):
				fail = True
				break
			with open(pseudo_file, 'r') as f:
				cum_cpu_time = int(f.readlines()[0])/1000000.0	# turn ns to ms
				docker_cpu_time[container] = max(cum_cpu_time - ContainerStats[container]['cpu_time'], 0)
				logging.info(container + ' docker cummulative cpu time: ' + \
					format(cum_cpu_time, '.1f') + ' interval cpu time: ' + \
					format(docker_cpu_time[container], '.1f'))
				ContainerStats[container]['cpu_time'] = cum_cpu_time

		if not fail:
			break
		else:
			reset_container_id_pids()

	return compute_mean(docker_cpu_time) 

def get_io_usage():
	global Containers
	global ContainerStats

	global Tiers
	global ContainerIds
	global CumIOSectors		
	global CumIOServices		
	global CumIOWaitTime

	ret_io_sectors	= {}
	ret_io_serviced = {}
	ret_io_wait		= {}

	for container in Containers:	
		# io sectors (512 bytes)
		pseudo_file = '/sys/fs/cgroup/blkio/docker/' + ContainerStats[container]['id']  + '/blkio.sectors_recursive'
		with open(pseudo_file, 'r') as f:
			lines = f.readlines()
			if len(lines) > 0:
				sector_num = int(lines[0].split(' ')[-1])
				ret_io_sectors[container] = sector_num - ContainerStats[container]['io_sectors']
				if ret_io_sectors[container] < 0:
					ret_io_sectors[container] = sector_num
			else:
				sector_num = 0
				ret_io_sectors[container] = 0
			ContainerStats[container]['io_sectors'] = sector_num

		# io services
		pseudo_file = '/sys/fs/cgroup/blkio/docker/' + ContainerStats[container]['id']  + '/blkio.io_serviced_recursive'
		with open(pseudo_file, 'r') as f:
			lines = f.readlines()
			for line in lines:
				if 'Total' in line:
					serv_num = int(line.split(' ')[-1])
					ret_io_serviced[container] = serv_num - ContainerStats[container]['io_services']
					if ret_io_serviced[container] < 0:
						ret_io_serviced[container] = serv_num
					ContainerStats[container]['io_services'] = serv_num

		# io wait time
		pseudo_file = '/sys/fs/cgroup/blkio/docker/' + ContainerStats[container]['id']  + '/blkio.io_wait_time_recursive'
		with open(pseudo_file, 'r') as f:
			lines = f.readlines()
			for line in lines:
				if 'Total' in line:
					wait_ms = round(int(line.split(' ')[-1])/1000000.0, 3)	# turn ns to ms
					ret_io_wait[container] = wait_ms - ContainerStats[container]['io_wait_time']
					if ret_io_wait[container] < 0:
						ret_io_wait[container] = wait_ms
					ContainerStats[container_name]['io_wait_time'] = wait_ms

		assert container in ret_io_serviced
		assert container in ret_io_wait

	return compute_mean(ret_io_sectors), compute_mean(ret_io_serviced), compute_mean(ret_io_wait)

# run before each experiment
# TODO: reimplement
# @service_restart: set to true if entire application is restarted
def init_data(service_restart):
	global ServiceName
	global ContainerStats

	if service_restart:
		reset_container_id_pids()

	# read initial values
	get_docker_cpu_usage()
	get_memory_usage()
	get_network_usage()
	get_io_usage()

def set_cpu_limit(cpu_limit, quiet=False):
	global Containers
	global CpuLimit

	CpuLimit = cpu_limit
	_stdout = sys.stdout
	_stderr = sys.stderr
	if quiet:
		_stdout = subprocess.DEVNULL
		_stderr = subprocess.DEVNULL
	p_list = []
	for container in Containers:
		cmd = 'docker update --cpus=%s %s' %(format(cpu_limit, '.2f'), container)
		p = subprocess.Popen(cmd, shell=True, stdout=_stdout, stderr=_stderr)
		p_list.append(p)
	for p in p_list:
		p.communicate()

# TODO: experiment writing net fs or sending through network
def start_experiment(host_sock):
	global MsgBuffer
	global CpuLimit

	logging.info('experiment starts')
	prev_host_query_time = time.time()
	terminate = False

	exp_succ = True
	while True:
		data = host_sock.recv(1024).decode('utf-8')
		# print 'recv: ', data
		MsgBuffer += data

		if len(data) == 0:
			logging.error('host_sock reset during experiment')
			terminate = True
			exp_succ = False

		while '\n' in MsgBuffer:
			(cmd, rest) = MsgBuffer.split('\n', 1)
			MsgBuffer = rest

			logging.info('cmd: ' + cmd)

			if 'get_info' in cmd:
				cur_time = time.time()
				logging.info('time since last host query: ' + format(cur_time - prev_host_query_time, '.2f') + 's')
				docker_cpu_time = get_docker_cpu_usage()
				rss, cache_memory, page_faults = get_memory_usage()
				rx_packets, rx_bytes, tx_packets, tx_bytes = get_network_usage()
				io_sectors, io_serviced, io_wait = get_io_usage()

				ret_info = {}
				ret_info['cpu_docker']   = round(docker_cpu_time/CpuLimit/((cur_time - prev_host_query_time)*1000), 4) * 100	# turn to percentage
				ret_info['rss'] 		 = rss
				ret_info['cache_mem']    = cache_memory
				ret_info['pgfault'] 	 = page_faults
				ret_info['rx_pkt'] 	     = rx_packets
				ret_info['rx_byte'] 	 = rx_bytes
				ret_info['tx_pkt'] 	     = tx_packets
				ret_info['tx_byte'] 	 = tx_bytes
				ret_info['io_sect'] 	 = io_sectors
				ret_info['io_serv'] 	 = io_serviced
				ret_info['io_wait'] 	 = io_wait

				prev_host_query_time = cur_time
				ret_msg = json.dumps(ret_info) + '\n'
				host_sock.sendall(ret_msg.encode('utf-8'))

			elif 'set_cpu_limit' in cmd:
				cpu_limit = float(cmd.split(' ')[1])
				set_cpu_limit(cpu_limit=cpu_limit)

			elif 'terminate_exp' in cmd:
				# host_sock.sendall('experiment_done\n')
				terminate = True

			elif len(cmd) == 0:
				continue

			else:
				logging.error('Error: undefined cmd: ' + cmd)
				exp_succ = False
				terminate = True

		if terminate:
			host_sock.sendall(('experiment_done\n').encode('utf-8'))
			return exp_succ

def main():
	global InstanceName
	global ServerPort
	global MsgBuffer
	global ServiceName
	global ContainerStats

	local_serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	local_serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	#---------------------------------
	# When application / server is configured for localhost or 127.0.0.1, 
	# which means accept connections only on the local machine. 
	# You need to bind with 0.0.0.0 which means listen on all available networks.
	#------------------------------------
	local_serv_sock.bind(('0.0.0.0', ServerPort))
	local_serv_sock.listen(1024)
	host_sock, addr = local_serv_sock.accept()
	host_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

	MsgBuffer = ''
	terminate = False
	while True:
		data = host_sock.recv(1024).decode('utf-8')
		if len(data) == 0:
			logging.info('connection reset by host, exiting...')
			break
		# else:
		# 	print 'recv in main loop: ' + data

		MsgBuffer += data
		while '\n' in MsgBuffer:
			(cmd, rest) = MsgBuffer.split('\n', 1)
			MsgBuffer = rest
			logging.info('cmd = ' + cmd)

			if cmd.startswith('init_exp'):
				ServiceName = cmd.split(' ')[1].strip()
			elif 'init_data' in cmd:
				service_restart = (int(cmd.split(' ')[1]) == 1)
				init_data(service_restart)
				host_sock.sendall(('init_data_done\n').encode('utf-8'))
			elif 'exp_start' in cmd:
				assert '\n' not in rest
				# docker_restart = (int(cmd.split(' ')[2]) == 1)
				stat = start_experiment(host_sock)
				if not stat:	# experiment failed
					terminate = True
					break
				if len(MsgBuffer) > 0:
					logging.info('Cmds left in MsgBuffer (after exp complete): ' + MsgBuffer)
					MsgBuffer = ''
			elif 'terminate_slave' in cmd:
				terminate = True
				break

		if terminate:
			break
	
	host_sock.close()
	local_serv_sock.close()

if __name__ == '__main__':
	# reload_sched_states()
	main()