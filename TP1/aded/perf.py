#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for benchmarking query implementations.
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of Deucalion Job Query.
#
# Deucalion Job Query is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Deucalion Job Query is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Deucalion Job Query.
# If not, see <https://www.gnu.org/licenses/>.
#
# SOURCE FILE --------------------------------------------------------------------------------------

import argparse
import datetime
import json
import socket
import tempfile
import time
import typing

from aded import config, hwmon, util
from aded.contexts import SparkContext

# Parses a list of threads for a scalability analysis
def __parse_thread_list(thread_list: str) -> list[int]:
    return [int(threads) for threads in thread_list.split(',')]

# Processes Spark monitoring metrics for the output file
@typing.no_type_check
def __format_spark_metrics(context: SparkContext) -> typing.Any:
    spark_metrics = {
        'jobs':                [],
        'numJobs':             len(context.new_jobs),
        'numStages':           0,
        'numNonSkippedStages': 0,
        'numTasks':            0,
        'numNonSkippedTasks':  0,
        'shuffleWriteBytes':   0,
        'shuffleWriteRecords': 0,
        'shuffleReadBytes':    0,
        'shuffleReadRecords':  0,
    }

    # Process job, stage, and task data
    transformed_jobs = []
    for job_id, original_job in context.new_jobs.items():
        # Select job metrics to keep
        transformed_job = {
            'jobId':         job_id,
            'executionTime': SparkContext.time_delta(
                original_job['submissionTime'], original_job['completionTime']
            ),

            'stages':              [],
            'numStages':           len(original_job['stageIds']),
            'numNonSkippedStages': 0,
            'numTasks':            original_job['numTasks'],
            'numNonSkippedTasks':  0,
            'shuffleWriteBytes':   0,
            'shuffleWriteRecords': 0,
            'shuffleReadBytes':    0,
            'shuffleReadRecords':  0,
        }

        # Process job stages
        for stage_id in original_job['stageIds']:
            # Select stage metrics to keep
            original_stage    = context.new_stages[stage_id]
            transformed_stage = {
                'stageId': stage_id,
                'skipped': original_stage['status'] == 'SKIPPED',

                'executionTime':       0.0,
                'shuffleWriteBytes':   original_stage['shuffleWriteBytes'],
                'shuffleWriteRecords': original_stage['shuffleWriteRecords'],
                'shuffleReadBytes':    original_stage['shuffleReadBytes'],
                'shuffleReadRecords':  original_stage['shuffleReadRecords'],

                'tasks':              [],
                'numTasks':           original_stage['numTasks'],
                'numNonSkippedTasks': len(original_stage['tasks'])
            }

            if original_stage['status'] != 'SKIPPED':
                transformed_stage['executionTime'] = SparkContext.time_delta(
                    original_stage['submissionTime'], original_stage['completionTime']
                )

            # Process stage tasks
            for task_id, original_task in original_stage['tasks'].items():
                transformed_task = {
                    'taskId':        original_task['taskId'],

                    'executionTime': original_task['duration'] / 1000.0,
                    'shuffleWriteBytes':
                        original_task['taskMetrics']['shuffleWriteMetrics']['bytesWritten'],
                    'shuffleWriteRecords':
                        original_task['taskMetrics']['shuffleWriteMetrics']['recordsWritten'],
                    'shuffleReadBytes':
                        original_task['taskMetrics']['shuffleReadMetrics']['localBytesRead'],
                    'shuffleReadRecords':
                        original_task['taskMetrics']['shuffleReadMetrics']['recordsRead'],
                }

                transformed_stage['tasks'].append(transformed_task)

            # Update job statistics
            transformed_job['numNonSkippedStages'] += original_stage['status'] != 'SKIPPED'
            transformed_job['numNonSkippedTasks']  += transformed_stage['numNonSkippedTasks']
            transformed_job['shuffleWriteBytes']   += transformed_stage['shuffleWriteBytes']
            transformed_job['shuffleWriteRecords'] += transformed_stage['shuffleWriteRecords']
            transformed_job['shuffleReadBytes']    += transformed_stage['shuffleReadBytes']
            transformed_job['shuffleReadRecords']  += transformed_stage['shuffleReadRecords']

            transformed_job['stages'].append(transformed_stage)

        # Update global query statistics
        spark_metrics['numStages']           += transformed_job['numStages']
        spark_metrics['numNonSkippedStages'] += transformed_job['numNonSkippedStages']
        spark_metrics['numTasks']            += transformed_job['numTasks']
        spark_metrics['numNonSkippedTasks']  += transformed_job['numNonSkippedTasks']
        spark_metrics['shuffleWriteBytes']   += transformed_job['shuffleWriteBytes']
        spark_metrics['shuffleWriteRecords'] += transformed_job['shuffleWriteRecords']
        spark_metrics['shuffleReadBytes']    += transformed_job['shuffleReadBytes']
        spark_metrics['shuffleReadRecords']  += transformed_job['shuffleReadRecords']

        spark_metrics['jobs'].append(transformed_job)

    return spark_metrics

# Formats disk metrics for the output file
def __format_disk_metrics(
    disk0: hwmon.DiskStatistics,
    disk1: hwmon.DiskStatistics,
    disk2: hwmon.DiskStatistics) -> dict[str, int]:

    tags = {
        'datasetLoad':    (disk1, disk0),
        'datasetProcess': (disk2, disk1),
        'total':          (disk2, disk0)
    }

    disk_metrics: dict[str, int] = {}
    for tag, (disk_new, disk_old) in tags.items():
        disk                                       = disk_new - disk_old
        disk_metrics[f'{tag}LogicalReadBytes']     = disk.logical_read_bytes
        disk_metrics[f'{tag}LogicalWrittenBytes']  = disk.logical_written_bytes
        disk_metrics[f'{tag}PhysicalReadBytes']    = disk.physical_read_bytes
        disk_metrics[f'{tag}PhysicalWrittenBytes'] = disk.physical_written_bytes

    return disk_metrics

