from bayopt.plot.loader import load_experiments
from bayopt.plot.staticplot import StaticPlot
from bayopt.plot.stats import maximum_locus
from bayopt.plot.stats import with_confidential
import numpy as np


def plot_experiments(function_name, dim, method, is_median=False, single=False):

    data = dict()

    for fill in method:
        results = load_experiments(
            function_name=function_name,
            start=None,
            end=None,
            dim=dim,
            feature=fill,
        )
        results = results * -1

        results_ = list()

        for i in range(len(results)):
            results_.append(maximum_locus(results[i]))

        results_ = np.array(results_)
        results_ = results_.T

        results_ = with_confidential(results_)

        x_axis = np.arange(0, len(results_))

        if is_median:
            median = results_['median']
            upper = results_['upper']
            lower = results_['lower']

            data[fill] = {'x_axis': x_axis, 'prediction': median, 'upper': upper, 'lower': lower}
        else:
            mean = results_['mean'].values
            std = results_['std'].values

            data[fill] = {'x_axis': x_axis, 'prediction': mean, 'upper': mean + std, 'lower': mean - std}

        if single:
            plot = StaticPlot()
            plot.add_data_set(x=x_axis, y=data[fill]['prediction'])
            plot.add_confidential_area(
                x=x_axis, upper_confidential_bound=data[fill]['upper'], lower_confidential_bound=data[fill]['lower'])
            plot.set_y(low_lim=-0.2, high_lim=1.2)
            plot.finish(option=function_name + '_' + fill)

    plot_all = StaticPlot()

    for key, data_ in data.items():
        plot_all.add_data_set(x=data_['x_axis'], y=data_['prediction'], label=key)
        plot_all.add_confidential_area(x=data_['x_axis'],
                                       upper_confidential_bound=data_['upper'], lower_confidential_bound=data_['lower'])

    plot_all.set_y(low_lim=-0.2, high_lim=1.2)
    if is_median:
        plot_all.finish(option=function_name + '_' + dim + '_median')
    else:
        plot_all.finish(option=function_name + '_' + dim + '_mean')