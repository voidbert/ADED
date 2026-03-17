# ABOUT --------------------------------------------------------------------------------------------
#
# Spark and database reusable context abstractions.
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

import datetime
import duckdb
import gc
import os
import psutil
import psycopg2
from pyspark.sql import SparkSession
import re
import requests
import socket
from types import TracebackType
from typing import Any

# Abstraction for a reusable Spark session or database connection.
class Context:
    # Method called between performance measurement runs that share the same context.
    # For instance, it is necessary to clean a database between runs.
    def between_runs_cleanup(self) -> None:
        pass

    # Method called after all query runs.
    def final_cleanup(self) -> None:
        pass

    # Method for context management (with-statement support)
    def __enter__(self) -> Context:
        return self

    # Method for context management (with-statement support)
    def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception_value: BaseException | None,
            traceback: TracebackType
        ) -> None:

        self.final_cleanup()

    # Gets the PID of the process whose disk activity should be monitored.
    def get_disk_monitoring_process_pid(self) -> int | None:
        return None

# Abstraction for reusable spark session.
class SparkContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Necessary state for analysis of Spark performance metrics
        self.event_logging                     = bool(kwargs.get('events', ''))
        self.next_requested_job                = 0    # First new job id since last cleanup
        self.next_requested_stage              = 0    # First new stage id since last cleanup
        self.new_jobs:   dict[str, Any] | None = None # New jobs since last cleanup
        self.new_stages: dict[str, Any] | None = None # New stages since last cleanup

        if self.event_logging:
            # Create directory for storing events
            assert isinstance(kwargs['events'], str)
            events_dir = os.path.abspath(kwargs['events'])

            try:
                os.mkdir(events_dir)
            except FileExistsError:
                pass

            # Create Spark session with event logging
            self.spark = SparkSession.builder.master(f'local[{threads}]')              \
                                             .appName('deucalion-query')               \
                                             .config('spark.eventLog.enabled', 'true') \
                                             .config('spark.eventLog.dir', events_dir) \
                                             .getOrCreate()
        else:
            # Create Spark session without event logging
            self.spark = SparkSession.builder.master(f'local[{threads}]') \
                                             .appName('deucalion-query')  \
                                             .getOrCreate()

        if self.event_logging:
            self.application_id = self.__request('/applications')[0]['id']
        else:
            self.application_id = ''

    def between_runs_cleanup(self) -> None:
        # Trigger Python's and Java's garbage collection to delete old data frames
        self.spark.catalog.clearCache()
        gc.collect()
        self.spark.sparkContext._jvm.System.gc() # type: ignore

        # Request new jobs and stages that were not present in the last query's results
        if self.event_logging:
            all_jobs                = self.__application_request(f'/jobs')
            new_jobs_list           = all_jobs[:len(all_jobs) - self.next_requested_job]
            self.new_jobs           = {job['jobId']: job for job in new_jobs_list[::-1]}
            self.next_requested_job = len(all_jobs)

            all_stages                = self.__application_request(f'/stages?details=true')
            new_stages_list           = all_stages[:len(all_stages) - self.next_requested_stage]
            self.new_stages           = {stage['stageId']: stage for stage in new_stages_list[::-1]}
            self.next_requested_stage = len(all_stages)

    def final_cleanup(self) -> None:
        self.spark.stop()

    def get_disk_monitoring_process_pid(self) -> int | None:
        # Return first Java process found in children
        children      = psutil.Process().children()
        spark_process = next(child for child in children if child.name() == 'java')
        return spark_process.pid

    # Caculates the difference in time (in seconds) between Spark timestamps.
    @staticmethod
    def time_delta(start: str, end: str) -> float:
        # Replace timezone for ISO 8601 parsing
        start = re.sub('[A-Z]+$', '+00:00', start)
        end   = re.sub('[A-Z]+$', '+00:00', end)

        # Parse dates and return difference
        start_date = datetime.datetime.fromisoformat(start)
        end_date   = datetime.datetime.fromisoformat(end)
        return (end_date - start_date).total_seconds()

    # Performs a /api/v1/[path] GET request to Spark's monitoring API
    def __request(self, path: str) -> Any:
        return requests.get(f'http://localhost:4040/api/v1{path}').json()

    # Performs a /api/v1/applications/[app-id]/[path] GET request to Spark's monitoring API
    def __application_request(self, path: str) -> Any:
        return self.__request(f'/applications/{self.application_id}{path}')

# Abstraction for reusable PostgreSQL connection.
class PostgreSQLContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Connect to a local database
        self.connection = psycopg2.connect(
            host='localhost',
            port=5432,
            database='postgres',
            user='postgres'
        )

        self.cursor = self.connection.cursor()

    def between_runs_cleanup(self) -> None:
        # Delete all temporary tables
        self.cursor.execute('DISCARD TEMP')

    def final_cleanup(self) -> None:
        self.cursor.close()
        self.connection.close()

    # Converts a file path to one that can be used in PostgreSQL.
    #
    # If PostgreSQL is running in a Docker container, it is assumed the local filesystem is mounted
    # on /mnt.
    def convert_file_path(self, path: str) -> str:
        absolute_path = os.path.abspath(path)
        if socket.gethostname().startswith('cna'): # ARM node (awful heuristic, but it's whatever)
            return absolute_path
        else:
            return f'/mnt{absolute_path}'

# Abstraction for reusable DuckDB connection.
class DuckDBContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Initialize an in-memory database and use a set number of threads
        self.connection = duckdb.connect(':memory:')
        self.connection.execute(f'SET THREADS TO {threads}')

    def between_runs_cleanup(self) -> None:
        # Delete all views
        view_names = self.connection.execute('SELECT view_name FROM duckdb_views').fetchall()
        for view_name_tuple in view_names:
            self.connection.execute(f'DROP VIEW IF EXISTS {view_name_tuple[0]}')

    def final_cleanup(self) -> None:
        self.connection.close()

    def get_disk_monitoring_process_pid(self) -> int | None:
        return os.getpid()