# Formats network interface metrics for the output file
def __format_net_metrics(
    net0: hwmon.NetStatistics,
    net1: hwmon.NetStatistics,
    net2: hwmon.NetStatistics) -> dict[str, int]:

    tags = {
        'datasetLoad':    (net1, net0),
        'datasetProcess': (net2, net1),
        'total':          (net2, net0)
    }

    net_metrics: dict[str, int] = {}
    for tag, (net_new, net_old) in tags.items():
        net                                     = net_new - net_old
        net_metrics[f'{tag}ReceivedBytes']      = net.rx_bytes
        net_metrics[f'{tag}ReceivedPackets']    = net.rx_packets
        net_metrics[f'{tag}TransmittedBytes']   = net.tx_bytes
        net_metrics[f'{tag}TransmittedPackets'] = net.tx_packets

    return net_metrics

if __name__ == '__main__':
    # Parse command-line arguments
    queries = util.get_avaialable_queries()
    parser  = argparse.ArgumentParser()

    parser.add_argument('query', choices=queries)
    parser.add_argument('dataset')

    parser.add_argument('-e', '--events',   nargs='?')
    parser.add_argument('-o', '--outfile',  nargs='?')
    parser.add_argument('-w', '--warmup',   nargs='?', type=int)
    parser.add_argument('-r', '--runs',     nargs='?', type=int)
    parser.add_argument('-n', '--nthreads', nargs='?', type=__parse_thread_list)

    args = parser.parse_args()

    # Use default arguments if arguments are not set
    query_class = queries[args.query]
    output_file = args.outfile  or 'perf.json'
    warmup_runs = args.warmup   or 0
    runs        = args.runs     or 3
    nthreads    = args.nthreads or [util.get_context_threads()]

    # Run scalability analysis
    output_data = {
        'query':       args.query,
        'hostname':    socket.gethostname(),
        'scalability': {}
    }

    for nthread in nthreads:
        # Create (and time) context creation
        context_init_start = time.monotonic()
        with query_class.create_context(nthread, events=args.events) as context:
            context_init_end  = time.monotonic()

            disk_monitoring_pid = context.get_disk_monitoring_process_pid()
            scalability_entry   = {
                'threads':         nthread,
                'contextInitTime': context_init_end - context_init_start,
                'runs':            []
            }

            # Run all runs for the current number of threads
            for run in range(warmup_runs + runs):
                # User feedback
                if run >= warmup_runs:
                    run_number = run + 1 - warmup_runs
                    print(f'Running: {nthread} threads -- run {run_number}')
                else:
                    print(f'Running: {nthread} threads -- warmup run {run + 1}')

                # Measure various hardware metrics for dataset loading and query execution
                t0    = time.monotonic()
                cpu0  = hwmon.get_working_cpu_time()
                disk0 = hwmon.get_disk_statistics(disk_monitoring_pid)
                net0  = hwmon.get_net_statistics()

                query = query_class(config.MONTH, config.YEAR, datetime.date(config.YEAR, 1, 1))
                query.load_dataset(context, args.dataset)

                t1    = time.monotonic()
                cpu1  = hwmon.get_working_cpu_time()
                disk1 = hwmon.get_disk_statistics(disk_monitoring_pid)
                net1  = hwmon.get_net_statistics()

                query.process_dataset(context)

                with tempfile.NamedTemporaryFile() as query_output_file:
                    query.output_result(query_output_file.name)

                t2    = time.monotonic()
                cpu2  = hwmon.get_working_cpu_time()
                disk2 = hwmon.get_disk_statistics(disk_monitoring_pid)
                net2  = hwmon.get_net_statistics()

                # Cleanup context before next run
                context.between_runs_cleanup()

                # Add non-warmup runs to output file
                if run >= warmup_runs:
                    run_entry = {
                        'run':                    run_number,
                        'datasetLoadTime':        t1 - t0,
                        'datasetProcessTime':     t2 - t1,
                        'totalTime':              t2 - t0,
                        'cpuMetrics': {
                            'datasetLoadCPUUsage':    (cpu1 - cpu0) / (t1 - t0),
                            'datasetProcessCPUUsage': (cpu2 - cpu1) / (t2 - t1),
                            'totalCPUUsage':          (cpu2 - cpu0) / (t2 - t0)
                        }
                    }

                    # Add additional Spark information
                    if isinstance(context, SparkContext):
                        run_entry['sparkMetrics'] = __format_spark_metrics(context)

                    # Add disk monitoring metrics
                    if disk_monitoring_pid:
                        assert disk0 is not None
                        assert disk1 is not None
                        assert disk2 is not None
                        run_entry['diskMetrics'] = __format_disk_metrics(disk0, disk1, disk2)

                    # Add network monitoring metrics
                    if config.NETWORK_INTERFACE:
                        assert net0 is not None
                        assert net1 is not None
                        assert net2 is not None
                        run_entry['netMetrics'] = __format_net_metrics(net0, net1, net2)

                    # Add runt to list of runs
                    scalability_entry['runs'].append(run_entry)

        # Add thread data to final file
        output_data['scalability'][str(nthread)] = scalability_entry

    # Output file data
    with open(output_file, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)
        json_file.write('\n')
