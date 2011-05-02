"""
Implements iterative algorithm class.
"""
import numpy as np
from copy import copy
import lo

from linesearch import *
from criterions import *

# defaults
TOL = 1e-6
GTOL = 1e-6
MAXITER = 100

# stop conditions
class StopCondition(object):
    def _test_maxiter(self, algo):
        return algo.iter_ > self.maxiter
    def _test_tol(self, algo):
        self.resid = np.abs(algo.last_criterion - algo.current_criterion)
        self.resid /= algo.first_criterion
        return self.resid < self.tol
    def _test_gtol(self, algo):
        return algo.current_gradient_norm < self.gtol
    _all_tests = [_test_maxiter, _test_tol, _test_gtol]
    def __init__(self, maxiter=None, tol=None, gtol=None, cond=np.any):
        self.cond = cond
        self.maxiter = maxiter
        self.tol = tol
        self.gtol = gtol
        self.all_val = [self.maxiter, self.tol, self.gtol]
        # filter out tests with None values
        self.tests_val = [val for val in self.all_val
                          if val is not None]
        self.tests = [test
                      for test, val in zip(self._all_tests, self.all_val)
                      if val is not None]
        # store values for printing
        self.resid = None
    def __call__(self, algo):
        return self.cond([test(self, algo) for test in self.tests])

default_stop = StopCondition(maxiter=MAXITER, tol=TOL, gtol=GTOL)

# update types

def fletcher_reeves(algo):
    """
    Fletcher-Reeves descent direction update method.
    """
    return algo.current_gradient_norm / algo.last_gradient_norm

def polak_ribiere(algo):
    """
    Polak-Ribiere descent direction update method.
    """
    b =  np.dot(algo.current_gradient.T,
                (algo.current_gradient - algo.last_gradient))
    b /= np.norm(algo.last_gradient)
    return b

# callback function

class Callback(object):
    def __init__(self, verbose=False, savefile=None):
        self.verbose = verbose
        self.savefile = savefile
    def print_status(self, algo):
        if self.verbose:
            if algo.iter_ == 1:
                print('Iteration \t Criterion')
            print("\t%i \t %e" %
                  (algo.iter_, algo.current_criterion))
    def save(self, algo):
        if self.savefile is not None:
            var_dict = {
                "iter":algo.iter_,
                "criterion":algo.current_criterion,
                "solution":algo.current_solution,
                }
            np.savez(self.savefile, **var_dict)
    def __call__(self, algo):
        if self.verbose:
            self.print_status(algo)
        if self.savefile is not None:
            self.save(algo)

default_callback = Callback()

# algorithms

class Algorithm(object):
    """
    Abstract class to define iterative algorithms.

    Attributes
    ----------

    iter_ : int
        Current iteration number.

    Methods
    -------

    initialize : Set variables to initial state
    iterate : perform one iteration and return current solution
    callback : user-defined function to print status or save variables
    cont : continue the optimization skipping initialiaztion
    __call__ : perform the optimization unt stop_condition is reached
    """
    def initialize(self):
        self.iter_ = 0
        self.current_solution = None
    def callback(self):
        pass
    def iterate(self):
        """
        Perform one iteration and returns current solution.
        """
        self.iter_ += 1
        self.callback(self)
        # return value not used in loop but usefull in "interactive mode"
        return self.current_solution
    def __call__(self):
        """
        Perform the optimization.
        """
        self.initialize()
        self.iterate() # at least 1 iteration
        return self.cont()
    def cont(self):
        """
        Continue an interrupted estimation (like call but avoid
        initialization).
        """
        while not self.stop_condition(self):
            self.iterate()
        return self.current_solution

