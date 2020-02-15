import sys
import os
import subprocess
import multiprocessing
import threading
import time
import numpy as np
import json
import math
import random
import socket
import argparse
import logging
import time
from pathlib import Path

import docker
# from socket import SOCK_STREAM, socket, AF_INET, SOL_SOCKET, SO_REUSEADDR

# -----------------------------------------------------------------------
# miscs
# -----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
Client = docker.DockerClient(base_url='unix://var/run/docker.sock')
ApiClient = docker.APIClient(base_url='unix://var/run/docker.sock')
# StackName = 'social-network-ml-swarm'
BenchmarkDir = Path.home() / 'sinan-gcp' / 'benchmarks' / 'social-network'
wrk2 = Path.home() / 'sinan-gcp' / 'utils' / 'wrk'
Wrk2Log = Path.home() / 'sinan-gcp' / 'logs' / 'wrk2_log.txt'
Wrk2pt = Path.home() / 'sinan-gcp' / 'logs' / 'pt.txt'
SchedStateFile = Path.home() / 'sinan-gcp' / 'logs' / 'sched_states.txt'
ServiceConfigPath = Path.home() / 'sinan-gcp' / 'config' / 'service_config.json'
DataDir = Path.home() / 'sinan-gcp' / 'logs' / 'collected_data'

if not os.path.isdir(str(DataDir)):
	os.makedirs(str(DataDir))

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--cpus', dest='cpus', type=int, required=True)
parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--min-rps', dest='min_rps', type=int, required=True)
parser.add_argument('--max-rps', dest='max_rps', type=int, required=True)
parser.add_argument('--rps-step', dest='rps_step', type=int, required=True)
parser.add_argument('--exp-time', dest='exp_time', type=int, required=True)
parser.add_argument('--measure-interval', dest='measure_interval', type=int, default=1)
parser.add_argument('--slave-port', dest='slave_port', type=int, required=True)
parser.add_argument('--cluster-config', dest='cluster_config', type=str, required=True)
# data collection parameters
parser.add_argument('--qos', dest='qos', type=int, default=100)
parser.add_argument('--state-lat-step', dest='state_lat_step', type=int, default=25)
parser.add_argument('--roi-range', dest='roi_range', type=int, default=100)
parser.add_argument('--next-rps-step', dest='next_rps_step', type=int, default=200)
parser.add_argument('--max-next-rps', dest='max_next_rps', type=int, default=5000)
parser.add_argument('--max-hold-cycles', dest='max_hold_cycles', type=int, default=10)
parser.add_argument('--viol-timeout-cycles', dest='viol_timeout_cycles', type=int, default=90)
# state penalization 
parser.add_argument('--viol-hold-cycles', dest='viol_hold_cycles', type=int, default=2)
parser.add_argument('--queue-delay-steps', dest='queue_delay_steps', type=int, default=3)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# todo: currently assumes all vm instances have the same #cpus
MaxCpus = args.cpus
StackName = args.stack_name
MinRps = args.min_rps
MaxRps = args.max_rps
RpsStep = args.rps_step
ExpTime = args.exp_time	# in second
MeasureInterval = args.measure_interval	# in second
SlavePort = args.slave_port
ServiceClusterPath = Path.home() / 'sinan-gcp' / 'config' / args.cluster_config.strip()

# -----------------------------------------------------------------------
# service configuration
# -----------------------------------------------------------------------
Services = []
ServiceConfig = {}
NodeServiceMap = {}
with open(ServiceConfigPath, 'r') as f:
	ServiceConfig = json.load(f)
	Services = list(ServiceConfig.keys())
	for service in Services:
		ServiceConfig[service]['cpus'] = MaxCpus
		NodeServiceMap[ServiceConfig[service]['node']] = service

# -----------------------------------------------------------------------
# data collection
# -----------------------------------------------------------------------
# LoadScripts 		 = {}		# for generating different load pattern
# MixedLoadScripts	 = {}
# LoadScriptsTime 	 = {}
# LoadScriptLoadDict	 = {}		# indexed by [load_name][int(time)], the value is the upcoming load in next second starting from int(time)
TestRps = range(MinRps, MaxRps + 1, RpsStep)

StartTime			 = -1		# the time that the script started
ViolTimeoutCycle	 = args.viol_timeout_cycles	    # #cycles of continuous violations after which the application is unlikely to recover even at max rsc
MaxHoldCycle		 = args.max_hold_cycles		# max #cycles scheduler can stay in the same rsc config

Wrk2LastTime		 = -1	# last time wrk2 pt is written

# # server info
# Servers 			 = []
# ServerMaxCores 	 = {}

# cluster tiers by functionality
Clusters 		= {}
ClustersProb 	= {}
PartialClusters = []

# -----------------------------------------------------------------------
# scheduling state parameters
# -----------------------------------------------------------------------
# qos
EndToEndQos			= args.qos		# ms
StateLatStep		= args.state_lat_step
ROI_Range	    	= args.roi_range		# upper bound for region of interest in terms of latency
# rps	
NextRps 			= 0 		# load in the next incoming interval
NextRpsStep			= args.next_rps_step		# the step size for quantizing cummulative load
MaxNextRps			= args.max_next_rps		# the upper bound for quantizing accumlative load
MaxNextRpsIndex		= MaxNextRps/NextRpsStep
# latency diff between previous and current cycle
StateLatFluctFlags  = {}		# the flag representing latency fluctuation for each state
StateLatFluctFlags[0] = [-1*ROI_Range/16.0, ROI_Range/16.0]
StateLatFluctFlags[1] = [ROI_Range/16.0, ROI_Range*(1/16.0 + 1/8.0)]
StateLatFluctFlags[2] = [ROI_Range*(1/16.0 + 1/8.0), ROI_Range*(1/16.0 + 1/8.0 + 1/4.0)]
StateLatFluctFlags[3] = [ROI_Range*(1/16.0 + 1/8.0 + 1/4.0)]
StateLatFluctFlags[-1] = [-1*ROI_Range*(1/16.0 + 1/8.0), -1*ROI_Range/16.0]
StateLatFluctFlags[-2] = [-1*ROI_Range*(1/16.0 + 1/8.0 + 1/4.0), -1*ROI_Range*(1/16.0 + 1/8.0)]
StateLatFluctFlags[-3] = [-1*ROI_Range*(1/16.0 + 1/8.0 + 1/4.0)]
for flag in StateLatFluctFlags:
	for i in range(0, len(StateLatFluctFlags[flag])):
		StateLatFluctFlags[flag][i] = round(StateLatFluctFlags[flag][i], 1)

# scheduling states
SchedState			= {}		# holds all encountered states, indexed by state name

