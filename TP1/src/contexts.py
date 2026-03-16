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

import duckdb
import gc
import os
import psycopg2
from pyspark.sql import SparkSession
import socket
from types import TracebackType

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

# Abstraction for reusable spark session.
class SparkContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        if kwargs.get('events', ''):
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

    def between_runs_cleanup(self) -> None:
        # Trigger Python's and Java's garbage collection to delete old data frames
        self.spark.catalog.clearCache()
        gc.collect()
        self.spark.sparkContext._jvm.System.gc() # type: ignore

    def final_cleanup(self) -> None:
        self.spark.stop()

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
