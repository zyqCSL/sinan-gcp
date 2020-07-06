import mxnet as mx
import numpy as np

def get_symbol(bn_mom=0.9, workspace=512, dtype='float32'):
    
    sys_data = mx.sym.Variable('data1')
    lat_data = mx.sym.Variable('data2')
    nxt_data = mx.sym.Variable('data3')

    sys_data = mx.sym.Flatten(data = sys_data)
    lat_data = mx.sym.Flatten(data = lat_data)
    nxt_data = mx.sym.Flatten(data = nxt_data)

    feature = mx.sym.Concat(sys_data, lat_data, nxt_data, dim = 1)
    fc2        = mx.sym.FullyConnected(data = feature, num_hidden = 1024, name = 'fc2')
    fc2_bn     = mx.sym.BatchNorm(data = fc2)
    fc2_act    = mx.sym.relu(data = fc2_bn)
    
    fc3        = mx.sym.FullyConnected(data = fc2_act, num_hidden = 512, name = 'fc3')
    fc3_bn     = mx.sym.BatchNorm(data = fc3)
    fc3_act    = mx.sym.relu(data = fc3_bn)
    
    fc4        = mx.sym.FullyConnected(data = fc3_act, num_hidden = 256, name = 'fc4')
    fc4_bn     = mx.sym.BatchNorm(data = fc4)
    fc4_act    = mx.sym.relu(data = fc4_bn)
   
    fc5        = mx.sym.FullyConnected(data = fc4_act, num_hidden = 64, name = 'fc5')
    fc5_bn     = mx.sym.BatchNorm(data = fc5)
    fc5_act    = mx.sym.relu(data = fc5_bn)
    
    fout        = mx.sym.FullyConnected(data = fc5_act, num_hidden = 5, name = 'fout')
    latency_output    = mx.sym.BlockGrad(data=fout, name='latency')
    
    label  = mx.sym.Variable('label')
    mask   = mx.sym.broadcast_greater(label, fout)
    
    penalty_lbl = label * mask
    penalty_fout = fout * mask

    loss = mx.sym.sum(mx.sym.mean(mx.sym.square(fout - label),1))
    penalty = mx.sym.sum(mx.sym.mean(mx.sym.square(penalty_lbl - penalty_fout),1))
    ce = loss + 1.0 * penalty
    cnvnet = mx.sym.MakeLoss(ce, normalization='batch')
    sym = mx.sym.Group([latency_output, cnvnet])
    return sym

    # ori_label  = mx.sym.Variable('data4')
    # fc4, ori_label = mx.sym.Custom(fc4, ori_label, op_type='DMon')
    #d          = 100.0 * mx.sym.ones_like(fc4)
    #k          = 0.005 
    #           = 0.01
    #fc4        = mx.sym.where(fc4 < d, fc4, d+(fc4-d)/(mx.sym.ones_like(fc4)+k*(fc4-d))) 
'''
    label      = mx.sym.Variable(name = 'label')
    mask       = mx.sym.broadcast_greater(label, fc4)
    penalty_lbl = label * mask
    penalty_fc4 = fc4 * mask
    loss        = mx.sym.LinearRegressionOutput(data = fc4, label = label)
    penalty	   = mx.sym.MAERegressionOutput(data = penalty_fc4, label = penalty_lbl)
    sym = loss + 1.0 * penalty
    return sym
'''
