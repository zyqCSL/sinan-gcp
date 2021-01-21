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
usermod -aG docker mingyulianggce
docker pull yz2297/social-network-ml-swarm:latest --quiet

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
git clone https://github.com/zyqCSL/sinan-gcp.git /home/mingyulianggce/sinan-gcp
sudo chown -R mingyulianggce:mingyulianggce /home/mingyulianggce/sinan-gcp

# for locust
mkdir /home/mingyulianggce/sinan_locust_log
sudo chmod -R 777 /home/mingyulianggce/sinan_locust_log

# finish flag
touch /home/mingyulianggce/startup_finished
chown mingyulianggce:mingyulianggce /home/mingyulianggce/startup_finished
