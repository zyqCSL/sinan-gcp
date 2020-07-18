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
usermod -aG docker yz2297
docker pull yz2297/social-network-ml-swarm:latest --quiet

# python packages
apt-get -y --no-install-recommends install \
  python \
  python-pip \
  python-setuptools

pip install argparse \
  pandas \
  numpy \
  cmake

# set up cuda
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-ubuntu1804.pin
mv cuda-ubuntu1804.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget http://developer.download.nvidia.com/compute/cuda/10.2/Prod/local_installers/cuda-repo-ubuntu1804-10-2-local-10.2.89-440.33.01_1.0-1_amd64.deb
dpkg -i cuda-repo-ubuntu1804-10-2-local-10.2.89-440.33.01_1.0-1_amd64.deb
apt-key add /var/cuda-repo-10-2-local-10.2.89-440.33.01/7fa2af80.pub
apt-get update
apt-get -y --no-install-recommends install cuda

sudo pip install --no-cache-dir mxnet-cu102
sudo pip install --no-cache-dir xgboost

# git clones
git clone https://github.com/zyqCSL/sinan-gcp.git /home/yz2297/sinan-gcp
sudo chown -R yz2297:yz2297 /home/yz2297/sinan-gcp

# for locust
mkdir /home/yz2297/sinan_locust_log
sudo chmod -R 777 /home/yz2297/sinan_locust_log

# finish flag
touch /home/yz2297/startup_finished
chown yz2297:yz2297 /home/yz2297/startup_finished
