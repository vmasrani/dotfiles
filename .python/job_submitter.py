#!/usr/bin/env python
import os
import subprocess
import time
import datetime
from pprint import pprint
from pathlib import Path
import sys
import itertools

# Global Arguments
BASH_FILE_NAME  = ""
EXPERIMENT_NAME = ""
SCHEDULER       = ""
SLEEP_TIME      = 0.1

# Global Directories
PROJECT_DIR = ""
SRC_PATH    = ""
DATA_DIR    = ""
RESULTS_DIR = ""
MODEL_DIR   = ""
SUBMIT_DIR  = ""

# bash script templates
PBS_TEMPLATE = '''
source /ubc/cs/research/fwood/vadmas/miniconda3/bin/activate ml3_10

echo "Starting job"
echo "Running python command:"
echo "${PYTHON_COMMAND}"
eval "${PYTHON_COMMAND}"

echo "Finished!"
'''

SLURM_TEMPLATE = '''
# ---------------------------------------------------------------------
echo "Current working directory: `pwd`"
echo "Starting run at: `date`"

module load python/3.6
virtualenv --no-download $SLURM_TMPDIR/env
source $SLURM_TMPDIR/env/bin/activate

pip install --no-index --upgrade pip
pip install -r /home/vadmas/dev/envs/requirements_ml3_new.txt
pip install --no-index torch_cpu

echo "Virutalenv created "

# RUN
# ---------------------------------------------------------------------

echo "Running python command:"
echo ${PYTHON_COMMAND}

eval ${PYTHON_COMMAND}

echo "Job complete! "
echo "Ending run at: `date`"
'''


########################
# Main submission loop #
########################

def submit(hyper_dict, project_dir, experiment_name, scheduler_options):
    # Validate Arguments and create bash script
    verify_dirs(project_dir, experiment_name)
    bash_file_name, scheduler = detect_scheduler(scheduler_options)
    make_bash_script(scheduler_options, bash_file_name, scheduler)

    # Init globals
    global BASH_FILE_NAME
    global EXPERIMENT_NAME
    global SCHEDULER
    BASH_FILE_NAME, EXPERIMENT_NAME, SCHEDULER = bash_file_name, experiment_name, scheduler

    # Display info
    hypers = make_hyper_string(hyper_dict)

    print("------Scheduler Options------")
    print(scheduler_options.strip())
    print("-------({})-------".format(SCHEDULER))

    print("Saving results in: {}".format(RESULTS_DIR))
    print("------Sweeping over------")
    pprint(hyper_dict)
    print("-------({} runs)-------".format(len(hypers)))

    # Submit
    ask = True
    for idx, hyper_string in enumerate(hypers):
        python_command = make_python_command(hyper_string)
        command = make_scheduler_command(python_command, hyper_string)

        if ask:
            flag = input("Submit ({}/{}): {}? (y/n/all/exit) ".format(idx + 1, len(hypers), python_command))

        if flag in ['yes', 'all', 'y', 'a']:
            output = subprocess.check_output(command,  stderr=subprocess.STDOUT, shell=True)
            print("Submitting ({}/{}): {}".format(idx + 1, len(hypers), output.strip().decode()))

        if flag in ['all', 'a']:
            ask = False
            time.sleep(SLEEP_TIME)

        if flag in ['exit', 'e']:
            sys.exit()

# returns strings of form: name1=value1 name2=value2 name3=value3...
def make_hyper_string(hyper_dict):
    # Check all values are iterable lists
    def type_check(value):
        return value if isinstance(value, list) else [value]

    hyper_dict = {key: type_check(value) for key, value in hyper_dict.items()}

    commands = []
    for args in itertools.product(*hyper_dict.values()):
        command = "".join(["{}={} ".format(k, v) for k, v in zip(hyper_dict.keys(), args)])
        commands.append(command[:-1])

    return commands