StateLatDict  		= {}
StateLoadDict 		= {}
StateLatKeys  		= {}
StateLoadKeys 		= {}
# keep different tables for different flags (used by state inheritance)
for i in range(-3, 4, 1):
	StateLatDict[i]  		= {}
	StateLoadDict[i] 		= {}
	StateLatKeys[i]  		= []
	StateLoadKeys[i] 		= []

TotalCycle			= 0
NonAOI_Cycle		= 0

# operations to be measured 
# @dec_freq: only decrease frequency of the tier (cpu number remains)
# @dec_cpu: decrease cpu number by 1, and set to max freq (for prioritizing less cpu)
# @reset: reset cpu to a random value between current and max, and freq also to max
DecOperations	= ['reset', 'dec_freq_cluster', 'dec_cpu', 'hold']
# IncOperations	= ['inc_max_freq', 'inc_1_cpu', 'inc_2_cpu', 'hold', 
# 				   'inc_1/16_cpu', 'inc_3/16_cpu', 'inc_5/16_cpu', 'inc_7/16_cpu',
# 				   'inc_1/8_cpu', 'inc_1/4_cpu', 'inc_3/8_cpu', 'inc_1/2_cpu']

IncOperations	= [# increase single cluster
				   'inc_cluster_1/8_cpu', 'inc_cluster_1/4_cpu', 'inc_cluster_1/2_cpu', 'cluster_max_cpu',
				   'inc_cluster_2f', 'inc_cluster_4f', 'inc_cluster_6f', 'inc_cluster_8f', 'cluster_max_freq',
				   # increase all tiers
				   'inc_1/16_cpu', 'inc_1/8_cpu', 'inc_1/2_cpu', 'max_cpu', 
				   'inc_1/8_freq', 'inc_2/8_freq', 'inc_3/8_freq', 'inc_4/8_freq', 'max_freq']

OpProbability	= {}	# indexed by upper bound of the end2end latency

# OpProbability[50]  = {}
# OpProbability[50]['dec'] = 0.95
# OpProbability[50]['inc'] = 0.05
# OpProbability[50]['reset'] = 0.05
# OpProbability[50]['hold']  = 0.2
# OpProbability[50]['dec_cpu'] = 1.0
# OpProbability[50]['dec_freq'] = 0.0

OpProbability['reset'] = 0.0
OpProbability['hold']  = 0.0
OpProbability['dec_freq'] = 0.0
OpProbability['dec_cpu'] = 1.0

# OpProbability['inc_fixed_cpu']       = 0.1
# OpProbability['inc_st_cpu'] 		  = 0.6
# OpProbability['inc_prop_cpu_lt_1/4'] = 0.15
# OpProbability['inc_prop_cpu_gt_1/4'] = 0.15

OpProbability['inc_cluster_cpu'] 	= 0.7
OpProbability['inc_prop_cpu'] 		= 0.3

ViolHoldCycleThres  = args.viol_hold_cycles		# max #cycles, with qos violated, scheduler can stay with one rsc config
ViolHoldCycle 		= 0

QueueingDelaySteps  = args.queue_delay_steps	# #cycles that queueing takes effect in tail latency (used for tracking which sched state to pernalize)
OpLog 	 = []
StateLog = []
ForceHold = 0
ForceHoldThresProb = 0.65

RecordList			= []
CurrentHoldCycle    = 0
AllHoldCycles		= []


# -----------------------------------------------------------------------
# util functions
# -----------------------------------------------------------------------
def run_wrk2(wrk2,  lua_script, nginx_ip,
		dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
		num_threads=10, num_conns=300, duration=10, reqs_per_sec=6000,
		quiet=False):
	_stdout = subprocess.PIPE
	if quiet:
		_stdout = subprocess.DEVNULL
	wrk2_proc = subprocess.Popen([str(wrk2),
		'-L', 
		'-D', str(dist), 
		'-p', str(tail),
		'-r', str(tail_resolution),
		'-S', str(stats_rate),
		'-i', str(tail_report_interval),
		'-t', str(num_threads),
		'-c', str(num_conns),
		'-d', str(duration) + 's',
		'-s', str(lua_script),
		nginx_ip,
		'-R', str(reqs_per_sec)],
		stdout=_stdout,
		bufsize=1,
		universal_newlines=True)
	return wrk2_proc

# DON'T USE THIS!!!
def docker_service_update(stack_name, service_name, limit_cpu):
    cmd = 'docker service update --detach --update-parallelism=0 ' + \
        '--limit-cpu=' + str(limit_cpu) + ' ' + \
        '_'.join([stack_name, service_name])
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

#----------- scheduling state -----------------#
class Record:
	def __init__(self, time):
		self.time = time
		# rsc
		self.cpu_limit = {}

		# lat info
		self.end_to_end_lat = {}
		self.xput  			= 0

		# cpu
		self.cpu_util 	 = {}

		# memory
		self.rss 	     = {}			# resident set size
		self.cache_mem   = {}
		self.page_faults = {}

		# network
		self.rx_packets = {}
		self.tx_packets = {}
		self.rx_bytes	= {}
		self.tx_bytes 	= {}

		# disk io
		self.io_sectors  = {}
		self.io_serviced = {}
		self.io_wait	 = {}

	def show_docker_metric(self):
		global Services

		line = ''
		for service in Services:
			line += service + '-cpu_util: ' + format(self.cpu_util[service], '.2f') + ';\t'

		for service in Services:
			line += service + '-rss: ' + str(self.rss[service]) + ';\t'
			line += service + '-cache_mem: ' + str(self.cache_mem[service]) + ';\t'
			line += service + '-page_faults :' + str(self.page_faults[service]) + ';\n'

		for service in Services:
			line += service + '-rx_pkts: ' + str(self.rx_packets[service]) + ';\t'
			line += service + '-rx_bytes: ' + str(self.rx_bytes[service]) + ';\t'
			line += service + '-tx_pkts: ' + str(self.tx_packets[service]) + ';\t'
			line += service + '-tx_bytes: ' + str(self.tx_bytes[service]) + ';\n'

		for service in Services:
			line += service + '-io_sect: ' + str(self.io_sectors[service]) + ';\t'
			line += service + '-io_serv: ' + str(self.io_serviced[service]) + ';\t'
			line += service + '-io_wait: ' + str(self.io_wait[service]) + ';\n'

		return line

# todo: reserved for later
# def read_load_patterns():
# 	global LoadScripts
# 	global MixedLoadScripts
# 	global LoadScriptDir
# 	global LoadScriptLoadDict
# 	global LoadScriptsTime

# 	for file in os.listdir(LoadScriptDir):
# 		if 'test_reserve' in file:
# 			continue

