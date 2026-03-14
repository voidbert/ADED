# ABOUT --------------------------------------------------------------------------------------------
#
# Fully optimized query implementation.
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

from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from pyspark.sql.types import StructType,  \
                              StructField, \
                              StringType,  \
                              IntegerType, \
                              LongType,    \
                              TimestampType

import os
import typing
import re

from contexts import Context, SparkContext
from query import Query

class Optimized(Query):
    @staticmethod
    def create_context(processes: int) -> Context:
        return SparkContext(processes)

    def load_dataset(self, context: Context, dataset_path: str) -> None:
        # Get Spark session from context
        spark = typing.cast(SparkContext, context).spark

        schema = StructType([
            StructField('JobID'        , StringType()   , True),
            StructField('JobIDRaw'     , IntegerType()  , True),
            StructField('ElapsedRaw'   , IntegerType()  , True),
            StructField('Account'      , StringType()   , True),
            StructField('AllocCPUS'    , IntegerType()  , True),
            StructField('CPUTimeRAW'   , LongType()     , True),
            StructField('NNodes'       , IntegerType()  , True),
            StructField('AllocNodes'   , StringType()   , True),
            StructField('NCPUS'        , IntegerType()  , True),
            StructField('Partition'    , StringType()   , True),
            StructField('TotalCPU'     , TimestampType(), True),
            StructField('User'         , StringType()   , True),
            StructField('ExitCode'     , StringType()   , True),
            StructField('State'        , StringType()   , True),
            StructField('Reservation'  , StringType()   , True),
            StructField('ReservationId', StringType()   , True),
            StructField('AllocTRES'    , StringType()   , True),
        ])

        year_data: DataFrame | None = None
        year_data = spark.read                                                            \
                         .option('delimiter', '|')                                        \
                         .csv(f'{dataset_path}', schema = schema, header = True)          \
                         .select('ElapsedRaw', 'Account', 'NNodes',
                                 'Partition', 'State', 'AllocTRES',
                                 F.regexp_extract(F.input_file_name(),
                                                  r'([^/]+)\.txt$', 1).alias('Filename')) \
                         .withColumn('Period', F.expr('substring(filename, 6)'))          \
                         .drop('Filename')

        assert isinstance(year_data, DataFrame)
        self.data = year_data

    def process_dataset(self, _: Context) -> None:
        self.data = self.data.withColumn(
            'Cluster',
            F.when(
                F.col('Partition').contains('arm'),
                'ARM'
            ).otherwise(
                F.when(
                    F.col('Partition').contains('a100'),
                    'GPU'
                ).otherwise(
                    'AMD'
                )
            )
        ).drop('Partition')

        self.data = self.data.withColumn(
            'Agency',
            F.when(
                F.col('Account').startswith('f'),
                'FCT'
            ).otherwise(
                F.when(
                    F.col('Account').startswith('ee'),
                    'EHPC'
                ).otherwise(
                    'LOCAL'
                )
            )
        ).drop('Account')

        self.data = self.data.withColumn(
            'VNodes',
            F.when(
                F.col('Cluster').contains('GPU'),
                F.when(
                    F.col('AllocTRES').isNull(),
                    F.col('NNodes')
                ).otherwise(
                    F.when(
                        F.col('AllocTRES').rlike(r'gres/gpu=(\d+)'),
                        F.regexp_extract(F.col('AllocTRES'), r'gres/gpu=(\d+)', 1)
                    ).otherwise(
                        F.col('NNodes') * 4
                    )
                )
            ).otherwise(
                F.col('NNodes')
            )
        ).drop('AllocTRES', 'NNodes')

        self.data = self.data.withColumn(
            'totalJobSeconds',
            (F.col('ElapsedRaw') * F.col('VNodes'))
        ).drop('ElapsedRaw', 'VNodes')

        self.data = self.data.withColumn(
            'COMPLETED',
            F.when(
                F.col('State') == 'COMPLETED',
                'COMPLETED'
            ).otherwise('FAILED')
        )

        global_summary = self.data.groupby('Period', 'Cluster', 'Agency', 'COMPLETED') \
                                  .agg(F.count('*').alias('job_count'),
                                       F.sum('totalJobSeconds').alias('total_secs'))   \
                                  .collect()

        for tag, months in self.tag_months.items():
            hours = dict()
            jobs  = dict()

            for row in global_summary:
                if row.Period in months:
                    if row.COMPLETED == 'COMPLETED':
                        self.output_parameters[f'{row.Cluster.lower()}CompletedJobs{tag}'] = \
                            self.output_parameters                                           \
                                .get(f'{row.Cluster.lower()}CompletedJobs{tag}', 0) +        \
                            row.job_count
                    else:
                        self.output_parameters[f'{row.Cluster.lower()}FailedJobs{tag}'] = \
                            self.output_parameters                                        \
                                .get(f'{row.Cluster.lower()}FailedJobs{tag}', 0) +        \
                            row.job_count

                    if row.Agency != 'LOCAL':
                        hours[row.Cluster] = hours.get(row.Cluster, 0) + row.total_secs
                        jobs[row.Cluster]  = jobs.get(row.Cluster, 0)  + row.job_count

                    for key, value in hours.items():
                        self.output_parameters[f'{key.lower()}usedhours{tag}'] = value / 3600

                    for key, value in jobs.items():
                        self.output_parameters[f'{key.lower()}Jobs{tag}'] = value

                    if row.Agency == 'EHPC':
                        self.output_parameters[f'{row.Cluster.lower()}usedhoursEuroHPC{tag}'] = \
                            self.output_parameters                                              \
                                .get(f'{row.Cluster.lower()}usedhoursEuroHPC{tag}', 0) +        \
                            row.total_secs / 3600

                        self.output_parameters[f'{row.Cluster.lower()}JobsEuroHPC{tag}'] = \
                            self.output_parameters                                         \
                                .get(f'{row.Cluster.lower()}JobsEuroHPC{tag}', 0) +        \
                            row.job_count
