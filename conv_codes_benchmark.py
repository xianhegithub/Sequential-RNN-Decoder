__author__ = 'yihanjiang'
'''
Evaluate convolutional code benchmark.
'''
from utils import corrupt_signal, get_test_sigmas

import sys
import numpy as np
import time

import commpy.channelcoding.convcode as cc
from commpy.utilities import hamming_dist
import multiprocessing as mp

def get_args():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('-num_block', type=int, default=100)
    parser.add_argument('-block_len', type=int, default=100)

    parser.add_argument('-code_rate',  type=int, default=2)

    parser.add_argument('-enc1',  type=int, default=7)
    parser.add_argument('-enc2',  type=int, default=5)
    parser.add_argument('-enc3',  type=int, default=1)

    parser.add_argument('-feedback',  type=int, default=7)

    parser.add_argument('-num_cpu', type=int, default=4)

    parser.add_argument('-snr_test_start', type=float, default=-1.0)
    parser.add_argument('-snr_test_end', type=float, default=8.0)
    parser.add_argument('-snr_points', type=int, default=10)

    parser.add_argument('-noise_type',        choices = ['awgn', 't-dist','hyeji_bursty'], default='awgn')
    parser.add_argument('-radar_power',       type=float, default=20.0)
    parser.add_argument('-radar_prob',        type=float, default=0.05)
    parser.add_argument('-radar_denoise_thd', type=float, default=10.0)
    parser.add_argument('-v',                 type=int,   default=3)


    parser.add_argument('-id', type=str, default=str(np.random.random())[2:8])

    args = parser.parse_args()

    print(args)
    print('[ID]', args.id)
    return args

def turbo_compute(turbo_input):
    '''
    Compute Turbo Decoding in 1 iterations for one SNR point.
    '''
    idx = turbo_input[0]
    x = turbo_input[1]
    np.random.seed()
    message_bits = np.random.randint(0, 2, args.block_len)

    coded_bits = cc.conv_encode(message_bits, trellis1)
    received  = corrupt_signal(coded_bits, noise_type =args.noise_type, sigma = test_sigmas[idx],
                                vv =args.v, radar_power = args.radar_power, radar_prob = args.radar_prob,
                                denoise_thd = args.radar_denoise_thd)

    # make fair comparison between (100, 204) convolutional code and (100,200) RNN decoder, set the additional bit to 0
    received[-2*int(M):] = 0.0

    decoded_bits = cc.viterbi_decode(received.astype(float), trellis1, tb_depth, decoding_type='unquantized')
    decoded_bits = decoded_bits[:-int(M)]
    num_bit_errors = hamming_dist(message_bits, decoded_bits)
    return num_bit_errors


if __name__ == '__main__':
    args = get_args()

    ##########################################
    # Setting Up Codec
    ##########################################
    M = np.array([2]) # Number of delay elements in the convolutional encoder
    if args.code_rate == 2:
        generator_matrix = np.array([[args.enc1, args.enc2]])
    elif args.code_rate == 3:
        generator_matrix = np.array([[args.enc1, args.enc2, args.enc3]])
    else:
        print('Not supported!')
        sys.exit()
    feedback = args.feedback

    print('[testing] Convolutional Code Encoder: G: ', generator_matrix,'Feedback: ', feedback,  'M: ', M)

    trellis1 = cc.Trellis(M, generator_matrix,feedback=feedback)  # Create trellis data structure
    trellis_length = 3
    state_order = [0,2,1,3]  # 00,10,01,11
    bit_colors = ['red', 'green'] 

    trellis1.visualize(trellis_length, state_order, 
                  edge_colors = bit_colors)

    SNRS, test_sigmas = get_test_sigmas(args.snr_test_start, args.snr_test_end, args.snr_points)

    tic = time.time()
    tb_depth = 15  # trace back depth

    commpy_res_ber = []
    commpy_res_bler= []

    nb_errors          = np.zeros(test_sigmas.shape)
    map_nb_errors      = np.zeros(test_sigmas.shape)
    nb_block_no_errors = np.zeros(test_sigmas.shape)

    for idx in range(len(test_sigmas)):
        start_time = time.time()

        pool = mp.Pool(processes=args.num_cpu)
        results = pool.map(turbo_compute, [[idx,x] for x in range(args.num_block)])

        for result in results:
            if result == 0:
                nb_block_no_errors[idx] = nb_block_no_errors[idx]+1

        nb_errors[idx]+= sum(results)
        print('[testing]SNR: ' , SNRS[idx])
        print('[testing]BER: ', sum(results)/float(args.block_len*args.num_block))
        print('[testing]BLER: ', 1.0 - nb_block_no_errors[idx]/args.num_block)
        commpy_res_ber.append(sum(results)/float(args.block_len*args.num_block))
        commpy_res_bler.append(1.0 - nb_block_no_errors[idx]/args.num_block)
        end_time = time.time()
        print('[testing] This SNR runnig time is', str(end_time-start_time))


    print('[Result]SNR: ', SNRS)
    print('[Result]BER', commpy_res_ber)
    print('[Result]BLER', commpy_res_bler)

    toc = time.time()

    print('[Result]Total Running time:', toc-tic)
