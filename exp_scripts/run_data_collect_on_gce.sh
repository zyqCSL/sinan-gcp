cd ../
python3 master_data_collect_social.py --user-name mingyulianggce \
	--stack-name sinan-socialnet \
	--min-users 4 --max-users 48 --users-step 2 \
	--exp-time 1200 --measure-interval 1 --slave-port 40011 --deploy-config social_swarm.json \
	--mab-config social_mab.json