class ConjugateGradient(Algorithm):
    """
    Apply the conjugate gradient algorithm to a Criterion instance.

    Parameters
    ----------

    criterion : Criterion
        A Criterion instance. It should have following methods and attributes:
            __call__ : returns criterion values at given point
            gradient : returns gradient (1st derivative) of criterion at given point
            n_variable: the size of the input vector of criterion

    x0 : ndarray (None)
        The first guess of the algorithm.

    callback : function (default_callback)
        Perform some printing / saving operations at each iteration.

    stop_condition : function (default_stop)
        Defines when the iterations should stop

    update_type : function (fletcher_reeves)
        Type of descent direction update : e.g. fletcher_reeves, polak_ribiere

    line_search : function (optimal step)
        Line search method to find the minimum along each direction at each
        iteration.

    Returns
    -------

    Returns an algorithm instance. Optimization is performed by
    calling the this instance.

    """
    def __init__(self, criterion, x0=None,
                 callback=default_callback,
                 stop_condition=default_stop,
                 update_type=fletcher_reeves,
                 line_search=optimal_step, **kwargs):
        self.criterion = criterion
        self.gradient = criterion.gradient
        self.n_variables = self.criterion.n_variables
        # functions
        self.callback = callback
        self.stop_condition = stop_condition
        self.update_type = update_type
        self.line_search = line_search
        self.kwargs = kwargs
        # to store values
        self.current_criterion = None
        self.current_solution = None
        self.current_gradient = None
        self.current_gradient_norm = None
        self.current_descent = None
        self.last_criterion = None
        self.last_solution = None
        self.last_gradient = None
        self.last_gradient_norm = None
        self.last_descent = None
    def initialize(self):
        """
        Initialize required values.
        """
        self.first_guess()
        self.first_criterion = self.criterion(self.current_solution)
        self.current_criterion = self.first_criterion
        Algorithm.initialize(self)
    def first_guess(self, x0=None):
        """
        Sets current_solution attribute to initial value.
        """
        if x0 is None:
            self.current_solution = np.zeros(self.n_variables)
        else:
            self.current_solution = copy(x0)
    # update_* functions encode the actual algorithm
    def update_gradient(self):
        self.last_gradient = copy(self.current_gradient)
        self.current_gradient = self.gradient(self.current_solution)
    def update_gradient_norm(self):
        self.last_gradient_norm = copy(self.current_gradient_norm)
        self.current_gradient_norm = norm2(self.current_gradient)
    def update_descent(self):
        if self.iter_ == 0:
            self.current_descent = - self.current_gradient
        else:
            self.last_descent = copy(self.current_descent)
            b = self.update_type(self)
            self.current_descent = - self.current_gradient + b * self.last_descent
    def update_solution(self):
        self.last_solution = copy(self.current_solution)
        a = self.line_search(self)
        self.current_solution += a * self.current_descent
    def update_criterion(self):
        self.last_criterion = copy(self.current_criterion)
        self.current_criterion = self.criterion(self.current_solution)
    def iterate(self):
        """
        Update all values.
        """
        self.update_gradient()
        self.update_gradient_norm()
        self.update_descent()
        self.update_solution()
        self.update_criterion()
        Algorithm.iterate(self)

class QuadraticConjugateGradient(ConjugateGradient):
    """
    A subclass of ConjugateGradient using a QuadraticCriterion.
    """
    def __init__(self, model, data, priors=[], hypers=[], **kwargs):
        store = kwargs.pop("store", True)
        criterion = QuadraticCriterion(model, data, hypers=hypers,
                                       priors=priors, store=store)
        ConjugateGradient.__init__(self, criterion, **kwargs)

class HuberConjugateGradient(ConjugateGradient):
    """
    A subclass of ConjugateGradient using an HuberCriterion.
    """
    def __init__(self, model, data, priors=[], hypers=[], deltas=None, **kwargs):
        store = kwargs.pop("store", True)
        criterion = HuberCriterion(model, data, hypers=hypers, priors=priors,
                                   deltas=deltas, store=store)
        ConjugateGradient.__init__(self, criterion, **kwargs)
 
# for backward compatibility

def acg(model, data, priors=[], hypers=[], **kwargs):
    algorithm = QuadraticConjugateGradient(model, data, priors=priors,
                                           hypers=hypers, **kwargs)
    sol = algorithm()
    return sol

def hacg(model, data, priors=[], hypers=[], deltas=None, **kwargs):
    algorithm = HuberConjugateGradient(model, data, priors=priors,
                                       hypers=hypers, deltas=deltas, **kwargs)
    sol = algorithm()
    return sol

# other

def normalize_hyper(hyper, y, x):
    """
    Normalize hyperparamaters so that they are independent of pb size
    """
    nx = float(x.size)
    ny = float(y.size)
    return np.asarray(hyper) * ny / nx