script='socialml_rps_10_v'${1}'.py'
cd ../
python3 gcloud_deploy.py --username mingyulianggce \
	--init-gcloud \
	--deploy-config social_swarm.json \
	--stack-name sinan-socialnet \
	--min-users 5 --max-users 45 --users-step 5 \
	--exp-time 300 \
	--measure-interval 1 --slave-port 40011 \
	--gpu-port 40010 \
	--gpu-config pred_cpu.json \
	--mab-config social_mab.json \
	--locust-script $script