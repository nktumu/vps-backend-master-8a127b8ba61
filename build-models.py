# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

"""
Train models, create model pickle files, and create and populate constants database.
"""
import itertools
import pathlib
import re
import shutil
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def main():
    # Main directories used in this script
    root_data_dir = pathlib.Path("data")
    root_model_dir = pathlib.Path("src/core/use_core/conf/models")

    shutil.rmtree(root_model_dir)
    root_model_dir.mkdir()

    # Database schema setup
    conn = sqlite3.connect(str(root_model_dir / "constants.db"))
    conn.execute(
        """create table constants_table (
            appliance text not null,
            site_version text not null,
            task text not null,
            workload text not null,
            name text not null,
            value real not null
            );
        """
    )
    conn.commit()

    # Values for specifying different datasets and models
    appliances = [
        "5150",
        "5240",
        "5250",
        "5250-FLEX",
        "5260-FLEX",
        "5340",
        "5350",
        "5350-FLEX",
        "5360-FLEX",
        "access-3340",
    ]
    site_versions = ["8.2", "8.3", "8.3-7.4.3", "9.0"]
    tasks = ["backup"]
    workloads = ["default", "vmware", "ma_cc", "ma_msdp_cc"]

    copies = {
        ("access-3340", "9.0", "backup", "ma_msdp_cc"): (
            "access-3340",
            "8.3-7.4.3",
            "backup",
            "msdp-c",
        ),
        ("access-3340", "9.0", "backup", "ma_cc"): (
            "access-3340",
            "8.3-7.4.3",
            "backup",
            "msdp-c",
        ),
        ("5250", "8.2", "backup", "ma_cc"): ("5340", "8.2", "backup", "ma_cc"),
        ("5250", "8.2", "backup", "ma_msdp_cc"): (
            "5340",
            "8.2",
            "backup",
            "ma_msdp_cc",
        ),
        ("5250", "8.3", "backup", "ma_cc"): ("5340", "8.3", "backup", "ma_cc"),
        ("5250", "8.3", "backup", "ma_msdp_cc"): (
            "5340",
            "8.3",
            "backup",
            "ma_msdp_cc",
        ),
        ("5250", "9.0", "backup", "ma_cc"): ("5340", "9.0", "backup", "ma_cc"),
        ("5250", "9.0", "backup", "ma_msdp_cc"): (
            "5340",
            "9.0",
            "backup",
            "ma_msdp_cc",
        ),
        ("5350", "9.0", "backup", "ma_cc"): ("5340", "9.0", "backup", "ma_cc"),
        ("5350", "9.0", "backup", "ma_msdp_cc"): (
            "5340",
            "9.0",
            "backup",
            "ma_msdp_cc",
        ),
        ("5350-FLEX", "9.0", "backup", "ma_cc"): ("5340", "9.0", "backup", "ma_cc"),
        ("5350-FLEX", "9.0", "backup", "ma_msdp_cc"): (
            "5340",
            "9.0",
            "backup",
            "ma_msdp_cc",
        ),
        ("5260-FLEX", "9.0", "backup", "ma_cc"): ("5340", "9.0", "backup", "ma_cc"),
        ("5260-FLEX", "9.0", "backup", "ma_msdp_cc"): (
            "5340",
            "9.0",
            "backup",
            "ma_msdp_cc",
        ),
        ("5260-FLEX", "9.0", "backup", "default"): ("5250", "9.0", "backup", "default"),
        ("5260-FLEX", "9.0", "backup", "vmware"): ("5250", "9.0", "backup", "vmware"),
        ("5360-FLEX", "9.0", "backup", "vmware"): ("5350", "9.0", "backup", "vmware"),
        ("5360-FLEX", "9.0", "backup", "ma_cc"): ("5340", "9.0", "backup", "ma_cc"),
        ("5360-FLEX", "9.0", "backup", "ma_msdp_cc"): (
            "5340",
            "9.0",
            "backup",
            "ma_msdp_cc",
        ),
    }

    # Main loop for fitting models and populating database
    for (
        orig_appliance,
        orig_site_version,
        orig_task,
        orig_workload,
    ) in itertools.product(appliances, site_versions, tasks, workloads):
        copy_key = (orig_appliance, orig_site_version, orig_task, orig_workload)
        (appliance, site_version, task, workload) = copies.get(copy_key, copy_key)

        # Further path setup
        if workload == "vmware":
            data_dir = root_data_dir / appliance / site_version / "default"
        else:
            data_dir = root_data_dir / appliance / site_version / workload

        if not data_dir.is_dir():
            continue
        model_dir = root_model_dir / orig_appliance / orig_site_version / orig_workload

        model_dir.mkdir(parents=True)

        cpu_model_path = model_dir / "cpu-model.pkl"
        memory_model_path = model_dir / "memory-model.pkl"

        # Model training
        train_cpu_model(
            data_dir,
            appliance,
            orig_appliance,
            orig_site_version,
            orig_task,
            orig_workload,
            cpu_model_path,
            conn,
        )
        train_memory_model(
            data_dir,
            appliance,
            orig_appliance,
            orig_site_version,
            orig_task,
            orig_workload,
            memory_model_path,
            conn,
        )

        conn.commit()

    # Cleanup
    conn.close()


