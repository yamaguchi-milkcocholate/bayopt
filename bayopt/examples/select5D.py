from bayopt.methods.select import SelectObjective
from bayopt.objective_examples.experiments import GaussianMixtureFunction

domain = [{'name': 'x0', 'type': 'continuous', 'domain': (1, 4), 'dimensionality': 1},
          {'name': 'x1', 'type': 'continuous', 'domain': (1, 4), 'dimensionality': 1},
          {'name': 'x2', 'type': 'continuous', 'domain': (1, 4), 'dimensionality': 1},
          {'name': 'x3', 'type': 'continuous', 'domain': (1, 4), 'dimensionality': 1},
          {'name': 'x4', 'type': 'continuous', 'domain': (1, 4), 'dimensionality': 1},
          ]

dim = len(domain)
f = GaussianMixtureFunction(dim=dim, mean_1=2, mean_2=3)

method = SelectObjective(fill_in_strategy='random', f=f, domain=domain, maximize=True)
method.run_optimization(max_iter=100)
