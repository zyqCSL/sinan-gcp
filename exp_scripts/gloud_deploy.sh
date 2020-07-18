cd ../
python3 gcloud_deploy.py --user-name yz2297 \
	--init-gcloud \
	--deploy-config social_swarm.json \
	--stack-name sinan-socialnet \
	--min-users 5 --max-users 45 --users-step 5 \
	--exp-time 300 \
	--measure-interval 1 --slave-port 40011 \
	--gpu-port 40010 \
	--gpu-config gpu.json \
	--mab-config social_mab.json