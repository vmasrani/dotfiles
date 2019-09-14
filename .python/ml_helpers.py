from __future__ import division
import torch
import numpy as np
import pandas as pd
import random

class AverageMeter(object):
    """
    Computes and stores the average and current value
    Taken from https://github.com/pytorch/examples/blob/master/imagenet/main.py
    """

    def __init__(self, name, fmt=':f'):
        self.name = name
        self.fmt = fmt
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

    def __str__(self):
        fmtstr = '{name} {val' + self.fmt + '} ({avg' + self.fmt + '})'
        return fmtstr.format(name=self.name, val=self.val, avg=self.avg)


class MovingAverageMeter(object):
    """Computes the  moving average of a given float."""

    def __init__(self, name, fmt=':f', window=5):
        self.name = "{} (window = {})".format(name, window)
        self.fmt = fmt
        self.N = window
        self.history = []
        self.val = None
        self.reset()

    def reset(self):
        self.val = None
        self.history = []

    def update(self, val):
        self.history.append(val)
        self.previous = self.val
        if self.val is None:
            self.val = val
        else:
            window = self.history[-self.N:]
            self.val = sum(window) / len(window)
            if len(window)  == self.N:
                self.history == window
        return self.val

    @property
    def relative_change(self):
        if None not in [self.val, self.previous]:
            relative_change = (self.previous - self.val) / self.previous
            return relative_change
        else:
            return 0

    def __str__(self):
        fmtstr = '{name} {val' + self.fmt + '} ({avg' + self.fmt + '})'
        return fmtstr.format(name=self.name, val=self.val, avg=self.relative_change)


def tensor(data, args):
    return torch.tensor(np.array(data), device=args.device, dtype=torch.float)


def logaddexp(a, b):
    """Returns log(exp(a) + exp(b))."""

    return torch.logsumexp(torch.cat([a.unsqueeze(0), b.unsqueeze(0)]), dim=0)


def lognormexp(values, dim=0):
    """Exponentiates, normalizes and takes log of a tensor.

    Args:
        values: tensor [dim_1, ..., dim_N]
        dim: n

    Returns:
        result: tensor [dim_1, ..., dim_N]
            where result[i_1, ..., i_N] =
                                 exp(values[i_1, ..., i_N])
            log( ------------------------------------------------------------ )
                    sum_{j = 1}^{dim_n} exp(values[i_1, ..., j, ..., i_N])
    """

    log_denominator = torch.logsumexp(values, dim=dim, keepdim=True)
    # log_numerator = values
    return values - log_denominator


def exponentiate_and_normalize(values, dim=0):
    """Exponentiates and normalizes a tensor.

    Args:
        values: tensor [dim_1, ..., dim_N]
        dim: n

    Returns:
        result: tensor [dim_1, ..., dim_N]
            where result[i_1, ..., i_N] =
                            exp(values[i_1, ..., i_N])
            ------------------------------------------------------------
             sum_{j = 1}^{dim_n} exp(values[i_1, ..., j, ..., i_N])
    """

    return torch.exp(lognormexp(values, dim=dim))


def seed_all(seed):
    """Seed all devices deterministically off of seed and somewhat
    independently."""
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def converged(loss, previous_loss, thresh=1e-3, check_increased=True, raise_on_increased=False, maximize=False):
    eps = np.finfo(float).eps
    inf = float('inf')
    converged = False
    assert not torch.isnan(loss), '****** loss is nan ********'

    diff = previous_loss - loss
    delta_diff = abs(diff)
    avg_diff = (abs(loss) + abs(previous_loss) + eps) / 2

    if check_increased:
        if maximize:
            if diff > 1e-3:  # allow for a little imprecision
                print('******loss decreased from %6.4f to %6.4f!\n' % (previous_loss, loss))
                if raise_on_increased:
                    raise ValueError
        else:
            if diff < -1e-3:  # allow for a little imprecision
                print('******loss increased from %6.4f to %6.4f!\n' % (previous_loss, loss))
                if raise_on_increased:
                    raise ValueError

    if (delta_diff == inf) & (avg_diff == inf):
        return converged

    if (delta_diff / avg_diff) < thresh:
        converged = True

    return converged


def get_grad(nn_module):
    """Returns a flattened tensor of gradient of an nn.Module."""

    grad = torch.zeros(0)
    for param in nn_module.parameters():
        grad = torch.cat([grad, torch.flatten(param.grad)])
    return grad


def log_ess(log_weight):
    """Log of Effective sample size.
    Args:
        log_weight: Unnormalized log weights
            torch.Tensor [batch_size, S] (or [S])
    Returns: log of effective sample size [batch_size] (or [1])
    """
    dim = 1 if log_weight.ndimension() == 2 else 0

    return 2 * torch.logsumexp(log_weight, dim=dim) - \
        torch.logsumexp(2 * log_weight, dim=dim)


def ess(log_weight):
    """Effective sample size.
    Args:
        log_weight: Unnormalized log weights
            torch.Tensor [batch_size, S] (or [S])
    Returns: effective sample size [batch_size] (or [1])
    """

    return torch.exp(log_ess(log_weight))
