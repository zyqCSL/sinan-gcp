python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.1 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_01_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.2 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_02_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.3 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_03_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.4 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_04_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.5 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_05_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.6 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_06_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.7 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_07_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.8 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_08_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 0.9 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_09_cnv
python  train_cnvnet.py --num-examples 29502 --lr 0.0001 --gpus 0,1 --data-dir ../logs/gcp_simple_sys_data_next_5s \
	--sample 1.0 --wd 0.001 --pretrain-model-prefix ./model/pre_cnv --load-epoch 200 --log finetune_10_cnv