def get_cpu_data(data_dir, task, workload, appliance):
    if "access" in appliance:
        return get_cpu_data_msdpc(data_dir, task, workload, appliance)
    if "cc" in workload:
        return get_cpu_data_cc(data_dir, task, workload, appliance)

    if appliance == "5250":
        df = pd.read_csv(
            data_dir / "throughput.average",
            names=[
                "dedup_ratio",
                "num_streams",
                "kb_transferred",
                "elapsed_avg",
                "avg_throughput",
                "min_eff1_elapsed",
                "max_eff1_elapsed",
                "eff_throughput_1",
                "eff_2_elapsed",
                "eff_throughput_2",
            ],
            sep=" ",
        )
        df.rename(
            columns={
                "eff_2_elapsed": "elapsed_time",
                "eff_throughput_2": "kb_throughput",
            },
            inplace=True,
        )
        df.drop(
            [
                "elapsed_avg",
                "avg_throughput",
                "min_eff1_elapsed",
                "max_eff1_elapsed",
                "eff_throughput_1",
            ],
            axis=1,
            inplace=True,
        )
        df["dedup_ratio"] = df["dedup_ratio"].astype(int)
    elif appliance == "5360-FLEX":
        df = pd.read_csv(
            data_dir / "throughput.average",
            names=[
                "dedup_ratio",
                "num_streams",
                "kb_transferred",
                "elapsed_avg",
                "avg_throughput",
                "eff_elapsed",
                "eff_throughput",
            ],
            sep="\t",
        )
        df.drop(["elapsed_avg", "avg_throughput"], axis=1, inplace=True)
        df.rename(
            columns={"eff_elapsed": "elapsed_time", "eff_throughput": "kb_throughput"},
            inplace=True,
        )
    else:
        df = pd.read_csv(
            data_dir / "throughput.average",
            names=[
                "dedup_ratio",
                "num_streams",
                "kb_transferred",
                "elapsed_time",
                "kb_throughput",
            ],
            sep=" ",
        )

    vm_df = pd.DataFrame(
        columns=["swapout", "cpu_usage_pct", "num_streams", "dedup_ratio"]
    )
    vmstat_original_column_names = [
        "r",
        "b",
        "swpd",
        "free",
        "buff",
        "cache",
        "si",
        "so",
        "bi",
        "bo",
        "in",
        "cs",
        "us",
        "sy",
        "id",
        "wa",
        "st",
    ]

    if appliance == "5360-FLEX":
        vm_df = pd.read_csv(data_dir / "vmstat.detail", sep="\t")
        vm_df.drop(
            [
                "r",
                "b",
                "swpd",
                "free",
                "buff",
                "cache",
                "si",
                "bi",
                "bo",
                "in",
                "cs",
                "st",
            ],
            axis=1,
            inplace=True,
        )
        vm_df["cpu_usage_pct"] = vm_df["us"] + vm_df["sy"] + vm_df["wa"]
        vm_df.rename(
            columns={
                "ded": "dedup_ratio",
                "str": "num_streams",
                "so": "swapout",
            },
            inplace=True,
        )
    else:
        for item in data_dir.glob("vmstat*.detail"):
            filename_parser_regex = (
                r"^vmstat.backup.(\d+)str.(\d+)ded.run(?:\d+).detail$"
            )
            m = re.match(filename_parser_regex, item.name)
            num_streams, dedup_ratio = [int(x) for x in m.groups()]
            if appliance in ["5350", "5350-FLEX"]:
                vmstat_data = pd.DataFrame(columns=vmstat_original_column_names)
                for line in item.read_text().splitlines():
                    parts = line.split()
                    if parts[0] in ["procs", "r"]:
                        # header line
                        continue
                    values = [
                        [int(p)] for p in parts[: len(vmstat_original_column_names)]
                    ]
                    row = dict(zip(vmstat_original_column_names, values))
                    vmstat_data = pd.concat(
                        [vmstat_data, pd.DataFrame(row)], ignore_index=True, sort=True
                    )
            else:
                vmstat_data = pd.read_csv(
                    item, sep=" ", header=None, names=vmstat_original_column_names
                )
            swapout_sum = vmstat_data["so"].sum()
            if vmstat_data["wa"].mean() != 0:
                # logger.warning("Nonzero average wait time.")
                pass
            avg_cpu_usage = (
                vmstat_data["us"].mean()
                + vmstat_data["sy"].mean()
                + vmstat_data["wa"].mean()
            )
            vm_df = pd.concat(
                [
                    vm_df,
                    pd.DataFrame(
                        {
                            "swapout": [swapout_sum],
                            "cpu_usage_pct": [avg_cpu_usage],
                            "num_streams": [num_streams],
                            "dedup_ratio": [dedup_ratio],
                        }
                    ),
                ],
                ignore_index=True,
                sort=True,
            )
    for col_name in vm_df.columns:
        vm_df[col_name] = pd.to_numeric(vm_df[col_name])

    merged_df = df.merge(vm_df, on=["num_streams", "dedup_ratio"])
    merged_df["cpu_usage_secs"] = (merged_df["cpu_usage_pct"] / 100) * merged_df[
        "elapsed_time"
    ]
    merged_df = merged_df.loc[merged_df["kb_throughput"] > 0]
    merged_df["dedup_ratio"] /= 100
    return merged_df


