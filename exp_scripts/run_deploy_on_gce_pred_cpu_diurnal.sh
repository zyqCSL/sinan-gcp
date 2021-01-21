cd ../
python3 master_deploy_diurnal_social.py --user-name mingyulianggce \
	--stack-name sinan-socialnet \
	--min-users 4 --max-users 36 --users-step 4 \
	--exp-time 120 --measure-interval 1 --slave-port 40011 \
	--deploy-config social_swarm.json \
	--gpu-config pred_cpu.json --gpu-port 40010 \
	--mab-config social_mab.json