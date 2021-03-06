from GPyOpt.core.bo import BO
from GPyOpt.core.task.cost import CostModel
from GPyOpt.core.task.objective import SingleObjective
from GPyOpt.models.gpmodel import GPModel
from GPyOpt.optimization.acquisition_optimizer import AcquisitionOptimizer
from GPyOpt.optimization.acquisition_optimizer import ContextManager
from GPyOpt.experiment_design import initial_design
from GPyOpt.util.general import normalize
from GPyOpt.util.duplicate_manager import DuplicateManager
from GPyOpt.util.arguments_manager import ArgumentsManager
from bayopt.space.space import initialize_space
from bayopt.clock.stopwatch import StopWatch
from bayopt.clock.clock import now_str
from bayopt import definitions
from bayopt.utils.utils import mkdir_when_not_exist
from copy import deepcopy
import numpy as np


class REMBO(BO):
    """

    Args:
        f (function): function to optimize.
        domain (list | None): the description of the inputs variables
            (See GpyOpt.core.space.Design_space class for details)
        constraints (list | None): the description of the problem constraints
            (See GpyOpt.core.space.Design_space class for details)


    Attributes:
        initial_design_numdata (int):
        initial_design_type (string):

        domain (dict | None):
        constraints (dict | None):
        space (Design_space):
        model (BOModel):
        acquisition (AcquisitionBase):
        cost (CostModel):
    """

    def __init__(self, f, domain=None, constraints=None, cost_withGradients=None, X=None,
                 Y=None, subspace_dim_size=0,
                 model_type='GP', initial_design_numdata=1, initial_design_type='random', acquisition_type='LCB',
                 normalize_Y=True, exact_feval=False, acquisition_optimizer_type='lbfgs', model_update_interval=1,
                 evaluator_type='sequential', batch_size=1, maximize=False, de_duplication=False):

        if model_type == 'input_warped_GP':
            raise NotImplementedError('input_warped_GP model is not implemented')

        if acquisition_type in ['EI_MCMC', 'MPI_MCMC', 'LCB_MCMC']:
            raise NotImplementedError('MCMC is not implemented')

        if batch_size is not 1 or evaluator_type is not 'sequential':
            raise NotImplementedError('only sequential evaluation is implemented')

        if cost_withGradients is not None:
            raise NotImplementedError('param cost is not implemented')

        if constraints is not None:
            raise NotImplementedError('param constraints is not implemented')

        # private field
        self._arguments_mng = ArgumentsManager(kwargs=dict())

        self.subspace_dim_size = subspace_dim_size
        self.cost_withGradients = cost_withGradients
        self.initial_design_numdata = initial_design_numdata
        self.initial_design_type = initial_design_type
        self.model_type = model_type
        self.acquisition_type = acquisition_type
        self.evaluator_type = evaluator_type
        self.model_update_interval = model_update_interval
        self.maximize = maximize
        self.normalize_Y = normalize_Y
        self.de_duplication = de_duplication
        self.subspace_dim_size = subspace_dim_size
        self.original_domain = domain

        # --- property injected in other methods.
        self.verbosity = False
        self.subspace = None
        self.max_time = None
        self.max_iter = None
        self.cum_time = None
        self.report_file = None
        self.evaluations_file = None
        self.models_file = None
        self.eps = None
        self.save_models_parameters = None
        # --- unnecessary property
        self.suggested_sample = None
        self.Y_new = None

        # --- BO class property in uncertain use
        self.num_cores = 1

        self.objective = SingleObjective(self._sign(f), batch_size, f.get_function_name())
        self.cost = CostModel(cost_withGradients=cost_withGradients)

        self.space = initialize_space(domain=domain, constraints=constraints)
        self.embedding_matrix = np.random.normal(size=(self.dimensionality, subspace_dim_size))

        subspace_domain = self.choose_subspace_domain(subspace_dim_size=subspace_dim_size)

        self.subspace = initialize_space(domain=subspace_domain, constraints=constraints)

        self.model = self._arguments_mng.model_creator(
            model_type=self.model_type, exact_feval=exact_feval, space=self.subspace)

        self.acquisition = self._arguments_mng.acquisition_creator(
            acquisition_type=self.acquisition_type, model=self.model, space=self.subspace,
            acquisition_optimizer=AcquisitionOptimizer(space=self.space, optimizer=acquisition_optimizer_type),
            cost_withGradients=self.cost_withGradients
        )

        self.evaluator = self._arguments_mng.evaluator_creator(
            evaluator_type=self.evaluator_type, acquisition=self.acquisition,
            batch_size=self.batch_size, model_type=self.model_type, model=self.model,
            space=self.space, acquisition_optimizer=self.acquisition_optimizer
        )

        self.X = X
        self.Y = Y
        self._set_initial_values()

        super().__init__(
            model=self.model,
            space=self.subspace,
            objective=self.objective,
            acquisition=self.acquisition,
            evaluator=self.evaluator,
            X_init=self.X,
            Y_init=self.Y,
            cost=self.cost,
            normalize_Y=self.normalize_Y,
            model_update_interval=self.model_update_interval,
            de_duplication=self.de_duplication
        )

    @property
    def dimensionality(self):
        return self.space.objective_dimensionality

    @property
    def subspace_domain(self):
        return self.subspace.config_space

    @property
    def domain(self):
        return self.space.config_space

    @property
    def constraints(self):
        return self.space.constraints

    @property
    def f(self):
        return self.objective.func

    @property
    def cost_type(self):
        return self.cost.cost_withGradients

    @property
    def exact_feval(self):
        return self.model.exact_feval

    @property
    def acquisition_optimizer_type(self):
        return self.acquisition_optimizer.optimizer_name

    @property
    def acquisition_optimizer(self):
        return self.acquisition.optimizer

    @property
    def batch_size(self):
        return self.objective.n_procs

    @property
    def objective_name(self):
        return self.objective.objective_name

    def choose_subspace_domain(self, subspace_dim_size):
        subspace_domain = list()

        for i in range(subspace_dim_size):
            subspace_domain.append({
                'name': 'x' + str(i),
                'type': 'continuous',
                'domain': (-np.sqrt(self.dimensionality), np.sqrt(self.dimensionality)),
                'dimensionality': 1
            })
        return subspace_domain

    def map_to_original_space(self, x):
        if x.shape != (1, self.subspace_dim_size):
            raise ValueError('x.shape is not correct ' + str(x.shape))

        x = np.array([np.dot(self.embedding_matrix, el) for el in x])
        return x

    def run_optimization(self, max_iter=0, max_time=np.inf, eps=1e-8, context=None,
                         verbosity=False, save_models_parameters=True, report_file=None,
                         evaluations_file=None, models_file=None):

        if self.objective is None:
            raise ValueError("Cannot run the optimization loop without the objective function")

        # --- Save the options to print and save the results
        self.verbosity = verbosity
        self.save_models_parameters = save_models_parameters
        self.report_file = report_file
        self.evaluations_file = evaluations_file
        self.models_file = models_file
        self.model_parameters_iterations = None
        self.context = context

        # --- Check if we can save the model parameters in each iteration
        if self.save_models_parameters:
            if not (isinstance(self.model, GPModel)):
                print('Models printout after each iteration is only available for GP and GP_MCMC models')
                self.save_models_parameters = False

                # --- Setting up stop conditions
            self.eps = eps
            if (max_iter is None) and (max_time is None):
                self.max_iter = 0
                self.max_time = np.inf
            elif (max_iter is None) and (max_time is not None):
                self.max_iter = np.inf
                self.max_time = max_time
            elif (max_iter is not None) and (max_time is None):
                self.max_iter = max_iter
                self.max_time = np.inf
            else:
                self.max_iter = max_iter
                self.max_time = max_time

        # --- Initialize iterations and running time
        stopwatch = StopWatch()
        self.num_acquisitions = self.initial_design_numdata
        self.suggested_sample = self.X
        self.Y_new = self.Y
        self._compute_results()

        self._run_optimization()

        self.cum_time = stopwatch.passed_time()

        # --- Stop messages and execution time
        self._compute_results()

        # --- Print the desired result in files
        if self.report_file is not None:
            self.save_report(self.report_file)
        if self.evaluations_file is not None:
            self.save_evaluations(self.evaluations_file)
        if self.models_file is not None:
            self.save_models(self.models_file)

        self._save()

    def _run_optimization(self):
        while True:
            print('.')

            # --- update model
            try:
                self.update()

            except np.linalg.LinAlgError:
                print('np.linalg.LinAlgError')
                break

            if self.num_acquisitions >= self.max_iter:
                break

            self.next_point()

            # --- Update current evaluation time and function evaluations
            self.num_acquisitions += 1

    def next_point(self):
        self.suggested_sample = self._compute_next_evaluations()

        # --- Augment X
        self.X = np.vstack((self.X, self.suggested_sample))

        # --- Evaluate *f* in X, augment Y and update cost function (if needed)
        self.evaluate_objective()

    def evaluate_objective(self):
        """
        Evaluates the objective
        """
        original_suggested_sample = self.map_to_original_space(x=self.suggested_sample)
        self.Y_new, cost_new = self.objective.evaluate(original_suggested_sample)
        self.cost.update_cost_model(self.suggested_sample, cost_new)
        self.Y = np.vstack((self.Y, self.Y_new))

    def get_best_point(self):
        self._compute_results()
        return self.x_opt, self.fx_opt

    def update(self):
        self._update_model(self.normalization_type)
        self._update_acquisition()
        self._update_evaluator()

    def _sign(self, f):
        if self.maximize:
            f_copy = f

            def f(x): return -f_copy(x)
        return f

    def _set_initial_values(self):
        if self.X is None:
            self.X = initial_design(self.initial_design_type, self.subspace, self.initial_design_numdata)
            self.Y, _ = self.objective.evaluate(self.map_to_original_space(x=self.X))
        elif self.X is not None and self.Y is None:
            self.Y, _ = self.objective.evaluate(self.map_to_original_space(x=self.X))

        # save initial values
        self.initial_X = deepcopy(self.X)
        if self.maximize:
            self.initial_Y = -deepcopy(self.Y)
        else:
            self.initial_Y = deepcopy(self.Y)

    def _update_acquisition(self):
        self.acquisition = self._arguments_mng.acquisition_creator(
            acquisition_type=self.acquisition_type, model=self.model, space=self.subspace,
            acquisition_optimizer=AcquisitionOptimizer(space=self.subspace, optimizer=self.acquisition_optimizer_type),
            cost_withGradients=self.cost_withGradients
        )

    def _update_evaluator(self):
        self.evaluator.acquisition = self.acquisition

    def _update_model(self, normalization_type='stats'):
        if self.num_acquisitions % self.model_update_interval == 0:

            self.model = self._arguments_mng.model_creator(
                model_type=self.model_type, exact_feval=self.exact_feval, space=self.subspace)

            X_inmodel, Y_inmodel = self._input_data(normalization_type=normalization_type)

            self.model.updateModel(X_inmodel, Y_inmodel, None, None)
            self.X_inmodel = X_inmodel
            self.Y_inmodel = Y_inmodel

        # Save parameters of the model
        self._save_model_parameter_values()

    def _input_data(self, normalization_type):
        # input that goes into the model (is unziped in case there are categorical variables)
        X_inmodel = self.subspace.unzip_inputs(self.X)

        # Y_inmodel is the output that goes into the model
        if self.normalize_Y:
            Y_inmodel = normalize(self.Y, normalization_type)
        else:
            Y_inmodel = self.Y

        return X_inmodel, Y_inmodel

    def _compute_next_evaluations(self, pending_zipped_X=None, ignored_zipped_X=None):
        # --- Update the context if any
        self.acquisition.optimizer.context_manager = ContextManager(self.subspace, self.context)

        # --- Activate de_duplication
        if self.de_duplication:
            duplicate_manager = DuplicateManager(
                space=self.subspace, zipped_X=self.X, pending_zipped_X=pending_zipped_X,
                ignored_zipped_X=ignored_zipped_X)
        else:
            duplicate_manager = None

        # We zip the value in case there are categorical variables
        suggested_ = self.subspace.zip_inputs(self.evaluator.compute_batch(
            duplicate_manager=duplicate_manager,
            context_manager=self.acquisition.optimizer.context_manager))

        return suggested_

    def _save(self):
        mkdir_when_not_exist(abs_path=definitions.ROOT_DIR + '/storage/' + self.objective_name)

        dir_name = definitions.ROOT_DIR + '/storage/' + self.objective_name + '/' + now_str() + ' ' + str(
            len(self.original_domain)) + 'D REMBO_' + str(self.subspace_dim_size)
        mkdir_when_not_exist(abs_path=dir_name)

        self.save_report(report_file=dir_name + '/report.txt')
        self.save_evaluations(evaluations_file=dir_name + '/evaluation.csv')
        self.save_models(models_file=dir_name + '/model.csv')

    def save_report(self, report_file=None):
        with open(report_file, 'w') as file:
            import GPyOpt
            import time

            file.write(
                '-----------------------------' + ' GPyOpt Report file ' + '-----------------------------------\n')
            file.write('GPyOpt Version ' + str(GPyOpt.__version__) + '\n')
            file.write('Date and time:               ' + time.strftime("%c") + '\n')
            if self.num_acquisitions == self.max_iter:
                file.write('Optimization completed:      ' + 'YES, ' + str(self.X.shape[0]).strip(
                    '[]') + ' samples collected.\n')
                file.write('Number initial samples:      ' + str(self.initial_design_numdata) + ' \n')
            else:
                file.write('Optimization completed:      ' + 'NO,' + str(self.X.shape[0]).strip(
                    '[]') + ' samples collected.\n')
                file.write('Number initial samples:      ' + str(self.initial_design_numdata) + ' \n')

            file.write('Tolerance:                   ' + str(self.eps) + '.\n')
            file.write('Optimization time:           ' + str(self.cum_time).strip('[]') + ' seconds.\n')

            file.write('\n')
            file.write(
                '--------------------------------' + ' Problem set up ' + '------------------------------------\n')
            file.write('Problem name:                ' + self.objective_name + '\n')
            file.write('Problem dimension:           ' + str(self.dimensionality) + '\n')
            file.write('Number continuous variables  ' + str(len(self.space.get_continuous_dims())) + '\n')
            file.write('Number discrete variables    ' + str(len(self.space.get_discrete_dims())) + '\n')
            file.write('Number bandits               ' + str(self.space.get_bandit().shape[0]) + '\n')
            file.write('Noiseless evaluations:       ' + str(self.exact_feval) + '\n')
            file.write('Cost used:                   ' + self.cost.cost_type + '\n')
            file.write('Constraints:                 ' + str(self.constraints == True) + '\n')
            file.write('Subspace Dimension:          ' + str(self.subspace_dim_size) + '\n')

            file.write('\n')
            file.write(
                '------------------------------' + ' Optimization set up ' + '---------------------------------\n')
            file.write('Normalized outputs:          ' + str(self.normalize_Y) + '\n')
            file.write('Model type:                  ' + str(self.model_type).strip('[]') + '\n')
            file.write('Model update interval:       ' + str(self.model_update_interval) + '\n')
            file.write('Acquisition type:            ' + str(self.acquisition_type).strip('[]') + '\n')
            file.write(
                'Acquisition optimizer:       ' + str(self.acquisition_optimizer.optimizer_name).strip('[]') + '\n')

            file.write('Acquisition type:            ' + str(self.acquisition_type).strip('[]') + '\n')
            if hasattr(self, 'acquisition_optimizer') and hasattr(self.acquisition_optimizer, 'optimizer_name'):
                file.write(
                    'Acquisition optimizer:       ' + str(self.acquisition_optimizer.optimizer_name).strip('[]') + '\n')
            else:
                file.write('Acquisition optimizer:       None\n')
            file.write('Evaluator type (batch size): ' + str(self.evaluator_type).strip('[]') + ' (' + str(
                self.batch_size) + ')' + '\n')
            file.write('Cores used:                  ' + str(self.num_cores) + '\n')

            file.write('\n')
            file.write(
                '---------------------------------' + ' Summary ' + '------------------------------------------\n')
            file.write('Initial X:                       ' + str(self.initial_X) + '\n')
            file.write('Initial Y:                       ' + str(self.initial_Y) + '\n')

            if self.maximize:
                file.write('Value at maximum:            ' + str(format(-min(self.Y)[0], '.20f')).strip('[]') + '\n')
                file.write('Best found maximum location: ' + str(self.X[np.argmin(self.Y), :]).strip('[]') + '\n')
            else:
                file.write('Value at minimum:            ' + str(format(min(self.Y)[0], '.20f')).strip('[]') + '\n')
                file.write('Best found minimum location: ' + str(self.X[np.argmin(self.Y), :]).strip('[]') + '\n')

            file.write(
                '----------------------------------------------------------------------------------------------\n')
            file.close()
