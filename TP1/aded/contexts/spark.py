# ABOUT --------------------------------------------------------------------------------------------
#
# Abstraction for reusable spark session.
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

from datetime import datetime
import gc
import os
import psutil
from pyspark.sql import SparkSession
import re
import requests
from typing import Any

from aded.contexts.context import Context

# Abstraction for reusable spark session.
class SparkContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Necessary state for analysis of Spark performance metrics
        self.threads                         = threads
        self.monitoring                      = bool(kwargs.get('monitoring', False))
        self.next_requested_job              = 0    # First new job id since last cleanup
        self.new_jobs: dict[str, Any] | None = None # New jobs since last cleanup
        self.stages:   dict[str, Any] | None = None # All stages

        # Create Spark session
        self.spark = SparkSession.builder.master(f'local[{threads}]') \
                                         .appName('deucalion-query')  \
                                         .getOrCreate()

        if self.monitoring:
            self.application_id = self.__request('/applications')[0]['id']
        else:
            self.application_id = ''

    def between_runs_cleanup(self) -> None:
        # Trigger Python's and Java's garbage collection to delete old data frames
        self.spark.catalog.clearCache()
        gc.collect()
        self.spark.sparkContext._jvm.System.gc() # type: ignore

        # Request new jobs and stages that were not present in the last query's results
        if self.monitoring:
            all_jobs                = self.__application_request(f'/jobs')
            new_jobs_list           = all_jobs[:len(all_jobs) - self.next_requested_job]
            self.new_jobs           = {job['jobId']: job for job in new_jobs_list[::-1]}
            self.next_requested_job = len(all_jobs)

            all_stages  = self.__application_request(f'/stages?details=true')
            self.stages = {stage['stageId']: stage for stage in all_stages[::-1]}

    def final_cleanup(self) -> None:
        self.spark.stop()

    def get_disk_monitoring_process_pid(self) -> int | None:
        # Return first Java process found in children
        children      = psutil.Process().children()
        spark_process = next(child for child in children if child.name() == 'java')
        return spark_process.pid

    # Parses a Spark timestamp
    @staticmethod
    def parse_time(time: str) -> datetime:
        return datetime.fromisoformat(re.sub('[A-Z]+$', '', time))

    # Calculates the difference in time (in seconds) between Spark timestamps
    @staticmethod
    def time_delta(start: str, end: str) -> float:
        delta = SparkContext.parse_time(end) - SparkContext.parse_time(start)
        return delta.total_seconds()

    # Performs a /api/v1/[path] GET request to Spark's monitoring API
    def __request(self, path: str) -> Any:
        return requests.get(f'http://localhost:4040/api/v1{path}').json()

    # Performs a /api/v1/applications/[app-id]/[path] GET request to Spark's monitoring API
    def __application_request(self, path: str) -> Any:
        return self.__request(f'/applications/{self.application_id}{path}')
