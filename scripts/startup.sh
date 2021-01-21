#!/bin/bash

# install docker-ce, pull images
apt-get -y update
apt-get -y --no-install-recommends install \
  apt-transport-https \
  ca-certificates \
  curl \
  software-properties-common
add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
apt-get update
apt-get install -y docker-ce
usermod -aG docker mingyulianggce
docker pull sailresearch/social-network-ml-swarm:latest --quiet

# python packages
apt-get -y --no-install-recommends install \
  python3 \
  python3-pip \
  python3-setuptools

pip3 install argparse \
  pandas \
  numpy \
  docker \
  pyyaml \
  aiohttp \
  asyncio

# # pre-requirements for wrk2
# apt-get -y --no-install-recommends install libssl-dev \
#   libz-dev \
#   luarocks \
#   gcc
# luarocks install luasocket

# git clones
# git clone https://github.com/zyqCSL/sinan-gcp.git /home/zzhou612/sinan-gcp
# sudo chown -R zzhou612:zzhou612 /home/zzhou612/sinan-gcp
git clone https://github.com/zyqCSL/sinan-gcp.git --branch artifact_eval /home/mingyulianggce/sinan-gcp
sudo chown -R mingyulianggce:mingyulianggce /home/mingyulianggce/sinan-gcp

# for locust
mkdir /home/mingyulianggce/sinan_locust_log
sudo chmod -R 777 /home/mingyulianggce/sinan_locust_log

# finish flag
touch /home/mingyulianggce/startup_finished
chown mingyulianggce:mingyulianggce /home/mingyulianggce/startup_finished
