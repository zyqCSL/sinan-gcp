# SINAN-GCP
## Prerequisites: 
- Python 3.5+
- Python 2.7 (for plotting)
- Install & set up Google Cloud SDK (https://cloud.google.com/sdk/docs/how-to). In order to reproduce results presented in the paper, the cpu qupta (Compute Engine API) of your Google Cloud project should be no less than 500.

## Repo structure & script usage
### benchmarks 
benchmarks directory contain the source codes of tested benchmarks. 

For SocialNetwork application (benchmarks/socialNetwork-ml-swarm), we added two compute-intensive machine learning microservices (text-filter and media-filter), and also add image data to user posts (previously posts only include text), in order to make the application a little more representative than original versions. We also provide a warm up script (benchmarks/socialNetwork-ml-swarm/setup_social_graph_init_data_sync.py) for the application, to fill the social-network friendship graph, and to fill the databases with posts

### config
config contains configuration files of cluster, scheduling actions, and inference engine

### misc
scripts to generate config files

### exp
scripts for running experiments

### locust
codes related to workload generation

### ml
scirpts for ml modeling data prepration, training, deployment and fine-tunning (for different user workload patterns)

### src
utilization functions

### scripts
initialization scripts for GCE VMs

### root directory
master_data_collect_social.py  --- master for data collection

master_deploy_social.py  --- master for running deployment experiment of socialNetwork

master_deploy_diurnal_social.py --- master for running deployment experiment of socialNetwork with diurnal load

slave_data_collect.py --- slave for data collection & deployment

gcloud.py --- set up gcloud cluster & collect data

gcloud_deploy.py --- set up glcoud cluster & deploy socialNetwork

gcloud_deploy_diurnal.py --- set up gcloud cluster & deploy socialNetwork with diurnal rps pattern

## Reproducing experiment results
Following instructions assume that users start from git root directory. Before executing any shell script, users should make sure to change the '--username' argument in the shell script to his own Google Cloud user name. When execution of scripts is completed, system execution log should be in the logs directory of the master node. Users can copy the data to local machine with scp (the ssh keys are automatically generated and stored in keys directory)

### Deployment experiment with static rps and identical workload
This script tests the deployment of Sinan under static RPS, with the workload composition the same as training data (w0 in Figure 13 and Figure 14 in the paper). For detailed information on workload characterization, please check locust/src/social_rps_10.py
```bash
cd exp_scripts
./gcloud_deploy_cpu_pred.sh
```

### Deployment experiment with static rps and skewed workload
This script tests the deployment of Sinan under static RPS, with the workload composition slightly skewed from training data (w1-w3 in Figure 13 and Figure 14 in the paper). For detailed information on workload characterization, please check locust/src/social_rps_10_v*.py
```bash
cd exp_scripts
./gcloud_deploy_cpu_pred_skewed.sh x
```
x can be set to 1, 2 and 3.

### Deployment experiment with diurnal rps pattern
This script tests the deployment of Sinan a diurnal RPS pattern
```bash
cd exp_scripts
./gcloud_deploy_diurnal_cpu_pred.sh
```

### Data processing
```bash
python data_proc/plot.py dir_name
```
dir_name should be the directory that contains system execution log. For example, logs/deploy_data in the static load experiments. For specific log directory, check DataDir variable in the master_deploy* scripts
