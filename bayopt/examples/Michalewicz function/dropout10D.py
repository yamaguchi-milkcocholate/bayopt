from bayopt.methods.dropout import Dropout
from bayopt.objective_examples.experiments import MichalewiczFunction
import numpy as np

domain = [{'name': 'x0', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x1', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x2', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x3', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x4', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x5', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x6', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x7', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x8', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          {'name': 'x9', 'type': 'continuous', 'domain': (0, np.pi), 'dimensionality': 1},
          ]

for i in range(3):

    dim = len(domain)
    fill_in_strategy = 'random'
    f = MichalewiczFunction(dimensionality=dim, dropout=[i for i in range(dim) if i % 2 == 1])
    method = Dropout(
        f=f, domain=domain, subspace_dim_size=15, fill_in_strategy=fill_in_strategy, maximize=False)
    # method.run_optimization(max_iter=500, eps=0)

    dim = len(domain)
    fill_in_strategy = 'copy'
    f = MichalewiczFunction(dimensionality=dim)
    method = Dropout(
        f=f, domain=domain, subspace_dim_size=5, fill_in_strategy=fill_in_strategy, maximize=False,
                     )
    method.run_optimization(max_iter=500, eps=0)

    dim = len(domain)
    fill_in_strategy = 'mix'
    f = MichalewiczFunction(dimensionality=dim)
    method = Dropout(
        f=f, domain=domain, subspace_dim_size=5, fill_in_strategy=fill_in_strategy, maximize=False, mix=0.5)
    method.run_optimization(max_iter=500, eps=0)


for i in range(5):
    dim = len(domain)
    fill_in_strategy = 'copy'
    f = MichalewiczFunction(dimensionality=dim)
    method = Dropout(
        f=f, domain=domain, subspace_dim_size=2, fill_in_strategy=fill_in_strategy, maximize=False,
    )
    method.run_optimization(max_iter=500, eps=0)

    dim = len(domain)
    fill_in_strategy = 'mix'
    f = MichalewiczFunction(dimensionality=dim)
    method = Dropout(
        f=f, domain=domain, subspace_dim_size=2, fill_in_strategy=fill_in_strategy, maximize=False, mix=0.5)
    method.run_optimization(max_iter=500, eps=0)
