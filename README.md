# SINAN-GCP

```bash
python /home/${USER}/sinan-gcp/scripts/gcloud.py \
    --username=${USER} \
    --stack-name=social-network-ml-swarm \
    --compose-file=docker-compose-swarm-labeled \
    --instances=27 \
    --cpus=2 \
    --instance-name=sinan-test \
    --rps=500 \
    --init-gcloud
```
