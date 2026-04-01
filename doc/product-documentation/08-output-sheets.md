# OUTPUT SHEETS {#output-sheets}

Clicking the _Sizing Results_ button on the [Sites](#sites-sheet)
sheet initiates the workload calculations based on the data from the
input and configuration sheets. The results are presented automatically
in the [Results](#results-sheet) sheet when the calculations are
completed. In addition, the data is presented in alternative formats
with varying levels of detail in a number of hidden sheets.

## Results {#results-sheet}

The _Results_ sheet is designed to give a high-level display of the
model and number of appliances assigned to each site. Workload
assignment details are not shown in this sheet.

If there are errors during sizing, a message summarizing the issues
will be shown on this sheet.  The [Errors And
Notes](#errors-and-notes-sheet) sheet will contain details.

The top of the sheet shows some basic configuration data. The _Package
Date_ is the release date of the version of USE you are using. _Sizer
Run At_ gives the date and time that the sizing results were
calculated.

Beneath the _Server Config_ sections are the appliance configurations.
The _Total_ column is the total number of appliances for each appliance
configuration. To the right of the _Total_ column is the list of sites
and the number of appliances of each appliance configuration that are
assigned to each site. Based on the site utilization, the color of the
site with the maximally utilized appliances will change. For example,
as capacity utilization gets higher the shade of yellow gets darker.

![Results of Appliances Sizing](images/results-sheet.png)

![Results of Flex Appliances Sizing](images/results-sheet-flex.png)

![Shaders Difference](images/shades-of-yellow.png)

The _Resource Utilization_ graph indicates the resource utilization of
the most heavily used appliance across the entire calculation. The
_Planning Horizon_ is shown as the vertical line over the _Planning
Year_ axis.

**Note: All of the appliance metrics are scaled to their actual
utilization, not to their maximum constraint settings from the
[Safety Considerations](#safety-considerations-sheet) sheet, and then
shown as a percentage of that actual utilization number.**

**Note: In Flex Appliances sizing the dark blue line that represents
the _Allocated Storage_ resource may appear to be flat across certain
years. This is a result of the best practice of preventing containers
from sharing the same LUN, so as to achieve better I/O performance.**

![](images/resource-utilization-chart.png)

To the right of the _Resource Utilization_ graph is the _Resource
Safety Margins_ table. The Resource Safety Margins table indicates the
maximum safety consideration for the appliances used in sizing. These
numbers are obtained from the
[Safety Consideration](#safety-considerations-sheet) sheet.

![](images/resource-safety-margins.png)

### Interpreting Results

#### Identifying Bottlenecks

If the sizer reports more appliances than expected, the following
process will help to figure out why.

1. Look at the chart on the [Results](#results-sheet) sheet and check
   which resource line is closest to the safety margin value. By
   default, for example, the sizer only uses 80% of the available
   storage capacity, so if the chart shows that the storage capacity
   is ~70% for the planning year, it is quite likely that this has
   caused the sizer to add additional appliances.
2. If none of the resources are hitting their limits at the planning
   year, it is possible that one of the software safety limits are
   being reached. To verify this, unhide the [Logs](#logs-sheet) tab
   and search for `"bottleneck"`. This may find several messages of the
   form "bottleneck value: workload WORKLOAD_NAME, dimension
   DIMENSION, window WINDOW, instances NUMBER". This message indicates
   that for the specified workload, many clients would fit on a single
   appliance if the mentioned dimension was the only one under
   consideration.

As an example, consider the messages:

  bottleneck value: workload DC_10_File System_A2, dimension capacity,
  window nowindow, instances 16
	bottleneck value: workload DC_10_File System_A2, dimension cpu,
  window WindowType.full, instances 1024

The above example means that for the workload `DC_10_File System_A2`,
1024 clients would fit on a single appliance if CPU usage was the only
thing under consideration. However, if storage capacity was the only
dimension under consideration, 16 clients would fit. The smallest of
these values are what the appliance is capable of since if any resource
hits its bottleneck, the sizer cannot add additional clients for the
workload to that appliance.

## Flex Scale Sizing Results {#flex-scale-results-sheet}

The _Flex Scale Sizing Results_ sheet is designed to give a high-level
display of the model, number of cluster, and cluster nodes assigned to
a site. Workload assignment details are not shown in this sheet.

Flex Scale sizing utilizes the following factors:

- Capacity: Storage required from the Flex Scale appliances to hold
  the backup data.  Backups that are taken more often, or are retained
  longer require more storage.
- Backup Throughput: Throughput (in TiB/hr) required from the Flex
  Scale appliances.  Each node in the Flex Scale cluster has a maximum
  backup throughput it can support.  Increasing number of workloads
  results in higher throughput demand from the cluster.
- Parallel Ops: Each Flex Scale node can support a limited number of
  parallel backup and Instant Access streams.  The suggested cluster
  sizes increase as the number of workloads increases.
- Network Bandwidth: Flex Scale appliances can be configured with a
  choice of network interfaces.  The effective network bandwidth
  provided by these interfaces will determine the size and number of
  clusters required to complete backups within the available backup
  window.

![Flex Scale Results](images/flexscale-results.png)

### Column Headings of Flex Scale Appliances Sizing
#### Capacity Calculations Table

This table lists the year-over-year overall performance and capacity
measures.

- **Total Capacity Required (TiB)**: Storage required to hold the
  backup data at the end of the year.
- **Total TiB/hr Required**: Throughput required for all backups
  during the year.
- **Total # Clusters**: Suggested number of Flex Scale clusters
  required.
- **# Nodes/cluster**: Suggested size of each Flex Scale cluster.
- **Driving factor(s) for #Nodes and #Clusters:**: Lists the metrics
  that are the primary driving factors for the suggested cluster size.

#### Sized Capacity Consumption Totals Table

This table lists attributes of total sized capacity:

- **Max Usable Capacity (usable * capacity threshold)**: The maximum
  usable capacity for the suggested Flex Scale configuration.
- **% of Available Capacity Used at End of Year**: Expected storage
  usage at the end of the year, expressed as a percentage of the total
  capacity of the Flex Scale configuration.

#### Assumptions (Customizable) Table

This table lists the limits and assumptions made by the Flex Scale
sizing.  These can be configured to better reflect specific customer
scenarios.

- **Maximum Capacity Threshold**: The limit of used storage at which a
  node or cluster is considered full.  The sizing process will not use
  more than this percentage of the available Flex Scale storage.
- **Maximum Throughput Threshold**: The limit of backup throughput at
  which a node or cluster is considered fully utilized.
- **Total # of Instant Access & parallel streams**: The number of
  Instant Access and parallel streams required by the scenario.
- **Public network connection speed**: Choice of network interface to
  use.  The network throughput supported by the Flex Scale clusters
  depends on this choice.
- **Maximum Network Throughput Threshold**: The limit of network
  bandwidth at which a node or cluster is considered fully utilized.
- **% Total Savings from Compression Alone**: Expected storage savings
  that can be attributed entirely to compression, if no deduplication
  were to happen.  For highly compressible data, this value should be
  increased.
- **% Common Data Within Same Workload Types**: Expected proportion of
  common data for the same workload type.  For example, OS disk images
  can expect to have a large proportion of common data.
- **Appliance Model**: Choice of Flex Scale appliance model to size
  with.

## Appliance Summary {#appliance-summary-sheet}

The _Appliance Summary_ sheet shows utilization of each appliance used
per year. Each appliance is grouped by its sites. Within each year,
the appliance utilization is broken down by the five different
appliance hardware metrics. Selecting the drop-down menu below the
_YEARS TO SHOW_ cell in column A will allow you to filter the output
by a specific year.  The values in each year column are as of the end
of the specified year, i.e, the _Year 1_ columns refer to the state at
the end of the first year of operation.

Based on the sizing with Appliances or Flex Appliances, the _Appliance
Summary_ sheet presents different headings and information
accordingly.

**Note: The values that have units in percentages are calculated to
their actual utilization, not to their maximum constraint settings from
the [Safety Considerations](#safety-considerations-sheet) sheet, and
then shown as a percentage of that actual utilization number.**

**Note: The _Allocated Capacity (TiB)_ values reported in Flex
Appliances sizing may appear to be the same across certain years. This
is a result of the best practice of preventing containers from sharing
the same LUN, to achieve better I/O performance.**

### Column Headings of Appliances Sizing

#### Media Server Table

This table lists attributes calculated per Media Server:

- **ID**: ID is a unique identifier per appliance configuration at a
  site
- **Capacity (TiB)**: Total disk capacity used
- **Capacity (%)**: The percentage of total disk capacity utilization
- **Allocated Capacity (TiB)**: Total allocated disk capacity
- **Allocated Capacity (%)**: The percentage of total allocated disk
  capacity utilization
- **Memory (%)**: The percentage of average memory utilization
- **CPU (%)**: The percentage of average CPU utilization
- **I/O (%)**: The percentage of average disk I/O utilization
- **Network (%)**: The percentage of average network utilization
- **DR-NW Transfer(Mbps)**: The network bandwidth usage between the
  appliance and a DR appliance
- **DR Transfer GiB/Week**: The network usage per week between the
  appliance and a DR appliance
- **Cloud-NW Transfer(Mbps)**: The network bandwidth usage between the
  appliance and a cloud provider
- **Cloud Transfer GiB/week**: The network usage per week between the
  appliance and a cloud provider.  The cloud provider will use this to
  calculate data transfer costs.
- **I/O (MB/s)**: Total disk I/O used
- **Full Backup (TiB)**: Total size of the full backups
- **Incremental Backup (TiB)**: Total size of the incremental backups
- **Size Before Deduplication (TiB)**: Total size of the backups before
  deduplication
- **Size After Deduplication (TiB)**: Total size of the backups before
  deduplication
- **Cloud Storage GiB-Months**: The total amount of data stored
  through the year.  This accounts for existing data being stored in
  the past year and the new data being added this year.  A cloud
  provider will use this to calculate storage costs.
- **Worst-case Cloud Storage GiB-Months**: The maximum space occupied
  by the cloud storage when using MSDP-C to send data to the cloud.

![](images/appliance-summary-table-1.png)

![](images/appliance-summary-table-2.png)

![](images/appliance-summary-table-3.png)

#### Primary Server Table

This table lists attributes calculated per Primary Server:

- **ID**: ID is a unique identifier per primary server of a domain at a
  site
- **Capacity (GiB)**: Total disk capacity used
- **CPU (%)**: The percentage of average CPU utilization
- **Memory (%)**: The percentage of average memory utilization
- **Files**: Total number of files
- **Images**: Total number of backup images
- **Jobs/day**: Number of jobs per day

![](images/appliance-summary-table-4.png)

#### Workload Table

This table lists attributes calculated per workload:

- **Capacity Workload (TiB)**: Total disk capacity usage for the
  workload
- **Replication (Mbps)**: The replication network bandwidth usage for
  the workload
- **Cloud Storage GiB-Months**: The total amount of data stored for the
  workload through the year. This accounts for existing data being
  stored in the past year and the new data being added this year. A
  cloud provider will use this to calculate storage costs
- **Worst-case Cloud Storage GiB-Months**: The maximum space occupied
  by the cloud storage when using MSDP-C to send data to the cloud.
- **Cloud Transfer GiB/week**: The network usage per week for the
  workload between appliance and a cloud provider. The cloud provider
  will use this to calculate data transfer costs
- **Catalog Size (GiB)**: Total catalog capacity usage for the workload

![](images/appliance-summary-table-5.png)

#### Access Appliance Table

This table lists attributes calculated per Access Appliance:

- **Capacity (TiB)**: Total disk capacity used
- **Capacity (%)**: The percentage of total disk capacity utilization

![](images/appliance-summary-nba-access.png)

### Column Headings of Flex Appliances Sizing

#### Flex Appliance Table

This table lists attributes calculated per Flex Appliance:

- **Appliance ID**: An identifier per appliance configuration at a site
- **Capacity (TiB)**: Total disk capacity used
- **Capacity (%)**: The percentage of total disk capacity utilization
- **Allocated Capacity (TiB)**: Total allocated disk capacity
- **Allocated Capacity (%)**: The percentage of total allocated disk
  capacity utilization
- **Memory (%)**: The percentage of average memory utilization
- **CPU (%)**: The percentage of average CPU utilization
- **I/O (%)**: The percentage of average disk I/O utilization
- **Network (%)**: The percentage of average network utilization
- **DR-NW Transfer(Mbps)**: The network bandwidth usage between an
  appliance and a DR appliance
- **DR Transfer GiB/Week**: The network usage per week between
  appliance and a DR appliance
- **Cloud-NW Transfer(Mbps)**: The network bandwidth usage between
  appliance and a cloud provider
- **Cloud Transfer GiB/week**: The network usage per week between
  appliance and a cloud provider.  The cloud provider will use this to
  calculate data transfer costs.
- **I/O (MB/s)**: Total disk I/O used
- **Full Backup (TiB)**: Total size of the full backups
- **Incremental Backup (TiB)**: Total size of the incremental backups
- **Size Before Deduplication (TiB)**: Total size of the backups before
  deduplication
- **Size After Deduplication (TiB)**: Total size of the backups before
  deduplication
- **Cloud Storage GiB-Months**: The total amount of data stored through
  the year.  This accounts for existing data being stored in the past
  year and the new data being added this year. A cloud provider will
  use this to calculate storage costs.
- **Worst-case Cloud Storage GiB-Months**: The maximum space occupied
  by the cloud storage when using MSDP-C to send data to the cloud.

![](images/appliance-summary-flex-table-1.png)

![](images/appliance-summary-flex-table-2.png)

![](images/appliance-summary-flex-table-3.png)

#### Container Table

This table lists attributes calculated per container:

- **Appliance ID**: An identifier per appliance configuration at a site
- **Capacity (TiB)**: Total disk capacity used

![](images/appliance-summary-flex-table-4.png)

#### Workload Table

This table lists attributes calculated per workload:

- **Capacity Workload (TiB)**: Total disk capacity usage for the
  workload
- **Replication (Mbps)**: The replication network bandwidth usage for
  the workload
- **Cloud Storage GiB-Months**: The total amount of data stored for the
  workload through the year. This accounts for existing data being
  stored in the past year and the new data being added this year. A
  cloud provider will use this to calculate storage costs
- **Worst-case Cloud Storage GiB-Months**: The maximum space occupied
  by the cloud storage when using MSDP-C to send data to the cloud.
- **Cloud Transfer GiB/week**: The network usage per week for the
  workload between an appliance and a cloud provider. The cloud
  provider will use this to calculate data transfer costs
- **Catalog Size (GiB)**: Total catalog capacity usage for the workload

![](images/appliance-summary-flex-table-5.png)

#### Access Appliance Table

This table lists attributes calculated per Access Appliance:

- **Capacity (TiB)**: Total disk capacity used
- **Capacity (%)**: The percentage of total disk capacity utilization

![](images/appliance-summary-flex-access.png)

## Primary Server Summary {#primary-server-summary-sheet}

The _Primary Server Summary_ sheet presents the _Primary Server
Utilization_ and _Primary Server Resource Usage_ charts.

The _Primary Server Utilization_ chart shows the _Storage (GiB)_ and
_Jobs/day_ usage of a NetBackup Primary server over the planning years.

The _Primary Server Resource Usage_ chart shows the _CPU_, _Memory_,
and _I/O_ usage of a NetBackup Primary server over the planning years.

![](images/documentation-primary-server-summary-sheet.png)

## Workload Assignments {#workload-assignments-sheet}

The _Workload Assignments_ sheet shows the assignment of the workloads
to appliances, grouped by domain, site, Primary Server Appliance, and
Media Server Appliance within a domain. This sheet helps to visualize
how each site is populated by appliances and how each appliance is
populated by workloads.

![](images/workload-assignments-sheet.png)

## Workload Assignments Flex {#workload-assignments-flex-sheet}

The _Workload Assignments Flex_ sheet shows the assignment of the
workloads to appliances, grouped by site, appliance, domain, and
container within a site. This sheet helps to visualize how each site is
populated by appliances and how each appliance is populated by
workloads.

![](images/workload-assignments-flex-sheet.png)

## Workload Assignment Details {#workload-assignment-details-sheet}

The _Workload Assignment Details_ sheet shows the assignment of the
workloads to appliances without grouping. This sheet is the raw data
output of the appliances and workload assignments. This data can be
used for customizing the visualization of the workload assignments by
reorganizing, sorting and filtering columns, creating charts, creating
pivot tables, etc..

Below the assignment of workloads is the _Workload Disk Usage By Year
(TB)_ table that shows each workload capacity at the primary or DR site
year by year.

![](images/workload-assignment-details-sheet.png)

## Workload Assign Details Flex {#workload-assign-details-flex-sheet}

The _Workload Assign Details Flex_ sheet shows the assignment of the
workloads to appliances without grouping. This sheet is the raw data
output of the containers and workload assignments. This data can be
used for customizing the visualization of the workload assignments by
reorganizing, sorting and filtering columns, creating charts, creating
pivot tables, etc..

Below the assignment of workloads is the _Workload Disk Usage By Year
(TB)_ table that shows each workload capacity at the primary or DR site
year by year.

![](images/workload-assignment-details-flex-sheet.png)

## Errors And Notes {#errors-and-notes-sheet}

The sizer may skip some workloads if there is no way to fit them on
the selected appliances.  If all of the workloads have to be skipped
this way, the sizing as a whole will fail.

![Workloads Skipped](images/results-workloads-skipped.png)

When workloads are skipped, the _Errors And Notes_ sheet will contain
a list of skipped workloads, along with the reason why the workloads
were skipped.

![Example Error](images/media-server-misfit.png)

The possible error types are:

- **Media Server Misfit**: The identified workload was skipped for
  media server sizing.  The sized appliances do not take the media
  server requirements for this workload into account.  This error
  means that a single client of the indicated workload is too big for
  an appliance.  It indicates that the number of clients might be too
  small, or the FETB value might be too large.
- **Primary Server Misfit**: The identified workload was skipped for
  primary server sizing.  The sized appliances do not take the primary
  server requirements for this workload into account.  The media
  server requirements may still be taken into account, unless there is
  an entry on this sheet specifically indicating otherwise.  This
  error can be resolved by splitting the workload into multiple
  workloads and distributing the clients across those workloads.
- **Workload Domain Change**: The indicated workload has had its
  domain changed.  This will happen if the sizer determines that a
  single primary server is not sufficient for the domain.  In this
  case, one or more workloads will have their domain changed so that
  they can be allocated to different primary servers.  The _Domain_
  column will show the new domain for the workload.
