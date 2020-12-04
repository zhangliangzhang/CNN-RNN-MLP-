#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# mail:levy_lv@hotmail.com
# Lyu Wei @ 2017-07-24
'''
This is a CNN decoder.
'''

import tensorflow as tf
import numpy as np
import scipy.io as sio
import math
import time
from datetime import datetime
import os 
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

slim = tf.contrib.slim

def cnn_arg_scope(weight_decay = 0.0005):
    '''Define the CNN arg scope

    Args: 
        weight_decay : The l2 regularization coefficient

    Returns:
        An arg_scope
    '''
    with slim.arg_scope([slim.conv2d, slim.fully_connected],
                        activation_fn = tf.nn.relu,
                        weights_regularizer = slim.l2_regularizer(weight_decay),
                        biases_initializer = tf.zeros_initializer()):
        with slim.arg_scope([slim.conv2d, slim.max_pool2d], stride = [1, 1], padding = 'SAME') as arg_sc:
            return arg_sc

def cnn(inputs,
        dropout_keep_prob,
        length_input,
        spatial_squeeze = True,
        scope = 'cnn',
        ):
    '''4-layers cnn

    Note: All the fully_connected layers haven been transformed to conv2d. The input size is [1, N, 1], the output size is N/2
    '''
    
    with tf.variable_scope(scope, 'cnn') as sc:
        end_points_collection = sc.name + '_end_points'
        # Collect outputs for conv2d, fully_connected and max_pool2d
        with slim.arg_scope([slim.conv2d, slim.max_pool2d, slim.fully_connected], outputs_collections = end_points_collection):
            net = slim.conv2d(inputs, 8, [1, 3], scope = 'conv1')
            net = slim.avg_pool2d(net, [1, 2], stride = [1, 2], scope = 'pool1')
            net = slim.conv2d(net, 16, [1, 3], scope = 'conv2')
            net = slim.avg_pool2d(net, [1, 2], stride = [1, 2], scope = 'pool2')
            net = slim.conv2d(net, 32, [1, 3], scope = 'conv3')
            net = slim.avg_pool2d(net, [1, 2], stride = [1, 2], scope = 'pool3')
            net = slim.conv2d(net, int(length_input / 2), [1, int(length_input / 8)], padding = 'VALID',
                            activation_fn = None,
                            normalizer_fn = None,
                            scope = 'fc4')
            # Convert end_points_collection into a end_point dict
            end_points = slim.utils.convert_collection_to_dict(end_points_collection)
            if spatial_squeeze:
                net = tf.squeeze(net, [1, 2], name = 'fc4/squeezed')
                end_points[sc.name + '/fc5'] = net

            return net, end_points

def get_random_batch_data(x, y, batch_size):
    '''get random batch data from x and y, which have the same length
    '''
    index = np.random.randint(0, len(x) - batch_size)
    return x[index:(index+batch_size)], y[index:(index+batch_size)]

# Parameters setting
N = 16
K = 8
data_path = '../../../../RNN/no-noise/K_8_N_16/train_data_10^6/data/'
num_epoch = 10**5
batch_size = 128
#train_snr = np.arange(-4, 6)
#test_snr = np.arange(7)
train_ratio = np.array([0.4, 0.6, 0.8, 1.0])
epoch_setting = np.array([10, 10**2, 10**3, 10**4, 10**5])
#res_ber = np.zeros([len(train_ratio), len(train_snr), len(test_snr), len(epoch_setting)])
res_ber = np.zeros([len(train_ratio), len(epoch_setting)])


# make the cnn model
keep_prob = tf.placeholder(tf.float32)
coded_words = tf.placeholder(tf.float32, [None, N])
labels = tf.placeholder(tf.float32, [None, K])
x = tf.reshape(coded_words, [-1, 1, N, 1])

with slim.arg_scope(cnn_arg_scope()):
    net, end_points = cnn(x, keep_prob, N)

print('CNN: input= %d, output = %d, batch size = %d' % (N, K, batch_size))
# Multi-label classification
logits = tf.nn.sigmoid(net)   
loss = slim.losses.mean_squared_error(logits, labels)

# Add MSE loss and regularization loss
total_loss = slim.losses.get_total_loss()
optimizer = tf.train.AdamOptimizer(1e-3).minimize(total_loss)

prediction = tf.cast(logits > 0.5, tf.float32)
correct_prediction = tf.equal(prediction, labels)
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
ber = 1.0 - accuracy

sess = tf.Session()
init = tf.global_variables_initializer()


# Get the different data of train and test
backward_batch_time_total = 0.0
forward_time_total = 0.0
for ratio_index in range(len(train_ratio)):
#    for tr_snr_index in range(len(train_snr)):
    train_filename = 'ratio_' + str(train_ratio[ratio_index]) + '.mat'
    train_data = sio.loadmat(data_path+train_filename)
    x_train = train_data['x_train']
    y_train = train_data['y_train']

    # start session
    sess.run(init)
    print('---------------------------------')
    print('New begining')
    print('---------------------------------')
    for epoch in range(num_epoch):
        x_batch, y_batch = get_random_batch_data(x_train, y_train, batch_size)

        # Set keep_prob = 0.9 for training
        backward_batch_time_start = time.time()
        _, train_ber = sess.run([optimizer, ber], feed_dict = {coded_words : x_batch, labels : y_batch, keep_prob : 0.9})
        duration = time.time() - backward_batch_time_start
        backward_batch_time_total += duration

        if (epoch+1) % 1000 == 0:
            print('%s: epoch = %d, train_ratio = %f ---> train_ber = %.4f, forward time = %.3f sec' % (datetime.now(), epoch+1, train_ratio[ratio_index], train_ber, duration))

        if epoch+1 in epoch_setting:
            epoch_index = int(np.log10(epoch+1) - 1)

            print('\n')
            print('***********TEST BEGIN************')
           # for te_snr_index in range(len(test_snr)):
            test_filename = 'test.mat'
            test_data = sio.loadmat(data_path+test_filename)
            x_test = test_data['x_test']
            y_test = test_data['y_test']
            
            # Set keep_prob = 1.0 for testing
            forward_time_start = time.time()
            res = sess.run(ber, feed_dict = {coded_words : x_test, labels: y_test, keep_prob : 1.0})
            duration = time.time() - forward_time_start
            forward_time_total += duration
            print('%s: epoch = %d, train_ratio = %f ---> ber = %.4f, forward time = %.3f sec' % (datetime.now(), epoch+1, train_ratio[ratio_index], res, duration))
            res_ber[ratio_index, epoch_index] = res
            print('***********TEST END**********')
            print('\n')
# Statistics
backward_batch_time_avg = backward_batch_time_total / (num_epoch * len(train_ratio))
forward_count = int(len(epoch_setting) * len(train_ratio))
forward_time_avg = forward_time_total / forward_count

print('\n')
print('*****************END***************')
print('For the backward time of CNN:')
print('batch size = %d, total batch = %d, time = %.3f sec/batch' % (batch_size, num_epoch, backward_batch_time_avg))
print('For the forward time of CNN:')
print('test number = %d, total test = %d, time = %.3f sec' % (len(x_test), forward_count, forward_time_avg))
sio.savemat('result/cnn_result', {'ber_trainRatio_epoch' : res_ber, 'backward_batch_time_avg' : backward_batch_time_avg, 'forward_time_avg' : forward_time_avg})