# Strictly enforce directory structure
def verify_dirs(project_dir, experiment_name):
    project_dir = Path(project_dir)
    src_path    = Path(project_dir) / 'run.py'
    data_dir    = Path(project_dir) / 'data'
    submit_dir  = Path(project_dir) / 'submit'

    assert project_dir.is_dir(), "{} does not exist".format(project_dir)
    assert data_dir.is_dir(), "{} does not exist".format(data_dir)
    assert src_path.is_file(), "{} does not exist".format(src_path)
    assert submit_dir.is_dir(), "{} does not exist".format(submit_dir)

    today = datetime.date.today()

    results_dir = project_dir / 'results' / experiment_name / today.strftime("%Y_%m_%d")
    models_dir  = project_dir / 'models'

    results_dir.mkdir(exist_ok=True, parents=True)
    models_dir.mkdir(exist_ok=True, parents=True)

    # make global
    global PROJECT_DIR
    global SRC_PATH
    global DATA_DIR
    global RESULTS_DIR
    global MODEL_DIR
    global SUBMIT_DIR
    PROJECT_DIR, SRC_PATH, DATA_DIR, RESULTS_DIR, MODEL_DIR, SUBMIT_DIR = project_dir, src_path, data_dir, results_dir, models_dir, submit_dir


#########################
#  Bash Script Helpers  #
#########################


def make_bash_script(scheduler_options, bash_file_name, scheduler):
    template = PBS_TEMPLATE if scheduler == 'pbs' else SLURM_TEMPLATE
    if "gpu" in scheduler_options and "torch_cpu" in template:
        template = template.replace("torch_cpu", "torch_gpu")
    bash_contents = "#!/bin/bash {} {}".format(scheduler_options, template)
    with open(bash_file_name, 'w') as rsh:
        rsh.write(bash_contents)


def detect_scheduler(scheduler_options):
    if "#PBS" in scheduler_options:
        bash_file_name = SUBMIT_DIR / "train_pbs.sh"
        scheduler = 'pbs'
    elif "#SBATCH" in scheduler_options:
        bash_file_name = SUBMIT_DIR / "train_slurm.sh"
        scheduler = 'slurm'
    else:
        raise ValueError("Incorrect header")
    return bash_file_name, scheduler


def make_python_command(hyper_string):
    return ("python {src_path} with "
            "data_dir={data_dir} "
            "model_dir={model_dir} "
            "{hyper_string} "
            "-p --name {experiment_name}").format(
                src_path=SRC_PATH,
                data_dir=DATA_DIR,
                model_dir=MODEL_DIR,
                hyper_string=hyper_string,
                experiment_name=EXPERIMENT_NAME)


def make_scheduler_command(python_command, hyper_string):
    identifier = hyper_string.replace(" ", ".")
    save_args = ("-o {results_dir}/{identifier}.res "
                 "-e {results_dir}/{identifier}.err").format(results_dir=RESULTS_DIR, identifier=identifier)
    if SCHEDULER == 'slurm':
        command = ("sbatch {save_args} "
                   "-J {experiment_name} "
                   "--export=ALL,PYTHON_COMMAND=\"{python_command}\" {bash_file_name}").format(save_args=save_args,
                                                                                               python_command=python_command,
                                                                                               experiment_name=EXPERIMENT_NAME,
                                                                                               bash_file_name=BASH_FILE_NAME)

    elif SCHEDULER == 'pbs':
        command = ("qsub {save_args} "
                   "-N {experiment_name} "
                   "-d {project_dir} "
                   "-v PYTHON_COMMAND=\"{python_command}\" {bash_file_name}").format(save_args=save_args,
                                                                                     python_command=python_command,
                                                                                     project_dir=PROJECT_DIR,
                                                                                     experiment_name=EXPERIMENT_NAME,
                                                                                     bash_file_name=BASH_FILE_NAME)
    else:
        raise ValueError

    return command

