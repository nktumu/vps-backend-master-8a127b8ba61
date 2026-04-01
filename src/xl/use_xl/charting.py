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

from mpl_toolkits.axisartist.parasite_axes import HostAxes, ParasiteAxes
import matplotlib

from use_core import constants

matplotlib.use("agg")  # needs to be before pyplot is imported
import matplotlib.pyplot as plt  # noqa: E402 (import not at top of file)

plt.rcParams.update({"figure.max_open_warning": 0})


def render_master_chart(mserver, last_year):
    years = list(range(1, 1 + last_year))
    capacities = [
        int(mserver.utilization.get("absolute_capacity", yr)) // (1024 * 1024)
        for yr in years
    ]
    jobs = [mserver.utilization.get("jobs/day", yr) for yr in years]
    planning_years = [str(y) for y in years]

    fig, axs = plt.subplots(1, 2, figsize=(28, 8), gridspec_kw={"wspace": 0.2})

    def plot_dim(ax, values, label):
        ax.plot(planning_years, values, label=label)
        ax.set_ylabel(label)
        ax.grid(True)

    plot_dim(axs[0], capacities, "Storage (GiB)")
    plot_dim(axs[1], jobs, "Jobs/day")

    return fig


def render_master_chart_single(mserver, last_year):
    years = list(range(1, 1 + last_year))
    capacities = [
        int(mserver.utilization.get("absolute_capacity", yr)) // (1024 * 1024)
        for yr in years
    ]
    jobs = [mserver.utilization.get("jobs/day", yr) for yr in years]
    planning_years = [y for y in years]

    fig = plt.figure()

    host = HostAxes(fig, [0.15, 0.1, 0.5, 0.8])

    host.set_title(f"{constants.MANAGEMENT_SERVER_DESIGNATION} Utilization")
    host.set_xlabel("Planning Year")

    par_jobs = ParasiteAxes(host, sharex=host)

    host.parasites.append(par_jobs)

    host.axis["right"].set_visible(False)

    par_jobs.axis["right"].set_visible(True)
    par_jobs.axis["right"].major_ticklabels.set_visible(True)
    par_jobs.axis["right"].label.set_visible(True)

    fig.add_axes(host)

    (stor_plot,) = host.plot(planning_years, capacities, label="Storage (GiB)")
    (jobs_plot,) = par_jobs.plot(planning_years, jobs, label="Jobs/day")

    for ax in [host, par_jobs]:
        ax.set_ylim(bottom=0.0)

    host.set_ylabel("Storage (GiB)")
    par_jobs.set_ylabel("Jobs/day")

    host.legend()
    host.grid(True, axis="x")

    host.axis["left"].label.set_color(stor_plot.get_color())
    par_jobs.axis["right"].label.set_color(jobs_plot.get_color())

    return fig


def render_master_resorce_usage_chart(mserver, last_year):

    years = list(range(1, 1 + last_year))
    cpu = [mserver.utilization.get("cpu", yr) * 100 for yr in years]
    memory = [mserver.utilization.get("memory", yr) * 100 for yr in years]
    i_o = [0 for yr in years]
    planning_years = [y for y in years]

    fig = plt.figure()

    host = HostAxes(fig, [0.15, 0.1, 0.5, 0.8])

    host.set_title(f"{constants.MANAGEMENT_SERVER_DESIGNATION} Resource Usage")
    host.set_xlabel("Planning Year")

    par_mem = ParasiteAxes(host, sharex=host)
    par_i_o = ParasiteAxes(host, sharex=host)

    host.parasites.append(par_mem)
    host.parasites.append(par_i_o)

    host.axis["right"].set_visible(False)

    par_mem.axis["right"].set_visible(False)
    par_mem.axis["right"].major_ticklabels.set_visible(False)
    par_mem.axis["right"].label.set_visible(False)

    fig.add_axes(host)

    host.plot(planning_years, cpu, label="CPU")
    par_mem.plot(planning_years, memory, label="Memory")
    par_i_o.plot(planning_years, i_o, label="I/O")

    for ax in [host, par_mem, par_i_o]:
        ax.set_ylim(0, 100)

    host.set_ylabel("Usage (%)")

    host.legend()
    host.grid(True, axis="x")

    return fig
