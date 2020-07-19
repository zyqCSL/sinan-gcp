cd ../
python3 master_deploy_social.py --user-name yz2297 \
	--stack-name sinan-socialnet \
	--min-users 5 --max-users 45 --users-step 5 \
	--exp-time 300 --measure-interval 1 --slave-port 40011 \
	--deploy-config social_swarm.json \
	--gpu-config pred_cpu.json --gpu-port 40010 \
	--mab-config social_mab.json