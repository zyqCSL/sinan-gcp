import mxnet as mx
import numpy as np

def get_symbol(bn_mom=0.9, workspace=512, dtype='float32'):
    
    sys_data = mx.sym.Variable('data1')
    lat_data = mx.sym.Variable('data2')
    nxt_data = mx.sym.Variable('data3')

    #sys_data  = mx.sym.BatchNorm(data = sys_data, eps=2e-5, momentum=bn_mom)
    #lat_data  = mx.sym.BatchNorm(data = lat_data, eps=2e-5, momentum=bn_mom)
    nxt_data  = mx.sym.BatchNorm(data = nxt_data, eps=2e-5, momentum=bn_mom)
    
    #======================================= system data convolution =======================================# 
    # 1st layer
    sys_fc    = mx.sym.FullyConnected(data = sys_data, flatten = False, num_hidden = 64, no_bias = True)
    sys_bn    = mx.sym.BatchNorm(data = sys_fc)
    sys_act   = mx.sym.relu(data = sys_bn)
    #======================================= system data convolution =======================================# 
    
    #======================================= latency data convolution =======================================# 
    lat_fc    = mx.sym.FullyConnected(data = lat_data, flatten = False, num_hidden = 64, no_bias = True)
    lat_bn    = mx.sym.BatchNorm(data = lat_fc)
    lat_act   = mx.sym.relu(data = lat_bn)
    #======================================= latency data convolution =======================================# 

    latent_var = mx.sym.Concat(sys_act, lat_act, dim=2)
    latent_var = mx.sym.swapaxes(latent_var, 0, 1)    

    rnn_layer = mx.gluon.rnn.LSTM(64, 2)
    rnn_layer.initialize()
    rnn_layer.hybridize()
    
    h = mx.sym.random.uniform(shape = (2, 2048, 64))
    c = mx.sym.random.uniform(shape = (2, 2048, 64))
    
    rnn, states = rnn_layer(latent_var, [h, c])
    rnn =  mx.sym.squeeze(data = mx.sym.slice_axis(data = rnn, axis = 0, begin = 4, end = 5), axis = 0)

    nxt_data   = mx.sym.Flatten(data = nxt_data)
    nxt_fc     = mx.sym.FullyConnected(data = nxt_data, num_hidden = 32, name = 'nxt_fc', no_bias = True)
    nxt_bn     = mx.sym.BatchNorm(data = nxt_fc)
    nxt_act    = mx.sym.relu(data = nxt_bn)
    
    full_feature = mx.sym.Concat(nxt_act, rnn, dim=1)

    fc3        = mx.sym.FullyConnected(data = full_feature, num_hidden = 64, name = 'fc3')
    fc3_bn     = mx.sym.BatchNorm(data = fc3)
    fc3_act    = mx.sym.relu(data = fc3_bn, name = 'fc3_relu')
    
    #fc3_act    = fc3_act + nxt_act
    # fc3_act    = mx.sym.Concat(nxt_act, fc3_act, dim=1)
    fc4        = mx.sym.FullyConnected(data = fc3_act, num_hidden = 5, name = 'fc4')
    latency_output    = mx.sym.BlockGrad(data=fc4, name='latency')
    
    label  = mx.sym.Variable('label')
    mask       = mx.sym.broadcast_greater(label, fc4)
    
    penalty_lbl = label * mask
    penalty_fc4 = fc4 * mask

    loss = mx.sym.sum(mx.sym.mean(mx.sym.square(fc4 - label),1))
    penalty = mx.sym.sum(mx.sym.mean(mx.sym.square(penalty_lbl - penalty_fc4),1))
    ce = loss + 1.0 * penalty
    cnvnet = mx.sym.MakeLoss(ce, normalization='batch')
    sym = mx.sym.Group([latency_output, cnvnet])
    return sym
