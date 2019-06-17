from bayopt import definitions
from bayopt.clock.clock import from_str
from bayopt.utils.utils import rmdir_when_any
import os
import csv
import numpy as np


def load_experiments(function_name, dim, feature, start=None, end=None, iter_check=None):
    experiments = load_files(
        function_name=function_name, start=start, end=end, dim=dim, feature=feature)

    results = list()
    for expt in experiments:
        evaluation_file = expt + '/evaluation.csv'
        y = csv_to_numpy(file=evaluation_file)
        y = y[:, 1]

        if iter_check:
            if len(y) < iter_check:
                print('Error in ' + expt + ': expect ' + str(iter_check) + ' given ' + str(len(y)))
                # rmdir_when_any(expt)
                raise ValueError('iterations is not enough')

        results.append(y)
        print(expt)

    results = make_uniform_by_length(results)

    return np.array(results, dtype=np.float)


def load_experiments_theta(function_name, dim, feature, created_at, update_check=None):
    experiments = load_files(
        function_name=function_name, start=created_at, end=created_at, dim=dim, feature=feature)

    if len(experiments) == 0:
        raise FileNotFoundError('zero experiments')

    if len(experiments) > 1:
        raise ValueError('2 more file exist.')

    expt = experiments[0]

    distribution_file = expt + '/distribution.csv'
    theta = csv_to_numpy(distribution_file, header=False)

    if update_check:
        if len(theta) < update_check:
            print('expect ' + str(update_check) + ' given ' + str(len(theta)))

            raise ValueError('the number of updating is not enough')

    print(expt)

    return np.array(theta, dtype=np.float)


def csv_to_numpy(file, header=True):
    y = list()

    with open(file, 'r') as f:
        reader = csv.reader(f, delimiter="\t")
        if header:
            next(reader)  # ヘッダーを読み飛ばしたい時

        for row in reader:
            y.append(row)
    return np.array(y, dtype=np.float)


def load_files(function_name, start=None, end=None, **kwargs):
    """
    :param function_name: string
    :param start: string
    :param end:  string
    :return: list
    """
    storage_dir = definitions.ROOT_DIR + '/storage/' + function_name
    experiments = os.listdir(storage_dir)

    masked = list()

    if start:
        start = from_str(start)
    if end:
        end = from_str(end)
    for expt in experiments:
        try:
            dt, tm, dim, feature = expt.split(' ')
        except ValueError as e:
            print('discard: ' + expt)
            continue

        expt_time = from_str(dt + ' ' + tm)

        is_append = True

        if start:
            if expt_time < start:
                is_append = False

        if end:
            if end < expt_time:
                is_append = False

        for kwd in kwargs:
            if not (kwargs[kwd] == dim or kwargs[kwd] == feature):
                is_append = False

        if is_append:
            masked.append(storage_dir + '/' + expt)

    return masked


def make_uniform_by_length(list_obj):
    if len(list_obj) is 0:
        return list()

    list_ = list()

    lengths = [len(el) for el in list_obj]

    min_len = min(lengths)

    for el in list_obj:
        list_.append(el[0:min_len])

    return list_
