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

import collections
import string
import sys

from hypothesis import event, given, settings, Verbosity
import hypothesis.strategies as st
import pytest

from use_core import appliance
from use_core import constants
from use_core import media_packing, packing
from use_core import run_info
from use_core import task
from use_core import utils

import helper_xl as helper

try:
    import xlwings as xw

    from use_xl import connection
    import end_to_end_support as etes
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)

MAX_CLIENTS = 2000
MAX_WORKLOADS = 50
MAX_RETENTION_YEARS = 10
NUM_SITES = 5
NUM_DOMAINS = 2
MAX_FILES = 1_000_000
MAX_JOB_KBS = 2**32 - 1

ANY_WORKLOAD_NAME = st.text(alphabet=string.ascii_letters, min_size=2)

WORKLOAD_TYPES = [
    ("DB2", True),
    ("Exchange", False),
    ("File System", False),
    ("Image Files", False),
    ("NDMP", False),
    ("Notes", False),
    ("Oracle", True),
    ("SQL", True),
    ("SyBase", True),
    ("VMware", False),
]
ANY_WORKLOAD_TYPE = st.one_of([st.just(t) for t in WORKLOAD_TYPES])

ANY_NUMBER_OF_CLIENTS = st.integers(min_value=1, max_value=MAX_CLIENTS)

# The workload size column is always TiB, because that's what the
# column header says.  There's no provision for users to provide their
# own units.
ANY_SIZE = st.floats(min_value=0.1, max_value=1023)

ALL_SITES = set(f"Site {i+1}" for i in range(NUM_SITES))

ANY_DOMAIN = st.one_of([st.just(f"Domain-{i+1}") for i in range(NUM_DOMAINS)])

ANY_BACKUP_LOCATION = st.one_of(
    [st.just(t.lower()) for t in constants.BACKUP_LOCATIONS]
)

ANY_RATE = st.floats(min_value=0.0, max_value=1.0)

ANY_NUMBER_OF_DAYS = st.integers(min_value=0, max_value=365 * MAX_RETENTION_YEARS)
ANY_NUMBER_OF_WEEKS = st.integers(min_value=0, max_value=52 * MAX_RETENTION_YEARS)
ANY_NUMBER_OF_MONTHS = st.integers(min_value=0, max_value=12 * MAX_RETENTION_YEARS)
ANY_NUMBER_OF_YEARS = st.integers(min_value=0, max_value=MAX_RETENTION_YEARS)

ANY_BACKUP_LEVEL = st.just("cumulative") | st.just("differential")

ANY_LOG_BACKUP_INTERVAL = st.just(15) | st.just(30) | st.just(60)

ANY_NETWORK_TYPE = st.one_of([st.just(n) for n in appliance.NetworkType])

ANY_MIN_SIZE_DUP_JOBS = st.just(utils.Size.assume_unit(8, "GiB"))
ANY_MAX_SIZE_DUP_JOBS = st.just(utils.Size.assume_unit(100, "GiB"))

ANY_JOBS_PER_WEEK = st.integers(min_value=0, max_value=constants.HOURS_PER_WEEK)
VALID_JOBS_PER_WEEK = st.integers(min_value=1, max_value=constants.HOURS_PER_WEEK)

ANY_FILES = st.integers(min_value=1, max_value=MAX_FILES)
ANY_CHANNELS = st.just(0) | st.just(8)
ANY_FILES_PER_CHANNEL = st.integers(min_value=1)


@st.composite
def valid_backup_location(draw):
    site = draw(st.one_of([st.just(s) for s in ALL_SITES]))
    loc = draw(ANY_BACKUP_LOCATION)
    if "dr" in loc:
        remaining_sites = ALL_SITES - set([site])
        dr_dest = draw(st.one_of([st.just(s) for s in remaining_sites]))
    else:
        dr_dest = " "
    return (site, loc, dr_dest)


@st.composite
def valid_jobs_per_week(draw):
    all_jobs = draw(VALID_JOBS_PER_WEEK)
    fulls = draw(st.integers(min_value=0, max_value=all_jobs))
    incrs = all_jobs - fulls
    return (fulls, incrs)