# 		if '.lua' in file and 'diurnal' in file:
# 			full_path = LoadScriptDir + file
# 			start_pos = file.rfind('_') + 1
# 			end_pos   = file.find('.lua')
# 			load_name = 'diurnal_' + file[start_pos: end_pos]
# 			LoadScripts[load_name] = file

# 			load_rate = []
# 			load_interval = []

# 			load_time = 0
# 			with open(full_path, 'r') as f:
# 				lines = f.readlines()
# 				for line in lines:
# 					if '--' in line:
# 						continue

# 					elif 'load_rates = ' in line:
# 						start_pos = line.find('{')
# 						end_pos   = line.find('}')
# 						data = line[start_pos + 1: end_pos].split(',')
# 						for l in data:
# 							l = int(l.replace('\'', ''))
# 							load_rate.append(l)

# 					elif 'load_intervals = ' in line:  
# 						start_pos = line.find('{')
# 						end_pos   = line.find('}')
# 						data = line[start_pos + 1: end_pos].split(',')
# 						for l in data:
# 							l = int(l.replace('\'', '').replace('s', ''))
# 							load_time += l
# 							load_interval.append(l)

# 			ptr = 0
# 			cur_time = 0
# 			LoadScriptLoadDict[load_name] = {}
# 			LoadScriptsTime[load_name] = load_time
# 			while ptr < len(load_rate):
# 				interval = load_interval[ptr]
# 				load_val = load_rate[ptr]
# 				for i in range(0, interval):
# 					LoadScriptLoadDict[load_name][cur_time] = load_val
# 					cur_time += 1
# 				ptr += 1

# 			# print load_name
# 			# for t in LoadScriptLoadDict[load_name]:
# 			# 	print t, ': ', LoadScriptLoadDict[load_name][t]	

# 		elif '.lua' in file and 'mixed-workload_type' in file:
# 			mixed_id = 'mixed_' +  file.split('mixed-workload_type_')[-1].split('.')[0]
# 			MixedLoadScripts[mixed_id] = file

# 	for name in LoadScriptsTime:	
# 		print name, ': ', LoadScriptsTime[name], 's'

# 	for name in MixedLoadScripts:
# 		print name, ': ', MixedLoadScripts[name]

def parse_cluster_config():
	# server info
	global Services
	global ServiceClusterPath

	global Clusters
	global ClustersProb
	global PartialClusters	

	with open(str(ServiceClusterPath), 'r') as f:
		lines = f.readlines()
		for line in lines:
			if line == '' or line == '\n':
				continue
			partial = False
			if line.startswith('partial----'):
				partial = True
			line = line.split('----')[-1]
			c_name, rest = line.split(':')
			services, prob = rest.split(';')
			c_name = c_name.replace(' ', '')
			Clusters[c_name] = []
			if partial:
				PartialClusters += [c_name]
			services = services.split(',')
			for s in services:				
				s = s.replace(' ', '').replace('\t', '')
				assert s in Services
				Clusters[c_name] += [s]

			ClustersProb[c_name] = float(prob)

	# for debug
	print('Clusters:')
	print(Clusters)
	print('ClustersProb:') 
	print(ClustersProb)
	print('PartialClusters:') 
	print(PartialClusters)

	total_prob = 0.0
	for c in ClustersProb:
		total_prob += ClustersProb[c]

	print('total prob = ' + str(total_prob))

# TODO: implement init & init_data
def init():
	connect_slave()
	time.sleep(1)
	send_init_exp()
	time.sleep(1)

def init_data(docker_restart):
	global RecordList
	global Services
	global ServiceConfig
	global MaxCpus
	global CurrentHoldCycle
	global QueueingDelaySteps
	global OpLog
	global StateLog
	global ForceHold

	OpLog = []
	StateLog = []
	for i in range(0, QueueingDelaySteps):
		StateLog += ['']
		OpLog 	 += [None]
	ForceHold = 0

	RecordList = []
	CurrentHoldCycle = 0

	for service in Services:
		ServiceConfig[service]['cpus'] = MaxCpus

	send_init_data(docker_restart)

# todo
def warmup_app():
	global wrk2
	global BenchmarkDir
	wrk2_proc = run_wrk2(wrk2=wrk2,
		lua_script=str(
			BenchmarkDir / 'wrk2' / 'scripts' / 'social-network' / 'mixed-workload.lua'),
		nginx_ip='http://127.0.0.1:8080',
		dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
		num_threads=10, num_conns=300, duration=30, reqs_per_sec=1000,
		quiet=False)
	wrk2_proc.wait()
	time.sleep(3)

def connect_slave():
	global Services
	global ServiceConfig
	global SlavePort

	for service in Services:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((ServiceConfig[service]['node'], SlavePort))
		sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		ServiceConfig[service]['sock'] = sock

		logging.info("%s on %s connected" %(service, ServiceConfig[service]['node']))

def get_lat_interest_ratio(lat):
	# define interest ratio as C - abs(lat - EndToEndQos) * 1.0
	global EndToEndQos
	global ROI_Range
	if lat > ROI_Range:
		return -1.0
	else:
		return 1.0
		# return max(-1.0, RoiOffset - abs(lat - EndToEndQos)*1.0/EndToEndQos)

def quantize_state_rps(rps):
	global NextRpsStep
	global MaxNextRps
	global MaxNextRpsIndex

	# print 'rps = ', rps, ' NextRpsStep = ', NextRpsStep
	if rps >= MaxNextRps:
		return MaxNextRps
	elif rps % NextRpsStep != 0:
		# print 'rps/NextRpsStep + 1 = ', rps/NextRpsStep + 1
		return (rps/NextRpsStep + 1) * NextRpsStep
	else:
		# print 'rps/NextRpsStep = ', rps/NextRpsStep
		return rps/NextRpsStep * NextRpsStep

def quantize_state_latency(lat):
	global ROI_Range
	global StateLatStep

	if lat > ROI_Range:
		return -1
	else:
		if lat % StateLatStep != 0:
			return (int(lat/StateLatStep) + 1)*StateLatStep
		else:
			return int(lat/StateLatStep)*StateLatStep

def name_state(lat_diff, lat, cum_load):
	# print 'in name_state, lat = ', lat, ', cum_load = ', cum_load
	return str(lat_diff) + '_' + str(lat) + 'ms_' + str(cum_load)

