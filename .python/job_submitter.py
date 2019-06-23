#!/usr/bin/env python
import os
import time
import sys
import itertools

SLEEP_TIME = 0.1

def make_hyper_string(hyper_dict):
    commands = []
    for args in itertools.product(*hyper_dict.values()):
        command = "".join(["{}={},".format(k, v) for k, v in zip(hyper_dict.keys(), args)])
        commands.append(command[:-1])
    return commands

def submit(hyper_dict, results_path, file_name, scheduler="pbs", ask=True):
    hypers = make_hyper_string(hyper_dict)

    if scheduler == 'slurm':
        commands = ["sbatch -o {0}/{1}.res -e {0}/{1}.err  --export=ALL,{1} {2}".format(results_path, hyper, file_name) for hyper in hypers]
    elif scheduler == 'pbs':
        commands = ["qsub -o {0}/{1}.res -o {0}/{1}.err -v {1} {2}".format(results_path, hyper, file_name) for hyper in hypers]
    else:
        raise ValueError

    print("Submitting {} commands".format(len(commands)))

    for command in commands:
        if ask:
            flag = input("Run: {}? (y/n/all/exit) ".format(command))
        if flag == 'y':
            os.system(command)
        elif flag == 'n':
            print("n")
        elif flag == 'all':
            ask = False
            os.system(command)
            time.sleep(SLEEP_TIME)
        elif flag == 'exit':
            sys.exit()
        else:
            commands.append(command)
