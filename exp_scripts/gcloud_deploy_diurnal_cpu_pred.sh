cd ../
python3 gcloud_deploy_diurnal.py --username mingyulianggce \
	--init-gcloud \
	--deploy-config social_swarm.json \
	--stack-name sinan-socialnet \
	--min-users 4 --max-users 36 --users-step 4 \
	--exp-time 120 \
	--measure-interval 1 --slave-port 40011 \
	--gpu-port 40010 \
	--gpu-config pred_cpu.json \
	--mab-config social_mab.json