# compute the flag value of the state, according to fluctuations in latency
def compute_state_flag(diff):
	global StateLatFluctFlags

	diff = round(diff, 1)
	# print 'diff = ', diff
	# print StateLatFluctFlags

	if diff > StateLatFluctFlags[0][0] and diff < StateLatFluctFlags[0][1]:
		return 0
	elif diff >= StateLatFluctFlags[1][0] and diff < StateLatFluctFlags[1][1]:
		return 1
	elif diff >= StateLatFluctFlags[2][0] and diff < StateLatFluctFlags[2][1]:
		return 2
	elif diff >= StateLatFluctFlags[3][0]:
		return 3
	elif diff > StateLatFluctFlags[-1][0] and diff <= StateLatFluctFlags[-1][1]:
		return -1
	elif diff > StateLatFluctFlags[-2][0] and diff <= StateLatFluctFlags[-2][1]:
		return -2
	elif diff <= StateLatFluctFlags[-3][0]:
		return -3
	else:
		print('debug')
		print('diff = ' +  str(diff))
		print(StateLatFluctFlags)

class RscProposal:
	def __init__(self):
		self.op = ''
		self.vic_service = ''
		self.vic_cluster = ''
		self.propose_cpu = {}

	def show(self):
		global Services
		report = self.op + ' vic_service: ' + self.vic_service + ' vic_cluster:' + self.vic_cluster + ' --'
		for service in Services:
			report += ' ' + service + ':%.1f;' %(self.propose_cpu[service])
		return report