@st.composite
def base_workload_input(draw):
    (workload_type, log_backup_capable) = draw(ANY_WORKLOAD_TYPE)

    w_src = {
        "name": draw(ANY_WORKLOAD_NAME),
        "domain": draw(ANY_DOMAIN),
        "type": workload_type,
        "client_dedup": draw(st.booleans()),
        "num_instances": draw(ANY_NUMBER_OF_CLIENTS),
        "fetb": draw(ANY_SIZE),
        "growth_rate": draw(ANY_RATE),
        "change_rate": draw(ANY_RATE),
        "retention_local_incr": draw(ANY_NUMBER_OF_DAYS),
        "retention_local_weekly": draw(ANY_NUMBER_OF_WEEKS),
        "retention_local_monthly": draw(ANY_NUMBER_OF_MONTHS),
        "retention_local_annually": draw(ANY_NUMBER_OF_YEARS),
        "retention_dr_incr": draw(ANY_NUMBER_OF_DAYS),
        "retention_cloud_incr": draw(ANY_NUMBER_OF_DAYS),
        "retention_dr_weekly": draw(ANY_NUMBER_OF_WEEKS),
        "retention_cloud_weekly": draw(ANY_NUMBER_OF_WEEKS),
        "retention_dr_monthly": draw(ANY_NUMBER_OF_MONTHS),
        "retention_cloud_monthly": draw(ANY_NUMBER_OF_MONTHS),
        "retention_dr_annually": draw(ANY_NUMBER_OF_YEARS),
        "retention_cloud_annually": draw(ANY_NUMBER_OF_YEARS),
        "initial_dedup": draw(ANY_RATE),
        "dedup": draw(ANY_RATE),
        "incremental_level": draw(ANY_BACKUP_LEVEL),
        "log_backup_capable": log_backup_capable,
        "log_backup_frequency": draw(ANY_LOG_BACKUP_INTERVAL),
        "front_end_nw": draw(ANY_NETWORK_TYPE),
        "min_size_dup_jobs": draw(ANY_MIN_SIZE_DUP_JOBS),
        "max_size_dup_jobs": draw(ANY_MAX_SIZE_DUP_JOBS),
        "force_small_dup_jobs": draw(st.integers()),
        "dr_nw": draw(ANY_NETWORK_TYPE),
        "files": draw(ANY_FILES),
        "channels": draw(ANY_CHANNELS),
        "files_per_channel": draw(ANY_FILES_PER_CHANNEL),
        "addl_full_dedup": draw(ANY_RATE),
        "incrementals_per_week": draw(ANY_JOBS_PER_WEEK),
        "fulls_per_week": draw(ANY_JOBS_PER_WEEK),
    }

    return w_src


@st.composite
def valid_workload_input(draw):
    w_src = draw(base_workload_input())
    (w_src["site"], w_src["backup_location"], w_src["dr_dest"]) = draw(
        valid_backup_location()
    )
    (w_src["fulls_per_week"], w_src["incrementals_per_week"]) = draw(
        valid_jobs_per_week()
    )
    return w_src


@st.composite
def valid_workload_list(draw):
    workloads = draw(
        st.lists(valid_workload_input(), min_size=1, max_size=MAX_WORKLOADS)
    )
    names = draw(
        st.lists(
            ANY_WORKLOAD_NAME,
            min_size=len(workloads),
            unique=True,
        )
    )
    sites = set()
    primary_counts = {}
    dr_counts = {}
    for w_name, w in zip(names, workloads):
        w["name"] = w_name
        sites.add(f"{w['domain']}/{w['site']}")
        if w["dr_dest"].strip():
            sites.add(f"{w['domain']}/{w['dr_dest'].strip()}")
            dr_counts[w_name] = w["num_instances"]
        primary_counts[w_name] = w["num_instances"]
    return workloads, sites, primary_counts, dr_counts


@st.composite
def any_timeframe(draw):
    num_years = draw(st.integers(min_value=1, max_value=15))
    planning_year = draw(st.integers(min_value=1, max_value=num_years))
    return utils.TimeFrame(planning_year=planning_year, num_years=num_years)


@st.composite
def any_scenario(draw):
    workloads, sites, primary_counts, dr_counts = draw(valid_workload_list())
    timeframe = draw(any_timeframe())
    should_flex = draw(st.booleans())

    return {
        "inputs": {
            "workloads": workloads,
            "timeframe": timeframe,
            "should_flex": should_flex,
        },
        "outputs": {
            "sites": sites,
            "primary_counts": primary_counts,
            "dr_counts": dr_counts,
        },
    }


@pytest.fixture(scope="session")
def the_book(excel_app):
    book = excel_app.books.open(fullname=etes.production_book_path())
    book.set_mock_caller()
    yield book
    # remove the mock caller because the book is going away.  No
    # reference to the book will be usable.
    del xw.Book._mock_caller
    book.close()


def report_events(workload_inputs, timeframe):
    total_clients = sum(w["num_instances"] for w in workload_inputs)
    event(f"total clients {helper.bracket(total_clients, 1000)}")
    event(f"num years {helper.bracket(timeframe.num_years, 5)}")


def validate_success(the_book, expectations):
    helper.assert_sites_in_result(
        the_book.sheets[connection.SITE_SUMMARY_SHEET],
        expectations["sites"],
    )
    (primary_counts, dr_counts) = helper.workload_assignments(
        the_book.sheets[connection.WORKLOAD_ASSIGNMENT_SHEET]
    )
    assert primary_counts == expectations["primary_counts"]
    assert dr_counts == expectations["dr_counts"]


