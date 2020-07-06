import numpy as np
import sys
import os
import re
import scipy.misc
import math
import argparse

t_steps = 5

# normalization for pkt/bytes
# rx_pkts_norm  = 200000.0
# rx_bytes_norm = 60000000.0
# tx_pkts_norm  = 200000.0
# tx_bytes_norm = 60000000.0

rx_pkts_norm  = 1.0
rx_bytes_norm = 1.0
tx_pkts_norm  = 1.0
tx_bytes_norm = 1.0

LookForward = 4
Upsample = False
qos = 300
targ_viol_ratio = 0.5

# directories

# sorted order for tiers
Tiers      = ['compose-post-redis',
              'compose-post-service',
              'home-timeline-redis',
              'home-timeline-service',
              # 'jaeger',
              'nginx-thrift',
              'post-storage-memcached',
              'post-storage-mongodb',
              'post-storage-service',
              'social-graph-mongodb',
              'social-graph-redis',
              'social-graph-service',
              'text-service',
              'text-filter',
              'unique-id-service',
              'url-shorten-service',
              'media-service',
              'media-filter',
              'user-mention-service',
              'user-memcached',
              'user-mongodb',
              'user-service',
              'user-timeline-mongodb',
              'user-timeline-redis',
              'user-timeline-service',
              'write-home-timeline-service',
              'write-home-timeline-rabbitmq',
              'write-user-timeline-service',
              'write-user-timeline-rabbitmq']

def upsample(sys_data, lat_data, next_info, next_k_info, lat_lbl, lat_next_k_lbl):
    global qos 
    # classify data to do upsampling
    label_nxt_k = np.squeeze(lat_next_k_lbl[:, -1, :])     # only keep 99% percentile

    # print label_nxt_t.shape
    label_nxt_k = np.greater_equal(label_nxt_k, qos)
    # return

    # print label_nxt_t.shape
    if LookForward > 1:
        label_nxt_k = np.sum(label_nxt_k, axis = 1)
    # print label_nxt_t.shape
    final_label_k = np.greater_equal(label_nxt_k, 1)

    print final_label_k.shape

    sat_idx  = np.where(final_label_k == 0)[0]
    viol_idx = np.where(final_label_k == 1)[0]

    # print 'sat_idx ', sat_idx
    # print 'viol_idx ', viol_idx

    print 'sat_idx.shape = ', sat_idx.shape
    print 'viol_idx.shape = ',viol_idx.shape

    viol_sat_ratio = len(viol_idx)*1.0/(len(sat_idx) + len(viol_idx))
    print '#viol/#total = %.4f' %(viol_sat_ratio)

    if len(viol_idx) == 0:
        print 'no viol in this run'

    elif viol_sat_ratio < targ_viol_ratio:
        sys_data_sat  = np.take(sys_data, indices = sat_idx, axis = 0)
        sys_data_viol = np.take(sys_data, indices = viol_idx, axis = 0)

        lat_data_sat  = np.take(lat_data, indices = sat_idx, axis = 0)
        lat_data_viol = np.take(lat_data, indices = viol_idx, axis = 0)

        next_info_sat  = np.take(next_info, indices = sat_idx, axis = 0)
        next_info_viol = np.take(next_info, indices = viol_idx, axis = 0)

        next_k_info_sat  = np.take(next_k_info, indices = sat_idx, axis = 0)
        next_k_info_viol = np.take(next_k_info, indices = viol_idx, axis = 0)

        lat_lbl_sat  = np.take(lat_lbl, indices = sat_idx, axis = 0)
        lat_lbl_viol = np.take(lat_lbl, indices = viol_idx, axis = 0)

        lat_next_k_lbl_sat  = np.take(lat_next_k_lbl, indices = sat_idx, axis = 0)
        lat_next_k_lbl_viol = np.take(lat_next_k_lbl, indices = viol_idx, axis = 0)

        sample_time = int(math.ceil(targ_viol_ratio/(1 - targ_viol_ratio)*len(sat_idx)*1.0/len(viol_idx)))
        print 'sample_time = ', sample_time
        print 'after upsample #total = %d, #viol = %d' %(sample_time * len(viol_idx) + len(sat_idx), sample_time * len(viol_idx))

        sys_data = sys_data_sat
        lat_data = lat_data_sat
        next_info = next_info_sat
        next_k_info = next_k_info_sat
        lat_lbl = lat_lbl_sat
        lat_next_k_lbl = lat_next_k_lbl_sat

        for i in range(0, sample_time):
            sys_data = np.concatenate((sys_data, sys_data_viol), axis = 0)

            next_info = np.concatenate((next_info, next_info_viol), axis = 0)
            next_k_info = np.concatenate((next_k_info, next_k_info_viol), axis = 0)

            lat_data = np.concatenate((lat_data, lat_data_viol), axis = 0)
            lat_lbl    = np.concatenate((lat_lbl, lat_lbl_viol), axis = 0)
            lat_next_k_lbl    = np.concatenate((lat_next_k_lbl, lat_next_k_lbl_viol), axis = 0)

        print sys_data.shape, lat_data.shape, next_info.shape, next_k_info.shape, lat_lbl.shape, lat_next_k_lbl.shape

    return sys_data, lat_data, next_info, next_k_info, lat_lbl, lat_next_k_lbl,



