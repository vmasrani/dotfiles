#!/usr/bin/env python
import os
import time
import datetime
from pprint import pprint
from pathlib import Path
import sys
import itertools


# returns strings of form: name1=value1 name2=value2 name3=value3...
def make_hyper_string(hyper_dict):
    commands = []
    for args in itertools.product(*hyper_dict.values()):
        command = "".join(["{}={} ".format(k, v) for k, v in zip(hyper_dict.keys(), args)])
        commands.append(command[:-1])
    return commands


def make_python_command(src_path, hyper_string, data_dir, model_dir, experiment_name):
    return ("python {src_path} with "
            "data_dir={data_dir} "
            "model_dir={model_dir} "
            "{hyper_string} "
            "--name {experiment_name}").format(
                src_path=src_path,
                data_dir=data_dir,
                model_dir=model_dir,
                hyper_string=hyper_string,
                experiment_name=experiment_name)


def make_scheduler_command(python_command, bash_src_path, results_dir, scheduler, hyper_string):
    identifier = hyper_string.replace(" ", ".")
    save_args = ("-o {results_dir}/res/{identifier}.res "
                 "-e {results_dir}/err/{identifier}.err").format(results_dir=results_dir,
                                                                 identifier=identifier)
    if scheduler == 'slurm':
        command = ("sbatch {save_args} --export=ALL,"
                   "PYTHON_COMMAND=\"{python_command}\" {bash_src_path}").format(save_args=save_args,
                                                                                 python_command=python_command,
                                                                                 bash_src_path=bash_src_path)

    elif scheduler == 'pbs':
        command = ("qsub {save_args} -v "
                   "PYTHON_COMMAND=\"{python_command}\" {bash_src_path}").format(save_args=save_args,
                                                                                 python_command=python_command,
                                                                                 bash_src_path=bash_src_path)
    else:
        raise ValueError

    return command


def make_results_dir(results_dir):
    today = datetime.date.today()
    results_dir = Path(results_dir)
    assert results_dir.is_dir(), "{} does not exist".format(results_dir)
    results_dir_with_date = results_dir / today.strftime("%Y_%m_%d")

    err = results_dir_with_date / 'err'
    res = results_dir_with_date / 'res'

    err.mkdir(exist_ok=True, parents=True)
    res.mkdir(exist_ok=True, parents=True)

    return str(results_dir_with_date)


def submit(hyper_dict, project_dir, bash_file_name, experiment_name, scheduler="pbs", ask=True, sleep_time=0.1):
    project_dir, src_path, data_dir, results_dir, model_dir = verify_dirs(project_dir)
    hypers = make_hyper_string(hyper_dict)

    print("Saving results in: {}".format(results_dir))
    print("------Sweeping over------")
    pprint(hyper_dict)
    print("-------({} runs)-------".format(len(hypers)))

    for idx, hyper_string in enumerate(hypers):
        python_command = make_python_command(src_path, hyper_string, data_dir, model_dir, experiment_name)
        command = make_scheduler_command(python_command, bash_file_name, results_dir, scheduler, hyper_string)

        if ask:
            flag = input("Submit ({}/{}): {}? (y/n/all/exit) ".format(idx + 1, len(hypers), python_command))
        if flag == 'y':
            os.system(command)
        elif flag == 'all':
            ask = False
            os.system(command)
            time.sleep(sleep_time)
        elif flag == 'exit':
            sys.exit()
        else:
            continue


# Strictly enforce directory structure
def verify_dirs(project_dir):
    project_dir = Path(project_dir)
    src_path     = Path(project_dir) / 'run.py'
    data_dir    = Path(project_dir) / 'data'

    assert project_dir.is_dir(), "{} does not exist".format(project_dir)
    assert data_dir.is_dir(), "{} does not exist".format(data_dir)
    assert src_path.is_file(), "{} does not exist".format(src_path)

    results_dir = project_dir / 'results'
    models_dir  = project_dir / 'models'

    results_dir.mkdir(exist_ok=True, parents=True)
    models_dir.mkdir(exist_ok=True, parents=True)

    results_dir = make_results_dir(results_dir)

    return project_dir, src_path, data_dir, results_dir, models_dir
