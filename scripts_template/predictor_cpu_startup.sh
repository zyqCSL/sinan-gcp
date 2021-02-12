#!/bin/bash

# install docker-ce, pull images
apt-get -y update
apt-get -y --no-install-recommends install \
  apt-transport-https \
  ca-certificates \
  curl \
  wget \
  software-properties-common
add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
apt-get update
apt-get install -y docker-ce
usermod -aG docker SINANUSER
docker pull sailresearch/social-network-ml-swarm:latest --quiet

# python packages
apt-get -y --no-install-recommends install \
  python \
  python-pip \
  python-setuptools \
  libgomp1

pip install argparse \
  pandas \
  numpy \
  cmake

# set up ml
pip install --no-cache-dir mxnet-mkl
pip install --no-cache-dir xgboost

# git clones
git clone https://github.com/zyqCSL/sinan-gcp.git  --branch artifact_eval /home/SINANUSER/sinan-gcp
sudo chown -R SINANUSER:SINANUSER /home/SINANUSER/sinan-gcp

# for locust
mkdir /home/SINANUSER/sinan_locust_log
sudo chmod -R 777 /home/SINANUSER/sinan_locust_log

# finish flag
touch /home/SINANUSER/startup_finished
chown SINANUSER:SINANUSER /home/SINANUSER/startup_finished