def get_cpu_data_cc(data_dir, task, workload, appliance):
    if appliance in ["5340", "5350", "5350-FLEX"]:
        tp_df = get_5340_cc_throughput_data(data_dir)
        vm_df = get_5340_cc_vmstat_data(data_dir)
    else:
        if workload == "ma_cc":
            name = "flex019-ma04"
        elif workload == "ma_msdp_cc":
            name = "flex019-ma03"
        tp_df = get_throughput_data(data_dir, name, task)
        vm_df = get_vmstat_data(data_dir, "eagappflx019", task)

    merged_df = tp_df.merge(vm_df, on=["num_streams", "dedup_ratio"])
    merged_df["cpu_usage_secs"] = (merged_df["cpu_usage_pct"] / 100) * merged_df[
        "elapsed_time"
    ]
    merged_df = merged_df.loc[merged_df["kb_throughput"] > 0]
    merged_df["dedup_ratio"] /= 100
    return merged_df


def get_cpu_data_msdpc(data_dir, task, workload, appliance):
    path = data_dir / "throughput.csv"
    df = pd.read_csv(path)
    df.rename(
        columns={"avgelapsed": "cpu_usage_secs", "totalsz": "mb_transferred"},
        inplace=True,
    )
    df["kb_transferred"] = df["mb_transferred"]
    df["dedup_ratio"] = df["dedup.1"] / 100
    return df


def get_5340_cc_throughput_data(data_dir):
    path = data_dir / "backup.summary"
    df = pd.read_csv(path, sep="\t")
    df.rename(
        columns={
            "ded": "dedup_ratio",
            "str": "num_streams",
            "datasize(MB)": "total_size",
            "total_elapsed": "elapsed_time",
            "appThput(MB/s)": "mb_throughput",
        },
        inplace=True,
    )
    df["kb_throughput"] = df["mb_throughput"]
    df["kb_transferred"] = df["total_size"]
    return df


def get_5340_cc_vmstat_data(data_dir):
    return pd.concat(
        parse_5340_cc_vmstat_file(path) for path in data_dir.glob("vmstat.*")
    )