#tier_names = ['frontend', 'rate', 'geo', 'search', 'profile']
def parser_subdir(dir):
    global rx_pkts_norm  
    global rx_bytes_norm
    global tx_pkts_norm 
    global tx_bytes_norm 

    global LookForward
    global t_steps
    global qos
    global Upsample

    global targ_viol_ratio

    print'processing ', dir

    tier_cpu_docker_dict = {}

    tier_cpu_limit_dict   = {}

    tier_rx_pkts_dict  = {}
    tier_rx_bytes_dict = {}
    tier_tx_pkts_dict  = {}
    tier_tx_bytes_dict = {}

    tier_rss_dict         = {}
    tier_cache_mem_dict   = {}
    tier_page_faults_dict = {}

    tier_io_sect_dict = {}
    tier_io_serv_dict = {}
    tier_io_wait_dict = {}

    tier_read_req_num_dict  = {}
    tier_write_req_num_dict = {}

    qps_file = ''

    for file in os.listdir(dir):
        if "cpu_util" in file:
            t = file.split('cpu_util_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_cpu_docker_dict[t] = file

        elif "cpu_limit" in file:
            t = file.split('cpu_limit_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_cpu_limit_dict[t] = file

        elif "rx_packets" in file:
            t = file.split('rx_packets_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_rx_pkts_dict[t] = file

        elif "rx_bytes" in file:
            t = file.split('rx_bytes_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_rx_bytes_dict[t] = file

        elif "tx_packets" in file:
            t = file.split('tx_packets_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_tx_pkts_dict[t] = file

        elif "tx_bytes" in file:
            t = file.split('tx_bytes_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_tx_bytes_dict[t] = file

        elif "rss" in file:
            t = file.split('rss_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_rss_dict[t] = file

        elif "cache_mem" in file:
            t = file.split('cache_mem_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_cache_mem_dict[t] = file

        elif "page_faults" in file:
            t = file.split('page_faults_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_page_faults_dict[t] = file

        elif "io_sectors" in file:
            t = file.split('io_sectors_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_io_sect_dict[t] = file

        elif "io_serviced" in file:
            t = file.split('io_serviced_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_io_serv_dict[t] = file

        elif "io_wait" in file:
            t = file.split('io_wait_')[-1].split('.txt')[0]
            assert t in Tiers
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            tier_io_wait_dict[t] = file

        elif 'qps' in file:
            globals()[file] = np.loadtxt(dir+'/'+file, dtype=np.float)
            qps_file = file

    #----------------- qps --------------------#
    iter = 0
    for t in Tiers:
        if iter == 0:
            qps = globals()[qps_file]
        else:
            qps = np.vstack((qps, globals()[qps_file]))
        iter = iter + 1

    for i in range(0, qps.shape[1]- t_steps - LookForward):
        if i == 0:
            qps_data = qps[:, i:i+t_steps].reshape([1, qps.shape[0], t_steps])
        else:
            qps_data = np.vstack((qps_data, qps[:, i:i+t_steps].reshape([1, qps.shape[0], t_steps])))

    qps_data = qps_data.reshape([qps_data.shape[0], 1, qps_data.shape[1], qps_data.shape[2]])


    # print 'qps_data.shape = ', qps_data.shape
    # qps_data = qps_data.reshape([qps_data.shape[0], 1, qps_data.shape[1], qps_data.shape[2]])

    #----------------- qps_next --------------------#
    for i in range(t_steps, qps.shape[1]-LookForward):
        if i == t_steps:
            qps_next = qps[:, i].reshape([1, qps.shape[0]])
        else:
            qps_next = np.vstack((qps_next, qps[:, i].reshape([1, qps.shape[0]])))
    qps_next = qps_next.reshape([qps_next.shape[0], 1, qps_next.shape[1]])
    # print 'qps_next.shape = ', qps_next.shape

     #----------------- qps_next_k --------------------#
    for i in range(t_steps, qps.shape[1]-LookForward):
        if i == t_steps:
            qps_next_k = qps[:, i + 1: i + LookForward + 1].reshape([1, qps.shape[0], LookForward])
        else:
            qps_next_k = np.vstack((qps_next_k, qps[:, i + 1: i + LookForward + 1].reshape([1, qps.shape[0], LookForward])))
    qps_next_k = qps_next_k.reshape([qps_next_k.shape[0], 1, qps_next_k.shape[1], qps_next_k.shape[2]])
    # print 'qps_next.shape = ', qps_next.shape

    # print 'qps_next = ', qps_next
    # print 'qps_next_k = ', qps_next_k

    #----------------- cpu_docker --------------------#
    # tier_cpu_docker_dict.sort()
    iter = 0
    for t in Tiers:
        cpu = tier_cpu_docker_dict[t]
        if iter == 0:
            cpu_util = globals()[cpu]
        else:
            cpu_util = np.vstack((cpu_util, globals()[cpu]))
        iter = iter + 1

    for i in range(0, cpu_util.shape[1]- t_steps - LookForward):
        if i == 0:
            cpu_docker_data = cpu_util[:, i:i+t_steps].reshape([1, cpu_util.shape[0], t_steps])
        else:
            cpu_docker_data = np.vstack((cpu_docker_data, cpu_util[:, i:i+t_steps].reshape([1, cpu_util.shape[0], t_steps])))

    cpu_docker_data = cpu_docker_data.reshape([cpu_docker_data.shape[0], 1, cpu_docker_data.shape[1], cpu_docker_data.shape[2]])

    #----------------- compute rsc --------------------#
    #----------------- cpu_limit --------------------#
    # tier_cpu_limit_dict.sort()
    #print tier_cpu_limit_dict
    iter = 0
    for t in Tiers:
        cpu_limit = tier_cpu_limit_dict[t]
        if iter == 0:
            core_count = globals()[cpu_limit]
        else:
            core_count = np.vstack((core_count, globals()[cpu_limit]))
        iter = iter + 1

    for i in range(0, core_count.shape[1]- t_steps - LookForward):
        if i == 0:
            ncore_data = core_count[:, i:i+t_steps].reshape([1, core_count.shape[0], t_steps])
        else:
            ncore_data = np.vstack((ncore_data, core_count[:, i:i+t_steps].reshape([1, core_count.shape[0], t_steps])))

    ncore_data = ncore_data.reshape([ncore_data.shape[0], 1, ncore_data.shape[1], ncore_data.shape[2]])

    #----------------- cpu_limit_next --------------------#
    for i in range(t_steps, core_count.shape[1] - LookForward):
        if i == t_steps:
            ncore_next = core_count[:, i].reshape([1, core_count.shape[0]])
        else:
            ncore_next = np.vstack((ncore_next, core_count[:, i].reshape([1, core_count.shape[0]])))
    ncore_next = ncore_next.reshape([ncore_next.shape[0], 1, ncore_next.shape[1]])

    #----------------- cpu_limit_next_k --------------------#
    for i in range(t_steps, core_count.shape[1] - LookForward):
        if i == t_steps:
            ncore_next_k = core_count[:, i + 1: i + LookForward + 1].reshape([1, core_count.shape[0], LookForward])
        else:
            ncore_next_k = np.vstack((ncore_next_k, core_count[:, i + 1: i + LookForward + 1].reshape([1, core_count.shape[0], LookForward])))
    ncore_next_k = ncore_next_k.reshape([ncore_next_k.shape[0], 1, ncore_next_k.shape[1], ncore_next_k.shape[2]])

    #----------------- network --------------------#
    #----------------- rx_pkts --------------------#
    # tier_rx_pkts_dict.sort()
    #print tier_core_freq_dict
    iter = 0
    for t in Tiers:
        pkt = tier_rx_pkts_dict[t]
        if iter == 0:
            pkt_rx = globals()[pkt]
        else:
            pkt_rx = np.vstack((pkt_rx, globals()[pkt]))
        iter = iter + 1

    for i in range(0, pkt_rx.shape[1] - t_steps - LookForward):
        if i == 0:
            rx_pkts_data = pkt_rx[:, i:i+t_steps].reshape([1, pkt_rx.shape[0], t_steps])
        else:
            rx_pkts_data = np.vstack((rx_pkts_data, pkt_rx[:, i:i+t_steps].reshape([1, pkt_rx.shape[0], t_steps])))

    rx_pkts_data = rx_pkts_data.reshape([rx_pkts_data.shape[0], 1, rx_pkts_data.shape[1], rx_pkts_data.shape[2]])

    #----------------- rx_pkts_next --------------------#
    for i in range(t_steps, pkt_rx.shape[1] - LookForward):
        if i == t_steps:
            rx_pkts_next = pkt_rx[:, i].reshape([1, pkt_rx.shape[0]])
        else:
            rx_pkts_next = np.vstack((rx_pkts_next, pkt_rx[:, i].reshape([1, pkt_rx.shape[0]])))
    rx_pkts_next = rx_pkts_next.reshape([rx_pkts_next.shape[0], 1, rx_pkts_next.shape[1]])

    #----------------- rx_pkts_next_k --------------------#
    for i in range(t_steps, pkt_rx.shape[1] - LookForward):
        if i == t_steps:
            rx_pkts_next_k = pkt_rx[:, i + 1: i + LookForward + 1].reshape([1, pkt_rx.shape[0], LookForward])
        else:
            rx_pkts_next_k = np.vstack((rx_pkts_next_k, pkt_rx[:, i + 1: i + LookForward + 1].reshape([1, pkt_rx.shape[0], LookForward])))
    rx_pkts_next_k = rx_pkts_next_k.reshape([rx_pkts_next_k.shape[0], 1, rx_pkts_next_k.shape[1], rx_pkts_next_k.shape[2]])

    #----------------- rx_bytes --------------------#
    # tier_rx_bytes_dict.sort()
    #print tier_core_freq_dict
    iter = 0
    for t in Tiers:
        byt = tier_rx_bytes_dict[t]
        if iter == 0:
            byte_rx = globals()[byt]
        else:
            byte_rx = np.vstack((byte_rx, globals()[byt]))
        iter = iter + 1

    for i in range(0, byte_rx.shape[1]- t_steps - LookForward):
        if i == 0:
            rx_bytes_data = byte_rx[:, i:i+t_steps].reshape([1, byte_rx.shape[0], t_steps])
        else:
            rx_bytes_data = np.vstack((rx_bytes_data, byte_rx[:, i:i+t_steps].reshape([1, byte_rx.shape[0], t_steps])))

    rx_bytes_data = rx_bytes_data.reshape([rx_bytes_data.shape[0], 1, rx_bytes_data.shape[1], rx_bytes_data.shape[2]])

    #----------------- rx_bytes_next --------------------#
    for i in range(t_steps, byte_rx.shape[1]-LookForward):
        if i == t_steps:
            rx_bytes_next = byte_rx[:, i].reshape([1, byte_rx.shape[0]])
        else:
            rx_bytes_next = np.vstack((rx_bytes_next, byte_rx[:, i].reshape([1, byte_rx.shape[0]])))
    rx_bytes_next = rx_bytes_next.reshape([rx_bytes_next.shape[0], 1, rx_bytes_next.shape[1]])

    #----------------- rx_bytes_next_k --------------------#
    for i in range(t_steps, byte_rx.shape[1]-LookForward):
        if i == t_steps:
            rx_bytes_next_k = byte_rx[:, i + 1: i + LookForward + 1].reshape([1, byte_rx.shape[0], LookForward])
        else:
            rx_bytes_next_k = np.vstack((rx_bytes_next_k, byte_rx[:, i + 1: i + LookForward + 1].reshape([1, byte_rx.shape[0], LookForward])))
    rx_bytes_next_k = rx_bytes_next_k.reshape([rx_bytes_next_k.shape[0], 1, rx_bytes_next_k.shape[1], rx_bytes_next_k.shape[2]])


    #----------------- tx_pkts --------------------#
    # tier_tx_pkts_dict.sort()
    #print tier_core_freq_dict
    iter = 0
    for t in Tiers:
        pkt = tier_tx_pkts_dict[t]
        if iter == 0:
            pkt_tx = globals()[pkt]
        else:
            pkt_tx = np.vstack((pkt_tx, globals()[pkt]))
        iter = iter + 1

    for i in range(0, pkt_tx.shape[1]- t_steps - LookForward):
        if i == 0:
            tx_pkts_data = pkt_tx[:, i:i+t_steps].reshape([1, pkt_tx.shape[0], t_steps])
        else:
            tx_pkts_data = np.vstack((tx_pkts_data, pkt_tx[:, i:i+t_steps].reshape([1, pkt_tx.shape[0], t_steps])))

    tx_pkts_data = tx_pkts_data.reshape([tx_pkts_data.shape[0], 1, tx_pkts_data.shape[1], tx_pkts_data.shape[2]])

    #----------------- tx_pkts_next --------------------#
    for i in range(t_steps, pkt_tx.shape[1]-LookForward):
        if i == t_steps:
            tx_pkts_next = pkt_tx[:, i].reshape([1, pkt_tx.shape[0]])
        else:
            tx_pkts_next = np.vstack((tx_pkts_next, pkt_tx[:, i].reshape([1, pkt_tx.shape[0]])))
    tx_pkts_next = tx_pkts_next.reshape([tx_pkts_next.shape[0], 1, tx_pkts_next.shape[1]])

    #----------------- tx_pkts_next_k --------------------#
    for i in range(t_steps, pkt_tx.shape[1]-LookForward):
        if i == t_steps:
            tx_pkts_next_k = pkt_tx[:, i + 1:i + LookForward + 1].reshape([1, pkt_tx.shape[0], LookForward])
        else:
            tx_pkts_next_k = np.vstack((tx_pkts_next_k, pkt_tx[:, i + 1:i + LookForward + 1].reshape([1, pkt_tx.shape[0], LookForward])))
    tx_pkts_next_k = tx_pkts_next_k.reshape([tx_pkts_next_k.shape[0], 1, tx_pkts_next_k.shape[1], tx_pkts_next_k.shape[2]])
    

    #----------------- tx_bytes --------------------#
    # tier_tx_bytes_dict.sort()
    #print tier_core_freq_dict
    iter = 0
    for t in Tiers:
        byt = tier_tx_bytes_dict[t]
        if iter == 0:
            byte_tx = globals()[byt]
        else:
            byte_tx = np.vstack((byte_tx, globals()[byt]))
        iter = iter + 1

    for i in range(0, byte_tx.shape[1]- t_steps - LookForward):
        if i == 0:
            tx_bytes_data = byte_tx[:, i:i+t_steps].reshape([1, byte_tx.shape[0], t_steps])
        else:
            tx_bytes_data = np.vstack((tx_bytes_data, byte_tx[:, i:i+t_steps].reshape([1, byte_tx.shape[0], t_steps])))

    tx_bytes_data = tx_bytes_data.reshape([tx_bytes_data.shape[0], 1, tx_bytes_data.shape[1], tx_bytes_data.shape[2]])

    #----------------- tx_bytes_next --------------------#
    for i in range(t_steps, byte_tx.shape[1]-LookForward):
        if i == t_steps:
            tx_bytes_next = byte_tx[:, i].reshape([1, byte_tx.shape[0]])
        else:
            tx_bytes_next = np.vstack((tx_bytes_next, byte_tx[:, i].reshape([1, byte_tx.shape[0]])))
    tx_bytes_next = tx_bytes_next.reshape([tx_bytes_next.shape[0], 1, tx_bytes_next.shape[1]])

    # net_lbl = np.concatenate((rx_pkts_next, tx_pkts_next, rx_bytes_next, tx_bytes_next), axis=1)

    #----------------- tx_bytes_next_k --------------------#
    for i in range(t_steps, byte_tx.shape[1]-LookForward):
        if i == t_steps:
            tx_bytes_next_k = byte_tx[:, i + 1: i + LookForward + 1].reshape([1, byte_tx.shape[0], LookForward])
        else:
            tx_bytes_next_k = np.vstack((tx_bytes_next_k, byte_tx[:, i + 1: i + LookForward + 1].reshape([1, byte_tx.shape[0], LookForward])))
    tx_bytes_next_k = tx_bytes_next_k.reshape([tx_bytes_next_k.shape[0], 1, tx_bytes_next_k.shape[1], tx_bytes_next_k.shape[2]])

    # net_next_lbl = np.concatenate((rx_pkts_next_k, tx_pkts_next_k, rx_bytes_next_k, tx_bytes_next_k), axis=1)


    #----------------- memory --------------------#
    #----------------- rss --------------------#
    # tier_rss_dict.sort()
    iter = 0
    for t in Tiers:
        r = tier_rss_dict[t]
        if iter == 0:
            rss = globals()[r]
        else:
            rss = np.vstack((rss, globals()[r]))
        iter = iter + 1

    for i in range(0, rss.shape[1]- t_steps - LookForward):
        if i == 0:
            rss_data = rss[:, i:i+t_steps].reshape([1, rss.shape[0], t_steps])
        else:
            rss_data = np.vstack((rss_data, rss[:, i:i+t_steps].reshape([1, rss.shape[0], t_steps])))

    rss_data = rss_data.reshape([rss_data.shape[0], 1, rss_data.shape[1], rss_data.shape[2]])

    #----------------- cache_mem --------------------#
    # tier_cache_mem_dict.sort()
    iter = 0
    for t in Tiers:
        cm = tier_cache_mem_dict[t]
        if iter == 0:
            cache_mem = globals()[cm]
        else:
            cache_mem = np.vstack((cache_mem, globals()[cm]))
        iter = iter + 1

    for i in range(0, cache_mem.shape[1]- t_steps - LookForward):
        if i == 0:
            cache_mem_data = cache_mem[:, i:i+t_steps].reshape([1, cache_mem.shape[0], t_steps])
        else:
            cache_mem_data = np.vstack((cache_mem_data, cache_mem[:, i:i+t_steps].reshape([1, cache_mem.shape[0], t_steps])))

    cache_mem_data = cache_mem_data.reshape([cache_mem_data.shape[0], 1, cache_mem_data.shape[1], cache_mem_data.shape[2]])

    #----------------- page_faults --------------------#
    # tier_page_faults_dict.sort()
    iter = 0
    for t in Tiers:
        pf = tier_page_faults_dict[t]
        if iter == 0:
            page_faults = globals()[pf]
        else:
            page_faults = np.vstack((page_faults, globals()[pf]))
        iter = iter + 1

    for i in range(0, page_faults.shape[1]- t_steps - LookForward):
        if i == 0:
            page_faults_data = page_faults[:, i:i+t_steps].reshape([1, page_faults.shape[0], t_steps])
        else:
            page_faults_data = np.vstack((page_faults_data, page_faults[:, i:i+t_steps].reshape([1, page_faults.shape[0], t_steps])))

    page_faults_data = page_faults_data.reshape([page_faults_data.shape[0], 1, page_faults_data.shape[1], page_faults_data.shape[2]])


    #----------------- io --------------------#
    #----------------- io_sectors --------------------#
    # tier_io_sect_dict.sort()
    iter = 0
    for t in Tiers:
        iosec = tier_io_sect_dict[t]
        if iter == 0:
            io_sect = globals()[iosec]
        else:
            io_sect = np.vstack((io_sect, globals()[iosec]))
        iter = iter + 1

    for i in range(0, io_sect.shape[1]- t_steps - LookForward):
        if i == 0:
            io_sect_data = io_sect[:, i:i+t_steps].reshape([1, io_sect.shape[0], t_steps])
        else:
            io_sect_data = np.vstack((io_sect_data, io_sect[:, i:i+t_steps].reshape([1, io_sect.shape[0], t_steps])))

    io_sect_data = io_sect_data.reshape([io_sect_data.shape[0], 1, io_sect_data.shape[1], io_sect_data.shape[2]])

    #----------------- io_serviced --------------------#
    # tier_io_serv_dict.sort()
    iter = 0
    for t in Tiers:
        ioserv = tier_io_serv_dict[t]
        if iter == 0:
            io_serv = globals()[ioserv]
        else:
            io_serv = np.vstack((io_serv, globals()[ioserv]))
        iter = iter + 1

    for i in range(0, io_serv.shape[1]- t_steps - LookForward):
        if i == 0:
            io_serv_data = io_serv[:, i:i+t_steps].reshape([1, io_serv.shape[0], t_steps])
        else:
            io_serv_data = np.vstack((io_serv_data, io_serv[:, i:i+t_steps].reshape([1, io_serv.shape[0], t_steps])))

    io_serv_data = io_serv_data.reshape([io_serv_data.shape[0], 1, io_serv_data.shape[1], io_serv_data.shape[2]])

    #----------------- io_wait --------------------#
    # tier_io_wait_dict.sort()
    iter = 0
    for t in Tiers:
        iow = tier_io_wait_dict[t]
        if iter == 0:
            io_wait = globals()[iow]
        else:
            io_wait = np.vstack((io_wait, globals()[iow]))
        iter = iter + 1

    for i in range(0, io_wait.shape[1]- t_steps - LookForward):
        if i == 0:
            io_wait_data = io_wait[:, i:i+t_steps].reshape([1, io_wait.shape[0], t_steps])
        else:
            io_wait_data = np.vstack((io_wait_data, io_wait[:, i:i+t_steps].reshape([1, io_wait.shape[0], t_steps])))

    io_wait_data = io_wait_data.reshape([io_wait_data.shape[0], 1, io_wait_data.shape[1], io_wait_data.shape[2]])


    #--------------------- concatenate ---------------------#
    # next_info = np.concatenate((ncore_next, core_freq_next, qps_next, rx_pkts_next, rx_bytes_next, tx_pkts_next, tx_bytes_next), axis=1)
    # next_info = np.concatenate((ncore_next, core_freq_next, read_qps_next, write_qps_next), axis=1)
    # next_k_info = np.concatenate((ncore_next_k, core_freq_next_k, read_qps_next_k, write_qps_next_k), axis=1)

    # next_info = np.concatenate((ncore_next, core_freq_next, read_qps_next, write_qps_next), axis=1)
    # next_k_info = np.concatenate((ncore_next_k, core_freq_next_k, read_qps_next_k, write_qps_next_k), axis=1)

    # sys_data = np.concatenate((cpu_mpstat_data, cpu_docker_data, ncore_data, core_freq_data, read_qps_data, write_qps_data,
    #                             rx_pkts_data, rx_bytes_data, tx_pkts_data, tx_bytes_data,
    #                             rss_data, cache_mem_data, page_faults_data, io_sect_data, io_serv_data, io_wait_data), axis=1)

    next_info = np.concatenate((ncore_next, qps_next), axis=1)
    next_k_info = np.concatenate((ncore_next_k, qps_next_k), axis=1)

    sys_data = np.concatenate((cpu_docker_data, ncore_data, qps_data,
                                rx_pkts_data, rx_bytes_data, tx_pkts_data, tx_bytes_data,
                                rss_data, cache_mem_data, page_faults_data, io_sect_data, io_serv_data, io_wait_data), axis=1)

    #--------------------- latency ---------------------#
    lat_list = []
    for file in os.listdir(dir):
        if "e2e" in file:
            name = re.sub('e2e_lat_', '', file)
            name = re.sub('.txt', '', name)
            globals()[name] = np.loadtxt(dir+'/'+file, dtype=np.float)
            lat_list.append(name)

    iter = 0
    for p in ['95.0', '96.0', '97.0', '98.0', '99.0']:
        if iter == 0:
            lat = globals()[p]
        else:
            lat = np.vstack((lat, globals()[p]))
        iter = iter + 1

    for i in range(0, lat.shape[1]- t_steps - LookForward):
        if i == 0:
            lat_data = lat[:, i:i+t_steps].reshape([1, lat.shape[0], t_steps])
        else:
            lat_data = np.vstack((lat_data, lat[:, i:i+t_steps].reshape([1, lat.shape[0], t_steps])))
    lat_data = lat_data.reshape([lat_data.shape[0], lat_data.shape[1], 1, lat_data.shape[2]])

    for i in range(t_steps, lat.shape[1]-LookForward):
        if i == t_steps:
            lat_lbl = lat[:, i].reshape([1, lat.shape[0]])
        else:
            lat_lbl = np.vstack((lat_lbl, lat[:, i].reshape([1, lat.shape[0]])))

    for i in range(t_steps, lat.shape[1]-LookForward):
        if i == t_steps:
            lat_next_k_lbl = lat[:, i + 1:i + LookForward + 1].reshape([1, lat.shape[0], LookForward])
        else:
            lat_next_k_lbl = np.vstack((lat_next_k_lbl, lat[:, i + 1:i + LookForward + 1].reshape([1, lat.shape[0], LookForward])))        
    '''
    #--------------------- per tier latency ---------------------#
    lat_tier_list = []
    for file in os.listdir(dir):
        if "_lat" in file and "95.0" in file and "e2e" not in file:
            lat_tier_list.append(file)

    l_count = 0
    for l in lat_tier_list:
        iter = 0
        for p in ['95.0', '96.0', '97.0', '98.0', '99.0']:
            name = re.sub('95.0', p, l)
            if iter == 0:
                lat_tier = np.loadtxt(dir+'/'+name, dtype=np.float)
            else:
                lat_tier = np.vstack((lat_tier, np.loadtxt(dir+'/'+name, dtype=np.float)))
            iter = iter + 1
        for i in range(0, lat_tier.shape[1]- t_steps - LookForward):
            if i == 0:
                lat_t_data = lat_tier[:, i:i+t_steps].reshape([1, lat_tier.shape[0], t_steps])
            else:
                lat_t_data = np.vstack((lat_t_data, lat_tier[:, i:i+t_steps].reshape([1, lat_tier.shape[0], t_steps])))
        lat_t_data = lat_t_data.reshape([lat_t_data.shape[0], lat_t_data.shape[1], 1, lat_t_data.shape[2]])

        if l_count == 0:
            lat_tier_data = lat_t_data
        else:
            lat_tier_data = np.concatenate((lat_tier_data, lat_t_data), axis=2)

        for j in range(t_steps, lat.shape[1]-LookForward):

            if j == t_steps:
                lat_label_cont = lat_tier[:, j].reshape([1, lat_tier.shape[0]])
            else:
                lat_label_cont = np.vstack((lat_label_cont, lat_tier[:, j].reshape([1, lat_tier.shape[0]])))
        lat_label_cont = lat_label_cont.reshape([lat_label_cont.shape[0], lat_label_cont.shape[1], 1])
        if l_count == 0:
            lat_lbl_cont = lat_label_cont
        else:
            lat_lbl_cont = np.concatenate((lat_lbl_cont, lat_label_cont), axis=2)
        l_count = l_count + 1

    #lat_data = np.concatenate((lat_data, lat_tier_data), axis=2)
    '''
    # stabk lat_lbl & lat_next_k_lbl
    lat_lbl       = lat_lbl.reshape([lat_lbl.shape[0], lat_lbl.shape[1], 1])
    # no need to reshape lat_next_k
    # lat_next_k_lbl  = lat_next_k_lbl.reshape([lat_next_k_lbl.shape[0], lat_next_k_lbl.shape[1], 1])
    # lat_lbl       = np.concatenate((lat_lbl, lat_lbl_cont), axis=2)

    shuffle_in_unison([sys_data, lat_data, next_info, next_k_info, lat_lbl, lat_next_k_lbl])

    print sys_data.shape, lat_data.shape, next_info.shape, next_k_info.shape, lat_lbl.shape, lat_next_k_lbl.shape

    num_val = int(lat_lbl.shape[0] * 0.1)

    sys_data_v = sys_data[:num_val,:,:,:]
    sys_data_t = sys_data[num_val:,:,:,:]

    lat_data_v = lat_data[:num_val,:,:,:]
    lat_data_t = lat_data[num_val:,:,:,:]

    next_info_v = next_info[:num_val,:,:]
    next_info_t = next_info[num_val:,:,:]

    next_k_info_v = next_k_info[:num_val,:,:,:]
    next_k_info_t = next_k_info[num_val:,:,:,:]

    lat_lbl_v = lat_lbl[:num_val,:,:]
    lat_lbl_t = lat_lbl[num_val:,:,:]

    lat_next_k_lbl_v = lat_next_k_lbl[:num_val,:,:]
    lat_next_k_lbl_t = lat_next_k_lbl[num_val:,:,:]

    if Upsample:
        sys_data_t, lat_data_t, next_info_t, next_k_info_t, lat_lbl_t, lat_next_k_lbl_t = upsample(sys_data_t, lat_data_t, next_info_t, next_k_info_t, lat_lbl_t, lat_next_k_lbl_t)
        sys_data_v, lat_data_v, next_info_v, next_k_info_v, lat_lbl_v, lat_next_k_lbl_v = upsample(sys_data_v, lat_data_v, next_info_v, next_k_info_v, lat_lbl_v, lat_next_k_lbl_v)

    return sys_data_t, lat_data_t, next_info_t, next_k_info_t, lat_lbl_t, lat_next_k_lbl_t, sys_data_v, lat_data_v, next_info_v, next_k_info_v, lat_lbl_v, lat_next_k_lbl_v

def shuffle_in_unison(arr):
    rnd_state = np.random.get_state()
    for a in arr:
        np.random.set_state(rnd_state)
        np.random.shuffle(a)
        np.random.set_state(rnd_state)
        # np.random.shuffle(b)
        # np.random.set_state(rnd_state)
        # np.random.shuffle(c)
        # np.random.set_state(rnd_state)
        # np.random.shuffle(d)
        # np.random.set_state(rnd_state)
        # np.random.shuffle(e)
        # np.random.set_state(rnd_state)
        # np.random.shuffle(f)

def main():
    print 'in main'
    global LookForward
    global Upsample

    parser = argparse.ArgumentParser()
    parser.add_argument('--log-dir', type=str, dest='log_dir', required=True)
    parser.add_argument('--look-forward', type=int, default=4, dest='look_forward', help='[+1, +look_forward]')
    parser.add_argument('--upsample', action='store_true', dest='upsample')
    args = parser.parse_args()

    LookForward = args.look_forward
    assert LookForward >= 1
    dir = args.log_dir
    Upsample = args.upsample

    count = 0
    for file in os.listdir(dir):
        #if ("10k" in sub_file) or ("9k" in sub_file) or ("8k" in sub_file) or ("7k" in sub_file) or ("6k" in sub_file) or ("5k" in sub_file) or ("4k" in sub_file):
        if ("diurnal" in file) or ("rps" in file):
            if len(os.listdir(dir+'/'+file)) == 0:
                continue
            sys_data_t, lat_data_t, next_info_t, next_k_info_t, lat_lbl_t, lat_next_k_lbl_t, sys_data_v, lat_data_v, next_info_v, next_k_info_v, lat_lbl_v, lat_next_k_lbl_v = parser_subdir(dir+'/'+file+'/')
            if count == 0:
                glob_sys_data_train = sys_data_t
                glob_lat_data_train = lat_data_t
                # glob_qps_data = qps_data
                glob_next_info_train      = next_info_t
                glob_next_k_info_train    = next_k_info_t
                # glob_next_qps  = next_qps
                glob_lat_lbl_train        = lat_lbl_t
                glob_lat_next_k_lbl_train  = lat_next_k_lbl_t

                glob_sys_data_valid = sys_data_v
                glob_lat_data_valid = lat_data_v
                # glob_qps_data = qps_data
                glob_next_info_valid      = next_info_v
                glob_next_k_info_valid    = next_k_info_v
                # glob_next_qps  = next_qps
                glob_lat_lbl_valid        = lat_lbl_v
                glob_lat_next_k_lbl_valid  = lat_next_k_lbl_v
            else:
                glob_sys_data_train = np.concatenate((glob_sys_data_train,sys_data_t),axis = 0)
                glob_lat_data_train = np.concatenate((glob_lat_data_train,lat_data_t),axis = 0)
                # glob_qps_data = np.concatenate((glob_qps_data,qps_data),axis = 0)

                glob_next_info_train      = np.concatenate((glob_next_info_train,next_info_t), axis = 0)
                glob_next_k_info_train    = np.concatenate((glob_next_k_info_train, next_k_info_t), axis = 0)
                # glob_next_qps  = np.concatenate((glob_next_qps,next_qps), axis = 0)
                glob_lat_lbl_train      = np.concatenate((glob_lat_lbl_train,lat_lbl_t), axis = 0)
                glob_lat_next_k_lbl_train   = np.concatenate((glob_lat_next_k_lbl_train,lat_next_k_lbl_t), axis = 0)

                glob_sys_data_valid = np.concatenate((glob_sys_data_valid,sys_data_v),axis = 0)
                glob_lat_data_valid = np.concatenate((glob_lat_data_valid,lat_data_v),axis = 0)
                # glob_qps_data = np.concatenate((glob_qps_data,qps_data),axis = 0)

                glob_next_info_valid      = np.concatenate((glob_next_info_valid,next_info_v), axis = 0)
                glob_next_k_info_valid    = np.concatenate((glob_next_k_info_valid, next_k_info_v), axis = 0)
                # glob_next_qps  = np.concatenate((glob_next_qps,next_qps), axis = 0)
                glob_lat_lbl_valid      = np.concatenate((glob_lat_lbl_valid,lat_lbl_v), axis = 0)
                glob_lat_next_k_lbl_valid   = np.concatenate((glob_lat_next_k_lbl_valid,lat_next_k_lbl_v), axis = 0)
            count = count + 1
    #print glob_sys_data.shape[0]
    #print glob_lat_data.shape[0]
    #print glob_next_info.shape[0]
    #print glob_lat_lbl.shape[0]

    # num_val = int(0.1 * float(glob_sys_data.shape[0]))
    # print 'total_num: ', glob_sys_data.shape[0]
    # print 'valid_num: ', num_val
    # shuffle_in_unison([glob_sys_data, glob_lat_data, 
    #     glob_next_info, glob_next_k_info, glob_lat_lbl,
    #     glob_lat_next_k_lbl])

    # glob_sys_data_valid = glob_sys_data[:num_val,:,:,:]
    # glob_sys_data_train = glob_sys_data[num_val:,:,:,:]
    # glob_lat_data_valid = glob_lat_data[:num_val,:,:,:]
    # glob_lat_data_train = glob_lat_data[num_val:,:,:,:]
    # # glob_qps_data_valid = glob_qps_data[:num_val,:,:,:]
    # # glob_qps_data_train = glob_qps_data[num_val:,:,:,:]

    # glob_next_info_valid = glob_next_info[:num_val,:,:]
    # glob_next_info_train = glob_next_info[num_val:,:,:]

    # glob_next_k_info_valid = glob_next_k_info[:num_val,:,:]
    # glob_next_k_info_train = glob_next_k_info[num_val:,:,:]

    # # glob_next_qps_valid = glob_next_qps[:num_val,:,:]
    # # glob_next_qps_train = glob_next_qps[num_val:,:,:]
    # glob_lat_lbl_valid = glob_lat_lbl[:num_val,:]
    # glob_lat_lbl_train = glob_lat_lbl[num_val:,:]

    # glob_lat_next_k_lbl_valid = glob_lat_next_k_lbl[:num_val,:]
    # glob_lat_next_k_lbl_train = glob_lat_next_k_lbl[num_val:,:]

    # glob_net_lbl_valid = glob_net_lbl[:num_val,:]
    # glob_net_lbl_train = glob_net_lbl[num_val:,:]


    print 'glob_sys_data_train.shape = ',  glob_sys_data_train.shape
    print 'glob_lat_data_train.shape = ',  glob_lat_data_train.shape
    # print 'glob_qps_data_train.shape = ',  glob_qps_data_train.shape
    print 'glob_next_info_train.shape = ', glob_next_info_train.shape
    print 'glob_next_k_info_train.shape = ', glob_next_k_info_train.shape
    # print 'glob_next_qps_train.shape = ', glob_next_qps_train.shape
    print 'glob_lat_lbl_train.shape = ',   glob_lat_lbl_train.shape
    print 'glob_lat_next_k_lbl_train.shape = ',   glob_lat_next_k_lbl_train.shape

    # glob_lat_lbl_train = glob_lat_lbl_train[:,:,0].reshape((glob_lat_lbl_train.shape[0], glob_lat_lbl_train.shape[1], 1))
    # glob_lat_lbl_train = np.concatenate((glob_lat_lbl_train, glob_lat_next_k_lbl_train), axis=2)
    
    # glob_lat_lbl_valid = glob_lat_lbl_valid[:,:,0].reshape((glob_lat_lbl_valid.shape[0], glob_lat_lbl_valid.shape[1], 1))
    # glob_lat_lbl_valid = np.concatenate((glob_lat_lbl_valid, glob_lat_next_k_lbl_valid), axis=2)

    print "latency label shapes:", glob_lat_lbl_train.shape, glob_lat_lbl_valid.shape
    #sys.exit()
    if not os.path.isdir("./data_+" + str(LookForward) + "s/"):
        os.makedirs("./data_+" + str(LookForward) + "s/")

    np.save("./data_+" + str(LookForward) + "s/sys_data_train", glob_sys_data_train)
    np.save("./data_+" + str(LookForward) + "s/sys_data_valid", glob_sys_data_valid)
    np.save("./data_+" + str(LookForward) + "s/lat_data_train", glob_lat_data_train)
    np.save("./data_+" + str(LookForward) + "s/lat_data_valid", glob_lat_data_valid)
    # np.save("./data_+1s/qps_data_train", glob_qps_data_train)
    # np.save("./data_+1s/qps_data_valid", glob_qps_data_valid)
    np.save("./data_+" + str(LookForward) + "s/nxt_data_train", glob_next_info_train)
    np.save("./data_+" + str(LookForward) + "s/nxt_data_valid", glob_next_info_valid)

    np.save("./data_+" + str(LookForward) + "s/nxt_k_data_train", glob_next_k_info_train)
    np.save("./data_+" + str(LookForward) + "s/nxt_k_data_valid", glob_next_k_info_valid)
    # np.save("./data_+1s/nxt_qps_train", glob_next_qps_train)
    # np.save("./data_+1s/nxt_qps_valid", glob_next_qps_valid)
    np.save("./data_+" + str(LookForward) + "s/train_label",  glob_lat_lbl_train)
    np.save("./data_+" + str(LookForward) + "s/valid_label",  glob_lat_lbl_valid)

    np.save("./data_+" + str(LookForward) + "s/nxt_k_train_label",  glob_lat_next_k_lbl_train)
    np.save("./data_+" + str(LookForward) + "s/nxt_k_valid_label",  glob_lat_next_k_lbl_valid)
    
    # np.save("./data_+" + str(LookForward) + "s/train_net_label",  glob_net_lbl_train)
    # np.save("./data_+" + str(LookForward) + "s/valid_net_label",  glob_net_lbl_valid)

    # np.save("./data_+1" + str(LookForward) + "s/train_net_nxt_label",  glob_net_next_lbl_train)
    # np.save("./data_+1" + str(LookForward) + "s/valid_net_nxt_label",  glob_net_next_lbl_valid)

if __name__ == '__main__':
    main()
