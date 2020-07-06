# multiclass classification
import pandas
import mxnet as mx
import xgboost as xgb
import numpy as np
import time
# load data
import matplotlib.pyplot as plt
import os
import argparse
import math

def _load_model(args, rank=0):
    if 'load_epoch' not in args or args.load_epoch is None:
        return (None, None, None)
    assert args.model_prefix is not None
    model_prefix = args.model_prefix
    if rank > 0 and os.path.exists("%s-%d-symbol.json" % (model_prefix, rank)):
        model_prefix += "-%d" % (rank)
    sym, arg_params, aux_params = mx.model.load_checkpoint(
        model_prefix, args.load_epoch)
    # logging.info('Loaded model %s_%04d.params', model_prefix, args.load_epoch)
    return (sym, arg_params, aux_params)

TimeSteps = 5
QoS = 300.0

def shuffle_in_unison(arr):
    rnd_state = np.random.get_state()
    for i in range(0, 10):
        for a in arr:
            np.random.set_state(rnd_state)
            np.random.shuffle(a)
            np.random.set_state(rnd_state)

def main():
    global QoS
    look_forward = args.look_forward

    mx.random.seed(2333)
    np.random.seed(2333)
    data_dir = args.data_dir


    #--------- data shape for look_forward = 6, which is the last dimension in next_k_lbl ---------#
    # glob_sys_data_train.shape =  (samples, 13, 28, 5)
    # glob_lat_data_train.shape =  (samples, 5, 1, 5)
    # glob_next_info_train.shape =  (samples, 2, 28)

    #---------------------- training data ----------------------#
    sys_data_t     = np.load(data_dir + '/sys_data_train.npy')
    nxt_data_t     = np.load(data_dir + '/nxt_data_train.npy')
    nxt_k_data_t   = np.load(data_dir + '/nxt_k_data_train.npy')
    lat_data_t     = np.load(data_dir + '/lat_data_train.npy')

    print nxt_k_data_t.shape

    #nxt_k_data_t = nxt_k_data_t[:,2,:,:]    # only keep qps
    sys_data_t = sys_data_t.reshape(sys_data_t.shape[0],-1)
    nxt_data_t = nxt_data_t.reshape(nxt_data_t.shape[0], -1)
    nxt_k_data_t = nxt_k_data_t.reshape(nxt_k_data_t.shape[0], -1)
    lat_data_t = lat_data_t.reshape(lat_data_t.shape[0], -1)

    X_train = np.concatenate((sys_data_t, nxt_data_t, nxt_k_data_t, lat_data_t), axis=1)

    label_t = np.load(data_dir + '/train_label.npy')
    label_t_nxt_k = np.load(data_dir + '/nxt_k_train_label.npy')
    label_nxt_t = np.concatenate((label_t, label_t_nxt_k), axis=2)
    label_nxt_t = np.squeeze(label_nxt_t[:, -1, :])     # only keep 99% percentile

    # print label_nxt_t.shape
    label_nxt_t = np.greater_equal(label_nxt_t, QoS)
    # +1 viol, (+1 sat, +2 viol), (+1 sat, +2 sat, +3 viol)
    print "violations:", np.sum(label_nxt_t[:, 0]), np.sum(np.logical_not(label_nxt_t[:,0])*label_nxt_t[:, 1]), np.sum(np.logical_not(label_nxt_t[:,0]) * np.logical_not(label_nxt_t[:,1]) * label_nxt_t[:, 2])
    
    n_v_v = 0
    n_s_v = 0
    n_s_s = 0
    n_v_s = 0

    if look_forward > 1:
        for i in range(0, label_nxt_t.shape[0]):
            nxt_1 = label_nxt_t[i, 0]
            nxt_k = (np.sum(label_nxt_t[i, 1:]) >= 1)

            if nxt_1 == 1 and nxt_k == 1:
                n_v_v += 1
            elif nxt_1 == 1 and nxt_k == 0:
                n_v_s += 1
            elif nxt_1 == 0 and nxt_k == 1:
                n_s_v += 1
            else:
                n_s_s += 1

    print 'train n_v_v = ', n_v_v
    print 'train n_s_v = ', n_s_v
    print 'train n_s_s = ', n_s_s
    print 'train n_v_v = ', n_v_v
    # return

    # print label_nxt_t.shape
    if look_forward > 1:
        label_nxt_t = np.sum(label_nxt_t, axis = 1)
    # print label_nxt_t.shape
    final_label_t = np.greater_equal(label_nxt_t, 1)

    print 'X_train.shape = ', X_train.shape
    # print X_train[0, :]
    y_train = final_label_t
    print 'y_train.shape = ', y_train.shape

    # # upsampling
    # viol_idx_train = []
    # sat_idx_train  = []
    # for i in range(0, len(y_train)):
    #     if y_train[i] == 1:
    #         viol_idx_train.append(i)
    #     else:
    #         sat_idx_train.append(i)

    # print '#train_set_viol = ', len(viol_idx_train)
    # print '#train_set_sat  = ', len(sat_idx_train)

    # sample_times = int(math.ceil(len(sat_idx_train)*1.0/len(viol_idx_train)))
    # print 'sample times = ', sample_times
    # # return

    # X_train_viol = np.take(X_train, indices = viol_idx_train, axis = 0)
    # X_train_sat  = np.take(X_train, indices = sat_idx_train, axis = 0)
    # y_train_viol = np.take(y_train, indices = viol_idx_train)
    # y_train_sat  = np.take(y_train, indices = sat_idx_train)

    # X_train = X_train_sat
    # y_train = y_train_sat
    # for i in range(0, sample_times):
    #     X_train = np.concatenate((X_train, X_train_viol), axis = 0)
    #     y_train = np.concatenate((y_train, y_train_viol), axis = 0)

    # shuffle_in_unison([X_train, y_train])

    #-------------------------- validation data ----------------------------#
    sys_data_v   = np.load(data_dir + '/sys_data_valid.npy')
    nxt_data_v   = np.load(data_dir + '/nxt_data_valid.npy')
    nxt_k_data_v = np.load(data_dir + '/nxt_k_data_valid.npy')
    lat_data_v   = np.load(data_dir + '/lat_data_valid.npy')

    sys_data_v = sys_data_v.reshape(sys_data_v.shape[0],-1)
    nxt_data_v = nxt_data_v.reshape(nxt_data_v.shape[0], -1)
    nxt_k_data_v = nxt_k_data_v.reshape(nxt_k_data_v.shape[0], -1)
    lat_data_v = lat_data_v.reshape(lat_data_v.shape[0], -1)

    X_test = np.concatenate((sys_data_v, nxt_data_v, nxt_k_data_v, lat_data_v), axis=1)

    label_v = np.load(data_dir + '/valid_label.npy')
    label_v_nxt_k = np.load(data_dir + '/nxt_k_valid_label.npy')
    label_nxt_v = np.concatenate((label_v, label_v_nxt_k), axis=2)
    label_nxt_v = np.squeeze(label_nxt_v[:, -1, :])     # only keep 99% percentile

    label_nxt_v = np.greater_equal(label_nxt_v, QoS)
    if look_forward > 1:
        label_nxt_v = np.sum(label_nxt_v, axis = 1)
    final_label_v = np.greater_equal(label_nxt_v, 1)

    # label_nxt_v = np.load('./data_+1s/valid_nxt_label.npy')
    # label_nxt_v = np.squeeze(label_nxt_v[:, :, 0])[:, -1]
    # final_label_v = np.where(label_nxt_v < QoS, 0, 1)
    print 'X_test.shape = ', X_test.shape
    # print X_test[0, :]
    y_test = final_label_v
    print 'y_test.shape = ', y_test.shape

    # # upsampling
    # viol_idx_test = []
    # sat_idx_test  = []
    # for i in range(0, len(y_test)):
    #     if y_test[i] == 1:
    #         viol_idx_test.append(i)
    #     else:
    #         sat_idx_test.append(i)

    # print 'test_set_viol = ', len(viol_idx_test)
    # print 'test_set_sat  = ', len(sat_idx_test)

    # X_test_viol = np.take(X_test, indices = viol_idx_test, axis = 0)
    # X_test_sat  = np.take(X_test, indices = sat_idx_test, axis = 0)
    # y_test_viol = np.take(y_test, indices = viol_idx_test)
    # y_test_sat  = np.take(y_test, indices = sat_idx_test)

    # X_test = X_test_sat
    # y_test = y_test_sat
    # for i in range(0, sample_times):
    #     X_test = np.concatenate((X_test, X_test_viol), axis = 0)
    #     y_test = np.concatenate((y_test, y_test_viol), axis = 0)

    # shuffle_in_unison([X_test, y_test])

    #-------------------------- model ----------------------------#
    

    # print X_train.shape, X_test.shape, y_train.shape, y_test.shape
    # encode string class values as integers
    seed = 2333

    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)

    progress = dict() # Store accuracy result
    watchlist = [(dtrain,'train-err'),(dtest,'eval-err')]
    tmp = time.time()
    # Train model
    params={'objective': 'binary:logistic',
            'booster': 'gbtree', 
            'eval_metric': 'error',
            'feature_selector': 'greedy',
            'eta': 0.01,
            'max_depth': 6,
            'tree_method': 'gpu_exact', # 'gpu_exact',
            'gamma': 0.0,
            'grow_policy': 'lossguide'}

    bst = xgb.train(params, dtrain, num_boost_round=2000, evals=watchlist, evals_result=progress, early_stopping_rounds=50)
    print("GPU Training Time: %s seconds" % (str(time.time() - tmp)))
    bst.dump_model('xgb_sys_state_no_dup.raw.txt')
    ypred = bst.predict(dtest)
    binary_ypred = np.greater(ypred, 0.4 * np.ones_like(ypred))
    print np.sum(binary_ypred) * 1.0 / binary_ypred.shape[0], np.sum(y_test) * 1.0 / y_test.shape[0]
    print 'false postive = ', np.sum(np.logical_not(y_test) * binary_ypred) * 1.0 / y_test.shape[0]
    print 'false negative = ', np.sum(np.logical_not(binary_ypred) * y_test) * 1.0 / y_test.shape[0]

    if not os.path.isdir('./raw_xgb_model/'):
        os.mkdir('./raw_xgb_model/')
    bst.save_model('./raw_xgb_model/social_nn_sys_state_look_forward_' + str(look_forward) + '.model')