def parse_5340_cc_vmstat_file(file_path):
    filename_parser_regex = r"^vmstat.(\d+)str"
    m = re.match(filename_parser_regex, file_path.name)
    num_streams = int(m.group(1))

    vmstat_cols = [
        "r",
        "b",
        "swpd",
        "free",
        "buff",
        "cache",
        "si",
        "so",
        "bi",
        "bo",
        "in",
        "cs",
        "us",
        "sy",
        "id",
        "wa",
        "st",
    ]
    df = pd.DataFrame(columns=vmstat_cols)
    for line in file_path.read_text().splitlines():
        parts = line.split()
        if parts[0] in ["procs", "r"]:
            # header line
            continue
        values = [[int(p)] for p in parts[: len(vmstat_cols)]]
        row = dict(zip(vmstat_cols, values))
        df = pd.concat([df, pd.DataFrame(row)], ignore_index=True, sort=True)

    df["cpu_usage_pct"] = df["us"] + df["sy"] + df["wa"]
    avg_cpu = df["cpu_usage_pct"].mean()
    total_swapout = df["so"].sum()

    return pd.DataFrame(
        {
            "dedup_ratio": [90],
            "num_streams": num_streams,
            "cpu_usage_pct": avg_cpu,
            "swapout": total_swapout,
        }
    )


def get_throughput_data(data_dir, appliance_name, task):
    return pd.concat(
        parse_throughput_summmary_file(path, appliance_name, task)
        for path in data_dir.glob(f"throughput.{appliance_name}.{task}*.summary")
    )


def parse_throughput_summmary_file(file_path, appliance_name, task):
    regex = r"throughput\.(flex\d+)+-(ma\d+)\.(\w+)\.(\d+)str\.(\d+)ded\.summary"
    m = re.match(regex, file_path.name)
    flex_type, ma_type, task, num_streams, dedup_ratio = m.groups()
    column_names = [
        "total_size",
        "elapsed_time",
        "avg_throughput",
        "min_elapsed_time",
        "max_elapsed_time",
        "effective_throughput_1",
        "total_elapsed_time",
        "effective_throughput_2",
        "mystery_value",
    ]
    dat = pd.read_csv(file_path, sep=" ", names=column_names)
    dat["flex_type"] = flex_type
    dat["ma_type"] = ma_type
    dat["task"] = task
    dat["num_streams"] = int(num_streams)
    dat["dedup_ratio"] = int(dedup_ratio)

    dat.rename(
        columns={
            "total_size": "kb_transferred",
            "effective_throughput_2": "kb_throughput",
        },
        inplace=True,
    )
    return dat


def read_vmstat_detail_file(file_path, appliance_name, task):
    filename_parser_regex = (
        f"^vmstat.{appliance_name}.{task}." + r"(\d+)str.(\d+)ded.detail$"
    )
    vmstat_original_column_names = [
        "r",
        "b",
        "swpd",
        "free",
        "buff",
        "cache",
        "si",
        "so",
        "bi",
        "bo",
        "in",
        "cs",
        "us",
        "sy",
        "id",
        "wa",
        "st",
    ]

    m = re.match(filename_parser_regex, file_path.name)
    try:
        num_streams, dedup_ratio = [int(x) for x in m.groups()]
    except Exception:
        return None

    vmstat_data = pd.read_csv(
        file_path, sep=" ", header=None, names=vmstat_original_column_names
    )
    swapout_sum = vmstat_data["so"].sum()
    if vmstat_data["wa"].mean() != 0:
        # Unlikely that this warning really adds anything to the application.
        pass
    avg_cpu_usage = (
        vmstat_data["us"].mean() + vmstat_data["sy"].mean() + vmstat_data["wa"].mean()
    )
    return swapout_sum, avg_cpu_usage, num_streams, dedup_ratio