class State:
	def __init__(self, flag, lat, cum_load):
		global Services
		global ServiceConfig
		global MaxCpus

		self.flag = flag
		self.lat = lat
		self.cum_load = cum_load
		self.name = name_state(flag, lat, cum_load)
		self.activations = 0	# times this state is activated
		self.true_activations = 0
		# self.bound_activaitons	= 0	# times current bound is used

		# the rsc config whose lat is within [0, ROI_Range] and provides the max rsc space
		self.roi_rsc_lower_bound 	  = {}		# indexed by [service][cpu_num]
		for service in Services:
			self.roi_rsc_lower_bound[service] 		= {}
			for c in range(1, MaxCpus + 1):
				self.roi_rsc_lower_bound[service][c] = {}
				self.roi_rsc_lower_bound[service][c]['viol'] = 0
				self.roi_rsc_lower_bound[service][c]['sat']  = 5

		self.resulting_lat_cnt = {}		# count the occurence of next state's quantized latencies
		self.resulting_lat_list = []

	def show_bound(self):
		global Services
		report = 'State: ' + self.name  + ', acts = %d' %(self.activations) + ' '
		for service in Services:
			report += service + ' lower bound: '
			for c in self.roi_rsc_lower_bound[service]:
				report += '[c:%d, sat:%d, viol:%d], ' %(c, 
					self.roi_rsc_lower_bound[service][c]['sat'], 
					self.roi_rsc_lower_bound[service][c]['viol'])
			report += '; '

		return report

	def update(self, result_lat):
		self.activations += 1
		self.true_activations += 1
		self.resulting_lat_list.append(str(int(result_lat)))

	# called after QueueingDelaySteps
	def delayed_update(self, result_lat, rsc_proposal):
		global ROI_Range	
		global Services
		global ServiceConfig
		global Clusters

		logging.info('delayed_update state %s tail = %.1f' %(self.name, result_lat))

		if result_lat < ROI_Range:
			for s in Services:
				cpu = rsc_proposal.propose_cpu[s]
				self.roi_rsc_lower_bound[s][cpu]['sat'] += 1
				logging.info('%s cpu %.1f viol = %d, sat(+1) = %d' %(s, cpu, 
					self.roi_rsc_lower_bound[s][cpu]['viol'], 
					self.roi_rsc_lower_bound[s][cpu]['sat']))

		else:
			if rsc_proposal.op == 'dec_cpu' or rsc_proposal.op == 'dec_freq':
				vic_service = rsc_proposal.vic_service
				vic_cluster = rsc_proposal.vic_cluster
				if vic_service != '':
					cpu = rsc_proposal.propose_cpu[vic_service]
					self.roi_rsc_lower_bound[vic_service][cpu]['viol'] += 1
					logging.info('vic_service %s cpu %.1f viol(+1) = %d, sat = %d' %(vic_service, cpu, 
						  self.roi_rsc_lower_bound[vic_service][cpu]['viol'], 
						  self.roi_rsc_lower_bound[vic_service][cpu]['sat']))

				if vic_cluster != '':
					assert vic_cluster in Clusters
					for vic_service in Clusters[vic_cluster]:
						cpu = rsc_proposal.propose_cpu[vic_service]
						self.roi_rsc_lower_bound[vic_service][cpu]['viol'] += 1
						logging.info('vic_service %s cpu %.1f viol(+1) = %d, sat = %d' %(vic_service, cpu, 
							self.roi_rsc_lower_bound[vic_service][cpu]['viol'], 
							self.roi_rsc_lower_bound[vic_service][cpu]['sat']))

			elif rsc_proposal.op == 'hold':
				for s in Services:
					cpu = rsc_proposal.propose_cpu[s]
					self.roi_rsc_lower_bound[s][cpu]['viol'] += 1
					logging.info('%s cpu %.1f viol(+1) = %d, sat = %d' %(s, cpu, 
						self.roi_rsc_lower_bound[s][cpu]['viol'], 
						self.roi_rsc_lower_bound[s][cpu]['sat']))

	def get_rsc_explore_prob(self, service, next_cpu):
		if next_cpu not in self.roi_rsc_lower_bound[service]:
			logging.info('service ' + service + ' cpu ' + str(next_cpu) + ' not in ' + self.name)
		assert next_cpu in self.roi_rsc_lower_bound[service]

		sat = self.roi_rsc_lower_bound[service][next_cpu]['sat']
		viol = self.roi_rsc_lower_bound[service][next_cpu]['viol']
		return sat * 1.0/(sat + viol)
		# return 1.0

	# need to check feasbility of the proposed action
	def propose_action(self, cur_e2e_lat, prev_op):
		global Services
		global ServiceConfig
		global MaxCpus
		global ROI_Range

		global EndToEndQos
		global OpProbability

		global CurrentHoldCycle
		global MaxHoldCycle

		global Clusters	
		global ClustersProb
		global PartialClusters

		global ForceHold
		global ForceHoldThresProb

		rsc_proposal = RscProposal()

		logging.info('in dec_rsc')
		propose_cpu = {}
		for s in Services:
			propose_cpu[s] = ServiceConfig[s]['cpus']
		service_tried = []

		coin = round(random.random(), 4)
		# check reset
		if coin < OpProbability['reset'] and ForceHold == 0:
			cand_services = list(Services)
			random.shuffle(cand_services)
			for vic_service in cand_services:
				# check reset
				if not (ServiceConfig[vic_service]['cpus'] == MaxCpus):
					CurrentHoldCycle = 0
					propose_cpu[vic_service] = random.randint( 
						min(ServiceConfig[vic_service]['cpus'] + 1, MaxCpus), 
						MaxCpus)
					rsc_proposal.op = 'reset'
					rsc_proposal.vic_service = vic_service
					rsc_proposal.propose_cpu = dict(propose_cpu)
					return rsc_proposal

		# check hold
		if coin < OpProbability['reset'] + OpProbability['hold'] or ForceHold > 0:
			rsc_proposal.op = 'hold'
			CurrentHoldCycle += 1
			rsc_proposal.propose_cpu = dict(propose_cpu)
			ForceHold = max(0, ForceHold - 1)
			return rsc_proposal

		# coin for dec_cpu/dec_freq
		coin = round(random.random(), 4)

		# check dec_cpu
		services_shuffle = list(Services)
		random.shuffle(services_shuffle)

		if coin <= OpProbability['dec_cpu']:
			for vic_service in services_shuffle:
				if ServiceConfig[vic_service]['cpus'] > 1:
					# check lower bound
					service_next_cpu = ServiceConfig[vic_service]['cpus'] - 1
					exp_prob = self.get_rsc_explore_prob(vic_service, service_next_cpu)
					logging.info('exp_prob for service %s = %.2f' %(vic_service, exp_prob))
					exp_coin = round(random.random(), 4)

					if exp_prob == 1.0 or exp_coin < exp_prob:
						CurrentHoldCycle = 0
						propose_cpu[vic_service] = service_next_cpu
						rsc_proposal.op = 'dec_cpu'
						rsc_proposal.vic_service = vic_service
						rsc_proposal.propose_cpu = dict(propose_cpu)

						if exp_prob < ForceHoldThresProb:
							ForceHold = 1
						return rsc_proposal
						
		# if there is no spare room for further scaling down, just hold
		CurrentHoldCycle += 1
		logging.info('CurrentHoldCycle = ' + str(CurrentHoldCycle))
		if CurrentHoldCycle < MaxHoldCycle:
			rsc_proposal.op = 'hold'
			rsc_proposal.propose_cpu = dict(propose_cpu)
			return rsc_proposal

		else:
			CurrentHoldCycle = 0
			coin = random.random()

			if coin < OpProbability['inc_cluster_cpu']:
				# sub_coin = random.random()
				recover_op = 'inc_cluster_'

				# choose cluster
				cluster = ''
				acc_prob = 0.0
				sub_coin = random.random()

				for c in Clusters:
					if sub_coin <= acc_prob + ClustersProb[c]:
						cluster = c 
						break
					acc_prob += ClustersProb[c]

				assert acc_prob <= 1.0
				assert cluster != ''
				recover_op += cluster

				# choose operation
				sub_coin = random.random()
				if sub_coin < 0.35:
					recover_op += '_1/8_cpu'
					for service in Clusters[cluster]:
						inc_cpu_num  	  = int(round(1/8.0*MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				elif sub_coin < 0.35:
					recover_op += '_1/4_cpu'
					for service in Clusters[cluster]:
						inc_cpu_num  	  = int(round(1/4.0*MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				elif sub_coin < 0.9:
					recover_op += '_1/2_cpu'
					for service in Clusters[cluster]:
						inc_cpu_num  	  = int(round(1/2.0*MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				else:
					recover_op += '_max_cpu'
					for service in Clusters[cluster]:
						propose_cpu[service] = MaxCpus

				rsc_proposal.op = recover_op
				rsc_proposal.propose_cpu = dict(propose_cpu)
				return rsc_proposal

			else:
				# increase all cpus proportionally
				sub_coin = random.random()
				if sub_coin < 0.35:
					recover_op = 'inc_1/8_cpu'
					for service in Services:
						if service == 'jaeger':
							continue
						inc_cpu = int(round(1.0/8 *MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				elif sub_coin < 0.65:
					recover_op = 'inc_1/4_cpu'
					for service in Services:
						if service == 'jaeger':
							continue
						inc_cpu = int(round(1.0/4 *MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				elif sub_coin < 0.85:
					recover_op = 'inc_1/2_cpu'
					for service in Services:
						if service == 'jaeger':
							continue
						inc_cpu = int(round(1.0/2 *MaxCpus))
						propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)

				else:
					recover_op = 'max_cpu'
					for service in Services:
						if service == 'jaeger':
							continue
						propose_cpu[service] = MaxCpus

				rsc_proposal.op = recover_op
				rsc_proposal.propose_cpu = dict(propose_cpu)
				return rsc_proposal

def update_state(cur_tail, cur_state_name, cur_rsc_proposal):
	global SchedState
	global QueueingDelaySteps
	global OpProbability
	global OpLog
	global StateLog

	global ROI_Range

	assert len(StateLog) == QueueingDelaySteps
	assert len(OpLog) == QueueingDelaySteps

	if cur_tail > ROI_Range:
		# viol
		for i in range(0, QueueingDelaySteps):
			if StateLog[i] != '' and OpLog[i] != None:
				state = StateLog[i]
				SchedState[state].delayed_update(cur_tail, OpLog[i])

			# clear the window	
			StateLog[i] = ''
			OpLog[i] = None

	else:
		if StateLog[0] != '' and OpLog[0] != None:
			# sat
			state = StateLog[0]
			SchedState[state].delayed_update(cur_tail, OpLog[0])

	OpLog = OpLog[1:] + [cur_rsc_proposal]
	StateLog = StateLog[1:] + [cur_state_name]

def show_states():
	global SchedState
	global SchedStateFile

	global TotalCycle
	global NonAOI_Cycle

	global AllHoldCycles

	total_actions = 0
	non_aoi_actions = 0

	with open(SchedStateFile, 'w+') as f:
		# f.write('\nexp done:\n')
		for state in SchedState:
			line = 'State: ' +  str(state) + ', true_activations = ' + str(SchedState[state].true_activations) + ' activations = ' + str(SchedState[state].activations)
			total_actions += SchedState[state].true_activations
			loggin.info(line)
			f.write(line + '\n')

			bound_report = SchedState[state].show_bound()
			logging.info(bound_report)
			f.write(bound_report + '\n')

			if -1 in SchedState[state].resulting_lat_cnt:
				non_aoi_actions += SchedState[state].resulting_lat_cnt[-1]
			q_lat_list = sorted(SchedState[state].resulting_lat_cnt.keys())
			for q_lat in q_lat_list:
				line =  'State: ' + state + ', resulting_lat: ' + str(q_lat) + ' occurence = ' + str(SchedState[state].resulting_lat_cnt[q_lat])
				logging.info(line)
				f.write(line + '\n')

			result_lat_str = ', '.join(SchedState[state].resulting_lat_list)
			line =  'State: ' + state + ' resulting lat str = ' + result_lat_str
			logging.info(line)
			f.write(line + '\n')

			print('')
			f.write('\n')

		line = 'total_samples = ' + str(total_actions) + ' non_aoi_samples = ' + str(non_aoi_actions)
		logging.info(line)
		f.write(line + '\n')

		line = 'total_cycle = ' + str(TotalCycle) + ' non_aoi cycles = ' + str(NonAOI_Cycle)
		logging.info(line)
		f.write(line + '\n')

		AllHoldCycles.sort()
		line = '\nhold_cycle_distr (%d records in total):' %len(AllHoldCycles)
		logging.info(line)
		f.write(line + '\n')
		if len(AllHoldCycles) > 0:
			for i in range(0, 101, 1):
				pos = int(i/100.0 * len(AllHoldCycles))
				if pos >= len(AllHoldCycles):
					pos = len(AllHoldCycles) - 1
				line = "%.1f%%: %d" %(i, AllHoldCycles[pos])
				logging.info(line)
				f.write(line + '\n')

def send_init_exp():
	global Services
	global ServiceConfig
	
	for service in Services:
		cmd = 'init_exp ' + service + '\n'
		ServiceConfig[service]['sock'].sendall(cmd.encode('utf-8'))

def send_service_terminate_exp(service):
	global ServiceConfig

	cmd = 'terminate_exp\n'
	sock = ServiceConfig[service]['sock']
	sock.sendall(cmd.encode('utf-8'))
	msg = ''
	exp_done = False
	while True:
		data = sock.recv(1024).decode('utf-8')
		msg += data
		while '\n' in msg:
			(cmd, rest) = msg.split('\n', 1)
			msg = rest
			logging.info('recv %s from %s' %(cmd, service))
			if cmd == 'experiment_done':
				exp_done = True
				break
		if exp_done:
			break

def send_terminate_exp():
	global Services

	t_list = []
	for service in Services:
		t = threading.Thread(target=send_service_terminate_exp, kwargs={
			'service': service
		})
		t_list.append(t)
		t.start()

	for t in t_list:
		t.join()
	logging.info('experiment fully terminated')

def send_terminate_slave():
	global Services
	global ServiceConfig

	cmd = 'terminate_slave\n'
	for service in Services:
		ServiceConfig[service].sendall(cmd.encode('utf-8'))

def send_service_init_data(restart_flag, service):
	global ServiceConfig
	cmd = 'init_data ' + restart_flag + '\n'
	sock = ServiceConfig[service]['sock']
	sock.sendall(cmd.encode('utf-8'))

	msg = ''
	init_data_done = False
	while True:
		data = sock.recv(1024).decode('utf-8')
		msg += data
		while '\n' in msg:
			(cmd, rest) = msg.split('\n', 1)
			msg = rest
			logging.info('recv %s from %s' %(cmd, service))
			if cmd == 'init_data_done':
				init_data_done = True
				break
		if init_data_done:
			break

# send init_data request to all slaves
def send_init_data(docker_restart):
	global Services

	# docker_restart set to True is application is restarted before this init_data
	flag = str(int(docker_restart))
	t_list = []
	for service in Services:
		t = threading.Thread(target=send_service_init_data, kwargs={
			'restart_flag': flag,
			'service': service
		})
		t_list.append(t)
		t.start()

	for t in t_list:
		t.join()
	logging.info('send_init_data done')

def send_exp_start():
	global Services
	global ServiceConfig

	cmd = 'exp_start\n'
	for service in Services:
		ServiceConfig[service]['sock'].sendall(cmd.encode('utf-8'))

def send_service_rsc_config(service, cpu_limit):
	global ServiceConfig

	cmd = 'set_cpu limit ' + format(cpu_limit, '.2f') + '\n'
	ServiceConfig[service]['sock'].sendall(cmd.encode('utf-8'))

def send_rsc_config(cpu_config):
	global Services
	global ServiceConfig
	for service in Services:
		cpu_limit = cpu_config[service]/float(ServiceConfig[service]['replica'])
		send_service_rsc_config(service, cpu_limit)

# def send_rsc_config(cpu_config):
# 	global Services
# 	global ServiceConfig

# 	t_list = []
# 	for service in Services:
# 		cpu_limit = cpu_config[service]/float(ServiceConfig[service]['replica'])
# 		t = threading.Thread(target=send_service_rsc_config, kwargs={
# 			'service': service,
# 			'cpu_limit': cpu_limit
# 		})
# 		t_list.append(t)
# 		t.start()

# 	for t in t_list:
# 		t.join()

def set_rsc_config(cpu_config):
	global Services
	global ServiceConfig
	global MaxCpus

	for service in Services:
		if service == 'jaeger':
			continue
		ServiceConfig[service]['cpus'] = cpu_config[service]
		assert ServiceConfig[service]['cpus'] <= MaxCpus

def send_max_rsc_config():
	global Services
	global ServiceConfig
	global MaxCpus

	t_list = []
	for service in Services:
		ServiceConfig[service]['cpus'] = MaxCpus
		cpu_limit = MaxCpus
		t = threading.Thread(target=send_service_rsc_config, kwargs={
			'service': service,
			'cpu_limit': MaxCpus
		})
		t_list.append(t)
		t.start()

	for t in t_list:
		t.join()

def set_max_rsc_config():
	global Services
	global ServiceConfig
	global MaxCpus

	for service in Services:
		if service == 'jaeger':
			continue
		ServiceConfig[service]['cpus'] = MaxCpus

# during recover, return prev_op
def send_set_recover_rsc():
	global Services
	global ServiceConfig

	global OpProbability
	global CurrentHoldCycle
	global AllHoldCycles

	global ViolHoldCycleThres 
	global ViolHoldCycle

	# cluster information
	global Clusters
	global ClustersProb
	global PartialClusters

	if ViolHoldCycle > 0 and ViolHoldCycle < ViolHoldCycleThres:
		# hold rsc
		ViolHoldCycle += 1
		recover_op = 'viol_hold'

	else:
		propose_cpu = {}
		assert ViolHoldCycle == 0 or ViolHoldCycle == ViolHoldCycleThres
		if ViolTimeoutCycle == 0:
			AllHoldCycles += [CurrentHoldCycle]
			CurrentHoldCycle = 0

		ViolHoldCycle = 1

		recover_op = ''
		coin = random.random()

		if coin < OpProbability['inc_cluster_cpu']:
			# sub_coin = random.random()
			recover_op = 'inc_cluster_'

			# choose cluster
			cluster = ''
			acc_prob = 0.0
			sub_coin = random.random()

			for c in Clusters:
				if sub_coin <= acc_prob + ClustersProb[c]:
					cluster = c 
					break
				acc_prob += ClustersProb[c]

			assert acc_prob <= 1.0
			assert cluster != ''
			recover_op += cluster

			# choose operation
			sub_coin = random.random()
			if sub_coin < 0.35:
				recover_op += '_1/8_cpu'
				for service in Clusters[cluster]:
					inc_cpu_num  	  = int(round(1/8.0*MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			elif sub_coin < 0.35:
				recover_op += '_1/4_cpu'
				for service in Clusters[cluster]:
					inc_cpu_num  	  = int(round(1/4.0*MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			elif sub_coin < 0.9:
				recover_op += '_1/2_cpu'
				for service in Clusters[cluster]:
					inc_cpu_num  	  = int(round(1/2.0*MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			else:
				recover_op += '_max_cpu'
				for service in Clusters[cluster]:
					propose_cpu[service] = MaxCpus
					ServiceConfig[service]['cpus'] = propose_cpu[service]

		else:
			# increase all cpus proportionally
			sub_coin = random.random()
			if sub_coin < 0.35:
				recover_op = 'inc_1/8_cpu'
				for service in Services:
					if service == 'jaeger':
						continue
					inc_cpu = int(round(1.0/8 *MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			elif sub_coin < 0.65:
				recover_op = 'inc_1/4_cpu'
				for service in Services:
					if service == 'jaeger':
						continue
					inc_cpu = int(round(1.0/4 *MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			elif sub_coin < 0.85:
				recover_op = 'inc_1/2_cpu'
				for service in Services:
					if service == 'jaeger':
						continue
					inc_cpu = int(round(1.0/2 *MaxCpus))
					propose_cpu[service] = min(ServiceConfig[service]['cpus'] + inc_cpu_num, MaxCpus)
					ServiceConfig[service]['cpus'] = propose_cpu[service]

			else:
				recover_op = 'max_cpu'
				for service in Services:
					if service == 'jaeger':
						continue
					propose_cpu[service] = MaxCpus
					ServiceConfig[service]['cpus'] = propose_cpu[service]

	send_rsc_config(propose_cpu)
	return recover_op
	

def get_service_slave_metric(service, cur_record):
	global ServiceConfig
	sock = ServiceConfig[service]['sock']
	sock.sendall(('get_info\n').encode('utf-8'))
	msg = b''
	while True:
		# msg += sock.recv(1024).decode('utf-8')
		msg += sock.recv(1024)
		if '\n' not in msg:
			continue
		else:
			metric = json.loads(msg.split(b'\n')[0])
			# debug
			logging.info('recv metric from %s' %service)
			if service != 'jaeger':
				cur_record.cpu_util[service]	     = metric['cpu_docker']
				cur_record.rss[service] 			 = metric['rss']
				cur_record.cache_mem[service] 		 = metric['cache_mem']
				cur_record.page_faults[service] 	 = metric['pgfault']
				cur_record.rx_packets[service] 		 = metric['rx_pkt']
				cur_record.rx_bytes[service] 		 = metric['rx_byte']
				cur_record.tx_packets[service] 		 = metric['tx_pkt']
				cur_record.tx_bytes[service] 		 = metric['tx_byte']
				cur_record.io_sectors[service] 		 = metric['io_sect']
				cur_record.io_serviced[service] 	 = metric['io_serv']
				cur_record.io_wait[service] 		 = metric['io_wait']
			break

# @cur_record: Record of current time slot
def get_slave_metric(cur_record):
	global Services
	global ServiceConfig

	t_list = []
	for service in Services:
		t = threading.Thread(target=get_service_slave_metric, kwargs={
			'service': service,
			'cur_record': cur_record
		})
		t_list.append(t)
		t.start()

	for t in t_list:
		t.join()

	# print 'slave metric'
	# print cur_record.show_docker_metric()

# def get_wrk2_data(file_handle, timestamp):
def get_wrk2_data(cur_record):
	global Wrk2LastTime
	global Wrk2pt

	# wait for wrk2 log to update
	# while True:
	# 	mtime = os.path.getmtime(Wrk2LogPath)
	# 	if mtime == Wrk2LastTime:
	# 		time.sleep(0.05)
	# 		print 'Wrk2 mtime = ', mtime
	# 		continue
	# 	else:
	# 		Wrk2LastTime = os.path.getmtime(Wrk2LogPath)
	# 		break

	while True:
		first_time = False
		with open(str(Wrk2pt), 'r') as f:
			lines = f.readlines()
			if len(lines) == 0:
				first_time = True
				time.sleep(0.1)
				continue
			else:
				if first_time:
					Wrk2LastTime = os.path.getmtime(str(Wrk2pt))
				line = lines[-1]
				data = line.split(';')

				lat  = 0
				load = 0
				xput = 0
				for item in data:
					t = item.split(':')
					if t[0] != 'xput':
						percent_key = round(float(t[0]))
						lat = round(int(t[1])/1000.0, 2)
						cur_record.end_to_end_lat[percent_key] = lat
					else:
						cur_record.xput = int(t[1])

					if '99.00' in t[0]:
						lat = round(int(t[1])/1000.0, 2)	# turn us to ms
					if 'xput' in t[0]:
						xput = int(t[1])

				# file_handle.write('time:' + str(timestamp) +'s: ' + line + '\n')
				return lat, xput

def save_records(record_file):
	global RecordList
	global Services

	with open(record_file, 'w+') as f:
		for record in RecordList:
			line = format(record.time, '.1f') + 's---'
			line += 'xput:' + str(record.xput) + ';'
			for service in Services:
				line += service + '-cpu:' + str(record.cpu_num[service]) + ';'
				line += service + '-freq:' + str(record.cpu_freq[service]) + ';'

			for service in Services:
				line += service + '-cpu_util:' + format(record.cpu_util[service], '.1f') + ';'
				line += service + '-docker_cpu_util:' + format(record.cpu_util[service], '.1f') + ';'

			for service in Services:
				line += service + '-rss:' + str(record.rss[service]) + ';'
				line += service + '-cache_mem:' + str(record.cache_mem[service]) + ';'
				line += service + '-page_faults:' + str(record.page_faults[service]) + ';'

			for service in Services:
				line += service + '-rx_pkts:' + str(record.rx_packets[service]) + ';'
				line += service + '-rx_bytes:' + str(record.rx_bytes[service]) + ';'
				line += service + '-tx_pkts:' + str(record.tx_packets[service]) + ';'
				line += service + '-tx_bytes:' + str(record.tx_bytes[service]) + ';'

			for service in Services:
				line += service + '-io_sect:' + str(record.io_sectors[service]) + ';'
				line += service + '-io_serv:' + str(record.io_serviced[service]) + ';'
				line += service + '-io_wait:' + str(record.io_wait[service]) + ';'

			percent_keys = sorted(list(record.end_to_end_lat.keys()))
			for p in percent_keys:
				line += 'e2e-' + format(p, '.2f') + ':' + format(record.end_to_end_lat[p], '.3f') + ';'

			# save jaeper per tier latency separately
			# for span in ValidSpans:
			# 	if span not in record.jaeger_lat[span]:
			# 		line += span + '--1:None;'
			# 	else:
			# 		percent_keys = sorted(list(record.jaeger_lat[span].keys()))
			# 		for p in percent_keys:
			# 			line += 'span-' + span + '-' + format(p, '.2f') + ':' + format(record.jaeger_lat[span][p], '.3f') + ';'

			line += '\n'
			f.write(line)

def help():
	print('1st arg: total hour allowed to run the experiments')

def main():
	global SchedState
	global ROI_Range
	global EndToEndQos
	global CumLoad

	global StartTime		
	# global LoadScripts
	# global MixedLoadScripts 	
	# global LoadScriptsTime 
	# global LoadScriptLoadDict
	# global LoadScriptDir

	global TestRps  
	global ExpTime		
	global MeasureInterval
	global DataDir 
	global BenchmarkDir
	
	global Services
	global ServiceConfig

	global TotalCycle
	global NonAOI_Cycle
	global ViolTimeoutCycle

	global RecordList

	global ViolHoldCycle

	global QueueingDelaySteps
	global OpLog
	global wrk2

	warmup_app()
	init()
	init_data(True)
	# for const load
	for rps in TestRps:
		logging.info('Test const rps: ' + str(rps))
		# setup dir
		exp_dir = DataDir / ('rps_' + str(rps)) 
		if not os.path.isdir(str(exp_dir)):
			os.makedirs(str(exp_dir))

		# trace_dir = exp_dir + 'jaeger_trace/'
		# if not os.path.isdir(trace_dir):
		# 	os.makedirs(trace_dir)

		record_path 	= exp_dir / 'record.txt'
		wrk2_exp_log	= exp_dir / 'wrk2_log.txt'
		time.sleep(5)
		init_data(False)

		# start wrk2
		logging.info("run wrk2")
		send_exp_start()

		wrk2_p = run_wrk2(wrk2=wrk2,
			lua_script=str(
				BenchmarkDir / 'wrk2' / 'scripts' / 'social-network' / 'mixed-workload.lua'),
			nginx_ip='http://127.0.0.1:8080',
			dist='exp', tail=95, tail_resolution=0.5, stats_rate=0.2, tail_report_interval=1,
			num_threads=10, num_conns=300, duration=ExpTime, reqs_per_sec=rps,
			quiet=False)

		time.sleep(0.1)

		StartTime = time.time()
		# start adjusting rsc
		prev_time = StartTime
		cur_time  = prev_time

		prev_state  = None
		prev_rsc_proposal = None
		culprit_state = None
		prev_lat = 0

		interval_idx	 = 1
		consecutive_viol = 0
		unlike_to_recover = False
		prev_op = ''
		while time.time() - StartTime < ExpTime:
			cur_time = time.time()
			if cur_time - StartTime < MeasureInterval*interval_idx:
				time.sleep(MeasureInterval*interval_idx - (cur_time - StartTime))
				continue
			else:
				logging.info('current interval_idx: ' + str(interval_idx) + ', cur_time = ' + str(cur_time - StartTime))
				interval_idx = int((cur_time - StartTime)/MeasureInterval) + 1
				# prev_time  = cur_time
				time_stamp = round(cur_time - StartTime, 1)

				cur_record = Record(time_stamp)
				# save resources before update
				cur_record.cpu_limit = {}
				for s in Services:
					cur_record.cpu_limit[s] = ServiceConfig[s]['cpus']

				tail, xput = get_wrk2_data(cur_record)
				get_slave_metric(cur_record)				
				lat_diff = tail - prev_lat
				prev_lat = tail
				# update state before changing rsc allocation
				if prev_state != None:
					logging.info('prev_state is ' + prev_state)
					SchedState[prev_state].update(tail)

				logging.info('cur_time = ' +  str(cur_time - StartTime) + ', tail = ' + str(tail) + ', xput = ' + str(xput))
				if tail != 0:
					TotalCycle += 1
					# print 'tail = ', tail, ', xput = ', xput
					if tail > ROI_Range:
						# check qos violation timeout
						consecutive_viol += 1
						if consecutive_viol > ViolTimeoutCycle:
							if culprit_state != None:
								SchedState[culprit_state].activations = max(500, SchedState[culprit_state].activations)
							unlike_to_recover = True
							logging.warning('consecutive viol of %d cycles, experiment aborted' %(consecutive_viol))
							break

						NonAOI_Cycle += 1
						if prev_state != None:
							culprit_state = prev_state
						if culprit_state != None and prev_state == None:
							SchedState[culprit_state].activations += 1/2.0
							SchedState[culprit_state].true_activations += 1
							if -1 not in SchedState[culprit_state].resulting_lat_cnt:
								SchedState[culprit_state].resulting_lat_cnt[-1] = 1
							else:
								SchedState[culprit_state].resulting_lat_cnt[-1] += 1
						prev_state = None

						prev_op = send_set_recover_rsc()
						vic_service = ''

						# update state with null values
						update_state(tail, '', None)

					else:
						ViolHoldCycle = 0
						consecutive_viol = 0
						culprit_state = None
						# print 'xput = ', xput
						q_load = quantize_state_rps(rps)
						# print 'q_load = ', q_load
						q_lat  = quantize_state_latency(tail)

						state_flag = compute_state_flag(lat_diff)

						state_name = name_state(state_flag, q_lat, q_load)
						logging.info('current state_name = ' + state_name)

						if state_name not in SchedState:
							SchedState[state_name] = State(state_flag, q_lat, q_load)

						prev_rsc_proposal = SchedState[state_name].propose_action(tail, prev_op)
						logging.info('State: ' + state_name + ' propose -- ' + prev_rsc_proposal.show())
						propose_cpu = dict(prev_rsc_proposal.propose_cpu)

						send_rsc_config(propose_cpu)
						set_rsc_config(propose_cpu)

						# update state with valid states
						update_state(tail, state_name, prev_rsc_proposal)

						prev_state = state_name

				RecordList.append(cur_record)
				prev_time = time.time()

		if not unlike_to_recover:
			msg = wrk2_p.communicate()
		else:
			wrk2_p.kill()

		send_terminate_exp()
		# for debug
		show_states()
		# mv pt.txt to exp dir
		cmd = 'cp ' + str(Wrk2pt) + ' ' + str(exp_dir) + 'wrk2_log.txt'
		p = subprocess.Popen(cmd, shell=True)
		p.communicate()

		save_records(record_path)

if __name__ == '__main__':
	# reload_sched_states()
	main()
	print('\n\nState stats:')
	show_states()
	send_terminate_slave()