def validate_failure(the_book, expectations, ex):
    if not isinstance(ex, media_packing.NotifyWorkloadError):
        return

    skipped = helper.workloads_skipped(
        the_book.sheets[connection.ERRORS_AND_NOTES_SHEET]
    )
    assert len(skipped) > 0

    (primary_counts, dr_counts) = helper.workload_assignments(
        the_book.sheets[connection.WORKLOAD_ASSIGNMENT_SHEET]
    )

    for wname in skipped:
        assert wname in expectations["primary_counts"]
        del expectations["primary_counts"][wname]
        if wname in expectations["dr_counts"]:
            del expectations["dr_counts"][wname]

    assert primary_counts == expectations["primary_counts"]
    assert dr_counts == expectations["dr_counts"]


@given(any_scenario())
@settings(deadline=None, verbosity=Verbosity.verbose)
def test_sizing(the_book, scenario):
    workload_inputs = scenario["inputs"]["workloads"]
    timeframe = scenario["inputs"]["timeframe"]
    should_flex = scenario["inputs"]["should_flex"]

    expectations = scenario["outputs"]

    workloads_sheet = the_book.sheets[connection.WORKLOADS_SHEET]
    slp_sheet = the_book.sheets[connection.STORAGE_LIFECYCLE_POLICIES_SHEET]

    helper.workload_to_excel(slp_sheet, workloads_sheet, workload_inputs)

    report_events(workload_inputs, timeframe)

    the_book.names["sizing_time_frame"].refers_to_range.value = timeframe.planning_year
    the_book.names["sizing_first_extension"].refers_to_range.value = timeframe.num_years

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)

    # What does this do?  Since the workloads are generated blind,
    # we can't predict whether any particular set of workloads can
    # be correctly sized.  So, this test checks only that either
    # the sizing succeeds, or fails with the "Unable to size
    # appliance" error.  Any other error is treated as a test
    # failure.  If the sizing succeeds, we then go ahead and
    # verify output sanity (all sites included, all workloads
    # assigned, etc.)

    try:
        connection.do_main(the_book, progress_reporting=False, sizing_flex=should_flex)
        validate_success(the_book, expectations)
    except Exception as ex:
        assert isinstance(
            ex,
            (
                media_packing.PackingError,
                packing.PackingError,
                media_packing.NotifyWorkloadError,
            ),
        )
        validate_failure(the_book, expectations, ex)


ANY_TASK = st.just("backup") | st.just("ma_cc") | st.just("ma_msdp_cc")
ANY_DUPLEX_TYPE = st.one_of([st.just(n) for n in task.TaskDuplexType])


@st.composite
def any_run_config(draw):
    dedup_ratio = draw(ANY_RATE)
    kb_xferred = draw(st.integers(min_value=1, max_value=MAX_JOB_KBS))
    num_streams = draw(st.integers(min_value=1, max_value=MAX_FILES))
    workload = draw(ANY_WORKLOAD_TYPE)[0]
    task = draw(ANY_TASK)
    io_duplex = draw(ANY_DUPLEX_TYPE)
    return appliance.RunConfig(
        dedup_ratio, kb_xferred, num_streams, workload, task, io_duplex
    )


ANY_SOFTWARE_VERSION = st.just(constants.DEFAULT_SOFTWARE_VERSION)
ANY_NUM_DRIVES = st.just(4) | st.just(8) | st.just(16)

ApplianceConfig = collections.namedtuple(
    "ApplianceConfig", "appliance site_version memory number_of_total_drives"
)


@st.composite
def any_appliance_memory(draw):
    appl_memories = set(
        (appl.model, appl.memory) for appl in appliance.Appliance.get_all_sku()
    )
    return draw(st.one_of([st.just(cfg) for cfg in sorted(appl_memories)]))


@st.composite
def any_appliance_config(draw):
    model, memory = draw(any_appliance_memory())
    software = draw(ANY_SOFTWARE_VERSION)
    num_drives = draw(ANY_NUM_DRIVES)
    return ApplianceConfig(
        appliance=model,
        site_version=software,
        memory=memory,
        number_of_total_drives=num_drives,
    )


@given(any_run_config(), any_appliance_config())
@settings(max_examples=1000, deadline=None)
def test_runinfo(rc, ap):
    ri = run_info.RunInfo(
        rc,
        ap,
        root_data_dir="src/main/python/conf/data",
        model_dir="src/main/python/conf/models",
    )
    cpu = ri.cpu_usage()
    assert isinstance(cpu, int)
    assert cpu >= 0

    mem_overhead = ri.memory_overhead()
    assert isinstance(mem_overhead, int)
    assert mem_overhead >= 0

    mem_usage = ri.memory_usage()
    assert isinstance(mem_usage, int)
    assert mem_usage >= 0

    net_usage = ri.network_usage()
    assert isinstance(net_usage, int)
    assert net_usage >= 0

    io_ops = ri.io_operations()
    assert isinstance(io_ops, int)
    assert io_ops >= 0
