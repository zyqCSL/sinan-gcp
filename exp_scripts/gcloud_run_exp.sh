cd ../
python3 gcloud.py --username yz2297 \
	--init-gcloud \
	--deploy-config social_swarm.json \
	--stack-name sinan-socialnet \
	--min-users 4 --max-users 48 --users-step 2 \
	--exp-time 1200 --measure-interval 1 --slave-port 40011 \
	--mab-config social_mab.json