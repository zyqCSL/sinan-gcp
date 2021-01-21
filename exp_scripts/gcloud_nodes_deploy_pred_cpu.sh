cd ../
python3 gcloud_nodes_deploy.py --username mingyulianggce \
	--init-gcloud \
	--deploy-config social_swarm.json \
	--gpu-config pred_cpu.json