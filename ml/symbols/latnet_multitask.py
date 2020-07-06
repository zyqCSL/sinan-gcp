import mxnet as mx
import numpy as np
def get_symbol(bn_mom=0.9, workspace=512, dtype='float32'):
    
    sys_data = mx.sym.Variable('data1')
    lat_data = mx.sym.Variable('data2')
    nxt_data = mx.sym.Variable('data3')

    sys_data  = mx.sym.BatchNorm(data = sys_data, eps=2e-5, momentum=bn_mom)
    lat_data  = mx.sym.BatchNorm(data = lat_data, eps=2e-5, momentum=bn_mom)
    nxt_data  = mx.sym.BatchNorm(data = nxt_data, eps=2e-5, momentum=bn_mom)
    
    #======================================= system data convolution =======================================# 
    # 1st layer
    sys_conv1 = mx.sym.Convolution(data = sys_data, num_filter = 16, kernel=(3, 3), pad=(2, 2), no_bias=True, 
            workspace=workspace)
    sys_bn1   = mx.sym.BatchNorm(data = sys_conv1, eps=2e-5, momentum=bn_mom)
    sys_act1  = mx.sym.relu(data = sys_bn1)
    
    # 3rd layer
    sys_conv3 = mx.sym.Convolution(data = sys_act1, num_filter = 16, kernel=(3, 3), pad=(1, 1), no_bias=True, 
            stride = (2, 1), workspace=workspace)
    sys_bn3   = mx.sym.BatchNorm(data = sys_conv3, eps=2e-5, momentum=bn_mom)
    sys_act3  = mx.sym.relu(data = sys_bn3)

    # 4th layer 
    sys_conv4 = mx.sym.Convolution(data = sys_act3, num_filter = 16, kernel=(3, 3), pad=(1, 1), no_bias=True, 
            stride = (1, 1), workspace=workspace)
    sys_bn4   = mx.sym.BatchNorm(data = sys_conv4, eps=2e-5, momentum=bn_mom)
    sys_act4  = mx.sym.relu(data = sys_bn4)
   
    # 5th layer 
    sys_conv5 = mx.sym.Convolution(data = sys_act4, num_filter = 32, kernel=(3, 3), pad=(1, 1), no_bias=True, 
            stride = (2, 1), workspace=workspace)
    sys_bn5   = mx.sym.BatchNorm(data = sys_conv5, eps=2e-5, momentum=bn_mom)
    sys_act5  = mx.sym.relu(data = sys_bn5)

    # 6th layer 
    sys_conv6 = mx.sym.Convolution(data = sys_act5, num_filter = 32, kernel=(3, 3), pad=(1, 1), no_bias=True, 
            stride = (1, 1), workspace=workspace)
    sys_bn6   = mx.sym.BatchNorm(data = sys_conv6, eps=2e-5, momentum=bn_mom)
    sys_act6  = mx.sym.relu(data = sys_bn6)

    pool = mx.sym.Pooling(data = sys_act6, global_pool=True, kernel=(7,7), pool_type='avg')

    sys       = mx.sym.Flatten(data = pool)
    sys_fc    = mx.sym.FullyConnected(data = sys, num_hidden = 64)
    sys_bn    = mx.sym.BatchNorm(data = sys_fc)
    sys_act   = mx.sym.relu(data = sys_bn)
    #======================================= system data convolution =======================================# 
    
    #======================================= latency data convolution =======================================# 
    lat_data   = mx.sym.Flatten(data = lat_data)
    lat_fc1    = mx.sym.FullyConnected(data = lat_data, num_hidden = 64)
    lat_bn1    = mx.sym.BatchNorm(data = lat_fc1)
    lat_act1   = mx.sym.relu(data = lat_bn1)
    
    #======================================= latency data convolution =======================================# 
    latent_var = mx.sym.Concat(sys_act, lat_act1, dim=1)
    fc1        = mx.sym.FullyConnected(data = latent_var, num_hidden = 64, name = 'fc1')
    fc1_bn     = mx.sym.BatchNorm(data = fc1)
    fc1_act    = mx.sym.relu(data = fc1_bn)
    
    fc2        = mx.sym.FullyConnected(data = fc1_act, num_hidden = 64, name = 'fc2')
    fc2_bn     = mx.sym.BatchNorm(data = fc2)
    fc2_act    = mx.sym.relu(data = fc2_bn)
    
    nxt_data   = mx.sym.Flatten(data = nxt_data)
    nxt_fc     = mx.sym.FullyConnected(data = nxt_data, num_hidden = 64, name = 'nxt_fc', no_bias = True)
    nxt_bn     = mx.sym.BatchNorm(data = nxt_fc)
    #nxt_bn     = nxt_fc
    nxt_act    = mx.sym.relu(data = nxt_bn)

    nxt_fc_1     = mx.sym.FullyConnected(data = nxt_act, num_hidden = 64, name = 'nxt_fc_1', no_bias = True)
    nxt_bn_1     = mx.sym.BatchNorm(data = nxt_fc_1)
    #nxt_bn     = nxt_fc
    nxt_act_1    = mx.sym.relu(data = nxt_bn_1)
    
    full_feature = mx.sym.Concat(nxt_act_1, fc2_act, dim=1, name = 'full_feature')
    fc3        = mx.sym.FullyConnected(data = full_feature, num_hidden = 128, name = 'fc3')
    fc3_bn     = mx.sym.BatchNorm(data = fc3)
    fc3_act    = mx.sym.relu(data = fc3_bn, name = 'fc3_relu')
    
    label      = mx.sym.Variable(name = 'label')
    # predict four time steps
    fc4        = mx.sym.FullyConnected(data = fc3_act, num_hidden = 5 * 4, name = 'fc4')

    fc5        = mx.sym.FullyConnected(data = full_feature, num_hidden = 16, name = 'fc5')
    fc5_bn     = mx.sym.BatchNorm(data = fc5)
    fc5_act    = mx.sym.relu(data = fc5_bn, name = 'fc5_relu')
    
    fc6        = mx.sym.FullyConnected(data = fc5_act, num_hidden = 1, name = 'fc6')
    prob       = mx.sym.sigmoid(data = fc6)
    vio_label  = mx.sym.max_axis(label, axis=1, keepdims=True)
    # qos = 100
    vio_label  = mx.sym.broadcast_greater(vio_label, 100.0 * mx.sym.ones_like(vio_label))
    
    #prob, vio_label = mx.sym.Custom(prob, vio_label, op_type='DMon')

    vio_loss   = mx.sym.sum(vio_label * mx.sym.log(prob) + (mx.sym.ones_like(vio_label) - vio_label)*mx.sym.log(mx.sym.ones_like(prob) - prob))

    cnn_out    = mx.sym.Concat(prob, fc4, dim=1)
    latency_output    = mx.sym.BlockGrad(data = cnn_out, name = 'latency')
    mask        = mx.sym.broadcast_greater(label, fc4)
    loss        = mx.sym.sum(mx.sym.mean(mx.sym.square(fc4 - label), axis = 1))
    
    penalty_fc4 = mask * fc4
    penalty_lbl = mask * label
    penalty     = mx.sym.sum(mx.sym.mean(mx.sym.square(penalty_lbl - penalty_fc4), axis = 1))
    ce          = loss + 0.0*penalty - 10.0 * vio_loss
    
    cnvnet     = mx.sym.MakeLoss(ce, normalization = 'batch')
    sym        = mx.sym.Group([latency_output, cnvnet])
    return sym