def get_vmstat_data(data_dir, appliance_name="eagappflx019", task="backup"):
    vm_df = pd.DataFrame(
        columns=["swapout", "cpu_usage_pct", "num_streams", "dedup_ratio"]
    )

    for file_path in data_dir.iterdir():
        res = read_vmstat_detail_file(file_path, appliance_name, task)
        if res is not None:
            swapout_sum, avg_cpu_usage, num_streams, dedup_ratio = res
            vm_df = pd.concat(
                [
                    vm_df,
                    pd.DataFrame(
                        {
                            "swapout": [swapout_sum],
                            "cpu_usage_pct": [avg_cpu_usage],
                            "num_streams": [num_streams],
                            "dedup_ratio": [dedup_ratio],
                        }
                    ),
                ],
                ignore_index=True,
                sort=True,
            )
    for col_name in vm_df.columns:
        vm_df[col_name] = pd.to_numeric(vm_df[col_name])

    return vm_df.sort_values(["num_streams", "dedup_ratio"])


def train_cpu_model(
    data_dir,
    data_appliance,
    appliance,
    site_version,
    task,
    workload,
    cpu_model_path,
    conn,
):
    df = get_cpu_data(data_dir, task, workload, data_appliance)

    if "swapout" in df:
        formula = (
            "cpu_usage_secs ~ kb_transferred + kb_transferred:dedup_ratio + swapout - 1"
        )
        converter_matrix = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 1]])
        constant_names = ["write_cpu_non_dup", "write_cpu_dup", "swap_cpu"]
    else:
        formula = "cpu_usage_secs ~ kb_transferred + kb_transferred:dedup_ratio - 1"
        converter_matrix = np.array([[1, 1], [1, 0], [0, 1]])
        constant_names = ["write_cpu_non_dup", "write_cpu_dup"]

    model = smf.ols(
        formula=formula,
        data=df,
    )
    results = model.fit()
    results.save(str(cpu_model_path))

    beta_hat = results.params.values
    c_hat = converter_matrix.dot(beta_hat)

    for constant_name, constant_value in zip(constant_names, list(c_hat)):
        conn.execute(
            f"""insert into constants_table (appliance, site_version,
                                                task, workload, name, value)
                values ('{appliance}',
                        '{site_version}',
                        '{task}',
                        '{workload}',
                        '{constant_name}',
                        {constant_value}
                )
            """
        )

        conn.commit()

    return


# This function is used by the memory_model_validation notebook
def _get_memory_data(data_dir):
    return pd.read_csv(data_dir / "run_set.csv")


def _memory_overhead(appliance_model, df):
    # A "+" in top output means "* 10"
    plus_factor = 1
    if appliance_model in ["5240", "5250", "5340", "5350", "5350-FLEX"]:
        plus_factor = 10

    return int(
        (
            df["used_mem"]
            - (df["spad_mem_fraction"]) * df["total_mem"] * plus_factor
            - (df["spoold_mem_fraction"]) * df["total_mem"] * plus_factor
        ).min()
    )


def train_memory_model(
    data_dir: pathlib.Path,
    data_appliance,
    appliance,
    site_version,
    task,
    workload,
    memory_model_path,
    conn,
):
    datafile = data_dir / "run_set.csv"
    if not datafile.exists():
        return
    df = pd.read_csv(datafile)
    memory_overhead_non_msdp = _memory_overhead(data_appliance, df)

    if "vmware" not in workload:
        constant_df = pd.DataFrame({"num_streams": [1, 2], "y": [300_000, 600_000]})
    elif workload == "vmware":
        # Current guess is 2GB additional memory usage per stream.
        constant_df = pd.DataFrame({"num_streams": [1, 2], "y": [2_300_000, 4_600_000]})

    model = smf.ols(formula="y ~ num_streams - 1", data=constant_df)
    results = model.fit()
    results.save(str(memory_model_path))

    beta_hat = results.params.values

    conn.execute(
        f"""insert into constants_table (appliance, site_version, task,
                                         workload, name, value)
            values ('{appliance}',
                    '{site_version}',
                    '{task}',
                    '{workload}',
                    'memory_overhead_non_msdp',
                    {memory_overhead_non_msdp}
            )
        """
    )

    conn.execute(
        f"""insert into constants_table (appliance, site_version, task,
                                         workload, name, value)
            values ('{appliance}',
                    '{site_version}',
                    '{task}',
                    '{workload}',
                    'memory_overhead_per_stream',
                    {beta_hat[0]}
            )
        """
    )

    conn.commit()

    return


if __name__ == "__main__":
    main()