# print list(ypred)
'''
counter = 0
for p in ypred:
    if p > 0.25 and p < 0.75:
        counter = counter+1
print ('prob within (0.25, 0.75) = %2.3f' %(counter/size))
plt.hist(ypred, normed=True, bins=30)
plt.ylabel('Probability')
plt.yscale('log')
plt.draw()
plt.savefig("pdf.png")

xgb.plot_importance(bst)
fig = plt.gcf()
fig.set_size_inches(150,100)
fig.savefig('importance.png')

xgb.plot_tree(bst)
fig = plt.gcf()
fig.set_size_inches(150,100)
fig.savefig('tree.png')
'''

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="command for training")
    parser.add_argument('--data-dir', type=str, required=True)
    parser.add_argument('--look-forward', type=int, default=4)
    parser.add_argument('--gpus', type=str, default='0', help='the gpus will be used, e.g "0,1,2,3"')
    parser.add_argument('--kv-store', type=str, default='local', help='the kvstore type')
    parser.add_argument('--batch-size', type=int, default=2048, help='the batch size')
    # parser.add_argument('--log', default='test', type=str)
    parser.add_argument('--network', type=str, default='cnvnet')
    parser.add_argument('--model-prefix', type=str, default='./model/cnv')
    parser.add_argument('--load-epoch', type=int, default=200)
    
    args = parser.parse_args()
    # logging.basicConfig(filename=args.log+'.log')
    # logger = logging.getLogger()
    # logger.setLevel(logging.INFO)
    # logging.info(args)

    main()
