# INPUT SHEETS

## Appliance Definitions {#appliance-definitions-sheet}

The _Appliance Definitions_ sheet contains a filterable list of
available appliance configurations. The _Appliance Configuration_
column on the _Site_ sheet will only consider the filtered rows from
the _Appliance Definitions_ sheet. The list can be filtered by the
appliance model and a number of other appliance characteristics.

![](images/appliance-definitions-sheet.png)

The _Name_ column contains a descriptive name for the selected
appliance. The rest of the columns can be used to filter the list of
appliances used in the calculations based on the following
configuration options:

- **Model**: Appliance model.
- **Shelves**: Number of external storage shelves.
- **Calculated Capacity**: Includes internal storage as well as
  storage contained in the external storage shelves.
- **Memory**: Memory contained in the compute node.
- **IO Configuration**: Appliance network configuration class.
- **1GbE**: Number of 1GbE copper network adapters. This number
  includes on-board and any added 1GbE copper network adapters.
- **10GbE Copper**: Number of 10GbE copper network adapters.
- **10GbE SFP**: Number of 10GbE SFP adapters.
- **8Gb FC**: Number of 8Gb fibre channel adapters.
- **16Gb FC**: Number of 16Gb fibre channel adapters.

## Storage Lifecycle Policies {#storage-lifecycle-policies-sheet}

The _Storage Lifecycle Policies_ (SLP) sheet contains the storage
lifecycle characteristics assigned to the customer workloads. Before
defining customer workloads, the SLPs must be defined so that they can
be assigned to the workloads.

SLPs in USE are similar to SLPs in NetBackup that they are unique
containers of storage and replication characteristics that can
be assigned to one or more unique workload entities. The workloads to
which the SLPs are assigned then inherit all of the SLP
characteristics.

![](images/slp-sheet-1.png)

![](images/slp-sheet-2.png)

To add a storage lifecycle policy, follow one of the following steps:
- Click the _New SLP_ button. Doing so inserts a new storage lifecycle
  policy row at the end of the table, or
- Copy a current SLP row by clicking the _Copy SLP_ button. Doing so
  inserts a copied storage lifecycle policy at the end of the table.

To add multiple policies, follow one of the following steps:
- Click the _Add Multiple SLPs_ button and specify the number of
  policies required, or
- Select multiple rows by highlighting the row numbers and clicking the
  _Add Multiple SLPs_ button.

To delete a policy, ensure at least one cell on that row is highlighted
and press the _Delete SLP_ button located on the header row.

**Note: Do not try to enter a new policy manually or try to copy and
paste a row manually, Utilize the _New SLP_, _Copy SLP_, or _Add
Multiple SLPs_ buttons to add policies. Manually entering a policy can
result in the required data cells in hidden columns being left empty,
which will cause errors during sizing calculation.**

You can change the sizing time frame by clicking the
[Settings](#settings-sheet) button.  This takes you to the _Settings_
sheet where this, and other aspects of sizer operation can be changed.

The _Storage Lifecycle Policy_ column is the name assigned to the SLP.
This column will appear in a drop-down list in the _Workloads_ sheet to
assign a SLP to a workload. When defining a new SLP, make sure the SLP
name is unique.

The _Domain_ column defines the name of a NetBackup Domain. If this
cell is being left in empty, then "Domain-X" will be used in the case
of absent.

The _Site_ column defines the local site or location of the workload.
This could be a country, city, data center, closet, rack location, or
cluster node. From USE’s point of view, a site is the local storage
entity of the workload.

The _DR-dest_ (also referred to as a Disaster Recovery (DR) destination
or DR Site) column defines the replication target site or location of
the workload for the purposes of disaster recovery. This could be a
country, city, data center, closet, rack location, or cluster node.
From USE’s point of view, _DR-dest_ is the DR replication target
storage entity of the workload.

The _Backup Image Location_ column defines how the workload is
protected through local backups and retention, disaster recovery
replication and retention, and long-term replication and retention.
This column is a pre-defined drop-down list. The option you choose will
define which of the other columns in this row will be used by the SLP.
Columns that will not be used will be grayed-out. Even if a grayed-out
cell contains a value, it will not be used in the calculation. Each
option is detailed in the following list:

- **Local Only**: The workload will be backed up locally and will use
  the local retention settings. The workload calculation will use the
  _Site_ column as the only storage location of the workload. The
  _DR-dest_ column, _DR retention_ columns, and _cloud retention_
  columns will all be grayed-out for this SLP.
 
- **Local+DR**: The workload will be backed up locally and will use
  the local retention settings. The workload will also be replicated
  to a DR site and will use the _DR retention_ settings. The workload
  calculation will use the _Site_ column as the local storage location
  of the workload and the _DR-dest_ column as the DR storage location
  of the workload. The _cloud retention_ columns will all be
  grayed-out for this SLP.
 
- **Local+LTR**: The workload will be backed up locally and will use
  the _local retention_ settings. The workload will also be replicated
  to a long-term retention site using Cloud Catalyst or MSDP-Cloud and
  will use the _cloud retention_ settings. The workload calculation
  will use the _Site_ column as the local storage location of the
  workload. The long-term retention site is considered to be a single
  cloud service target and does not require a column. The _DR-dest_
  column and the _DR retention_ columns will all be grayed-out for this
  SLP.

- **Local+DR+LTR**: The workload will be backed up locally and will
  use the _local retention_ settings. The workload will also be
  replicated to a DR site and will use the _DR retention_
  settings. The workload will also be replicated to a long-term
  retention site using Cloud Catalyst or MSDP-Cloud and will use the
  _cloud retention_ settings. The workload calculation will use the
  _Site_ column as the local storage location of the workload and the
  _DR-dest_ column as the DR storage location of the workload. The
  long-term retention site is considered to be a single cloud service
  target and does not require a column. All columns are used for this
  SLP.

- **LTR Only**: The workload will be backed up to a local cache but
  will not use _local retention_ settings. The workload will be
  replicated to a long-term retention site using Cloud Catalyst or
  MSDP-Cloud and will use the _cloud retention_ settings. The workload
  calculation will use the Site column as the local cache storage
  location of the workload. The long-term retention site is considered
  to be a single cloud service target and does not require a column.
  The _DR-dest_ column, _local retention_ columns, and the _DR
  retention_ columns will all be grayed-out for this SLP.

The _retention_ columns define how long the backup images are retained
locally, at the DR replication site, and in the cloud container. Each
retention column is detailed in the following list:

- **Incremental Retention (days) - Local**: Number of days local
  incremental backups are retained on local storage
- **Weekly Full Retention (weeks) - Local**: Number of local weekly
  full backups retained on local storage
- **Monthly Full Retention (months) - Local**: Number of local monthly
  full backups retained on local storage
- **Incremental Retention (days) - DR**: Number of days replicated
  incremental backups are retained on DR replication target storage
- **Weekly Full Retention (weeks) - DR**: Number of replicated weekly
  full backups retained on DR replication target storage
- **Monthly Full Retention (months) - DR**: Number of replicated
  monthly full backups retained on DR replication target storage
- **Incremental Retention (days) - Cloud**: Number of days
  replicated incremental backups are retained on cloud replication
  target storage
- **Weekly Full Retention (weeks) - Cloud**: Number of replicated
  weekly full backups retained on cloud replication target storage
- **Monthly Full Retention (months) - Cloud**: Number of replicated
  monthly full backups retained on cloud replication target storage

The sizer currently asks for separate retention values for weekly full
backups, monthly full backups, and annual full backups. These full
backups values are then used by the sizer to calculate the **effective
number** of backup images that exist at a time. **Note: The effective
number of backup images is equal to the sum across all these retention
values, with adjustments to avoid double-counting. Such double-counting
can occur, for example, when the retention values of both weekly full
backups and monthly full backups are specified, in which case, one
backup image is double-counted and has to be removed.**

In effect, these retention values could be used to specify an arbitrary
number of backup images being retained at a time. If a user wished to
specify certain retention, say 30 days, for daily full backups, this
could be done by specifying a value indicating the number of full
backups in one of the existing retention columns, for example, by
putting 30 in the weekly full retention column.

**Special note on Automatic Schedules:** Protection Plans introduced a
simplified scheduling mechanism referred to as an Automatic Schedule.
An Automatic Schedule automatically creates full and incremental backup
windows by just specifying the backup frequency, data retention and
start window. It is important to understand that the automatically
created incremental backups will be the same retention as the full
backups. For example, if you specified 2 months as the retention in the
Automatic Schedule, the incremental backups will be kept for 2 months
which means that 60 incremental backup images will be kept.

The _Number of Full Backups per Week_ column indicates the total number
of full backups taken of the workload over a seven-day period. This
number is not necessarily limited to one full backup per day. For
example, if there will be a full backup of the workload taken twice a
day, this number will be 14. If there will be one full backup of the
workload per week, this number will be 1.

The _Number of Incremental Backups per Week_ column indicates the total
number of incremental backups taken of the workload over a seven-day
period. This number is not necessarily limited to one incremental
backup per day. For example, if a workload has an incremental backup
job that is running once per day, the number of this field will be 7.
If a workload has an incremental backup job that is running twice per
day, the number of this field will be 14.

The _Incremental Backup Level (differential or cumulative)_ column
indicates whether the incremental backups of the workload will be
cumulative or differential. Cumulative incremental backups include all
changes since the last full backup. Differential incremental backups
include all changes since the last incremental or full backup.

The _Log Backup Frequency (minutes between)_ column indicates the
number of minutes between transaction log backups and only applies to
database workloads. The calculations take into account the total size
of the workload and the daily change rate to determine how big the
transaction log backups will be.

The _Appliance Front-End Network_ column indicates the network
connectivity used by the appliance for the workload backups. The
appliance front-end network will be used to determine the required
network configuration of the appliance to which the workload’s client
backup traffic will be assigned. The appliance front-end network will
also determine the available network throughput for the workload
backups. If the default option of auto is selected, the calculations
will use the best available network interface for the chosen appliance
model.

The _Minimum size per duplication job_ column indicates the smallest
batch size that can run as a single duplication job. For example, if
the minimum size per duplication is set to 1 TiB, when the workload
reaches that 1 TiB threshold the workload will be replicated. The
minimum size for this attribute is 1 kilobyte with no maximum. (hidden
column)

The _Maximum size per duplication job_ column indicates the
biggest batch size that can run as a single duplication job. For
example, if the maximum size per duplication is set to 5 TiB, when the
workload reaches that threshold the workload will be replicated.
(hidden column)

The _Force Interval for small jobs_ column indicates the maximum time
the workload job is held before replication. For example, if the force
interval is set to 30 minutes, that workload job will be replicated
every 30 minutes. The force interval number default is set to 30
minutes. (hidden column)

The _Appliance DR Network_ column indicates the network connectivity
used by the appliance for DR replication. The appliance DR network will
be used to determine the required network configuration of the
appliance to which the workload’s DR replication will be assigned. The
appliance DR network will also determine the available network
throughput for the workload DR replication. If the default option of
auto is selected, the calculations will use the best available network
interface for the chosen appliance model.

The _Appliance LTR Network_ column indicates the network connectivity
used by the appliance for Cloud Catalyst or MSDP-Cloud replication. The
appliance LTR network will be used to determine the required network
configuration of the appliance to which the workload’s Cloud Catalyst
or MSDP-Cloud traffic will be assigned. The appliance LTR network will
also determine the available network throughput for the workload Cloud
Catalyst or MSDP-Cloud replication. If the default option of auto is
selected, the calculations will use the best available network
interface for the chosen appliance model.

The _Log Backup Incremental Level (differential or cumulative)_ column
is not currently being used.

## Workloads {#workloads-sheet}

The _Workloads_ sheet contains the customer workloads and their
corresponding storage characteristics. Each line on the _Workloads_
sheet represents a separate workload. The storage characteristics come
from the storage lifecycle policy (SLP) that has been created on the
[Storage Lifecycle Policies](#storage-lifecycle-policies-sheet) sheet.

If part of a workload has a unique characteristic, that workload
should be split into two different workloads. For example, if a VMware
workload is 1000 clients; is all within a single site; has the same
growth and change rates; has the same retention rates; but only 5 of
those clients need to be replicated to the cloud, the workload should
be split into two different workloads, each one having their own
storage lifecycle policy.

![](images/workloads-sheet.png)

To add a workload, follow one of the following steps:
- Click the _New Workload_ button. Doing so inserts a new workload row
  at the end of the table, or
- Copy a current workload row by clicking the _Copy Workload_ button.
  Doing so inserts a copied workload at the end of the table.

To add multiple workloads, follow one of the following steps:
- Click the _Add Multiple Workloads_ button and specify the number of
  workloads required, or
- Select multiple rows by highlighting the row numbers and clicking the
  _Add Multiple Workloads_ button.

To delete a workload, ensure at least one cell on that row is
highlighted and press the _Delete Workload_ button located on the
header row.

**Note: Do not try to enter a new workload manually or try to copy and
paste a row manually. Utilize the _New Workload_, _Copy Workload_, or
_Add Multiple Workloads_ buttons to add workloads. Manually entering a
workload can result in the required data cells in hidden columns being
left empty, which will cause errors during sizing calculation.**

To import workloads and storage lifecycle policies from another sheet
or from a sheet in a different workbook, click the _Import Workload_
button at the top of the _Workloads_ sheet. Locate the USE workbook
Excel file from the File Navigation window, select it, then click Open.
The first dialog will ask for the name of the sheet that contains the
workloads to be imported. The default name is _Workloads_. The second
dialog will ask for the name of the sheet that contains the storage
lifecycle policies that contain the policies to be imported.
The default sheet name is _Storage Lifecycle Policies_. Enter the name
of the import source sheet exactly how it appears in the workbook.
After the import, check to ensure that there is no duplicated storage
lifecycle policy name in your
[Storage Lifecycle Policies](#storage-lifecycle-policies-sheet) sheet.

USE 3.0 introduced a new feature to import workloads from NetBackup's
NBDeployUtil itemization output and convert them into workloads in
the _Workloads_ sheet. To import NBDeployUtil itemization output, click
the _Import NBDeployUtil_ button at the top of the _Workloads_ sheet,
locate the NBDeployUtil report workbook Excel file from the File
Navigation window, select it, then click Open.

**Note: The NBDeployUtil report contains no information about storage
lifecycle policy.  Workloads imported from the NBDeployUtil
itemization outputs are assigned a policy from the _Storage Lifecycle
Policies_ sheet.  The import process will ask the user to specify the
name of a policy that the imported workloads should be associated
with.  If the named policy does not exist already, it will be created
with default values and the workloads will be associated with that
policy.  The attributes of this policy can then be updated on the
_Storage Lifecycle Policies_ sheet.**

The _Workload Name_ column indicates the name of the workload. The
name, which is derived from the workload options, is automatically
generated. It is created using the information in the worksheet
columns that are described below.

  Example: Site_Number of Clients_Workload Type_Cell Number
	DC_2_VMware_A2

**Note: If a cell value of "#N/A" or "#REF!" is showing under the
_Workload Name_ column of a row, make sure a Storage Lifecycle Policy
exists in the _Storage Lifecycle Polices_ sheet that matches the policy
name under the _Storage Lifecycle Policy_ column of the row in the
_Workloads_ sheet.**

The _Workload Type_ column indicates the workload type that is
associated with this workload. It is chosen from a drop-down list that
contains a predefined list of workload types. Available options are:

- **DB2** (IBM DB2)
- **Exchange** (Microsoft Exchange Server)
- **File System (Large Files)** (generic large size files on the local
  file system of a file server)
- **File System (Small Files)** (generic small size files on the local
  file system of a file server)
- **File System (Typical)** (generic typical size files on the local
  file system of a file server)
- **Image Files** (optimized for image files such as .JPG, .TIFF, .BMP,
  etc.)
- **Informix-On-Bar** (IBM Informix database)
- **MySQL** (Oracle MySQL database)
- **NCR-Teradata** (Teradata database)
- **NDMP (Large Files)** (Network Data Management Protocol / NAS
  consists of large size files)
- **NDMP (Small Files)** (Network Data Management Protocol / NAS
  consists of small size files)
- **NDMP (Typical)** (Network Data Management Protocol / NAS consists
  of typical size files)
- **Notes** (IBM Notes)
- **Oracle** (Oracle database)
- **Oracle-TDE** (Oracle database with Transparent Data Encryption)
- **PostgreSQL** (PostgreSQL database)
- **SAP** (SAP database)
- **SharePoint** (Microsoft SharePoint Server)
- **SQL** (Microsoft SQL Server)
- **SQL-TDE** (Microsoft SQL Server with Transparent Data Encryption)
- **Splunk** (Splunk software)
- **Sybase** (SAP Sybase database)
- **VMware** (VMware virtual machines)

**Note: See the table below for NBDeployUtil policy types that do not
map to the USE workload types directly.**

+-------------------------------+-------------------------------+
|NBDeployUtil Policy Type       |USE Workload Type              |
+===============================+===============================+
|File System                    |File System (Typical)          |
+-------------------------------+-------------------------------+
|FlashBackup-Windows            |File System (Typical)          |
+-------------------------------+-------------------------------+
|Lotus-Notes                    |Notes                          |
+-------------------------------+-------------------------------+
|MS-Exchange-Server             |Exchange                       |
+-------------------------------+-------------------------------+
|MS-SQL-Server                  |SQL                            |
+-------------------------------+-------------------------------+
|MS-Windows                     |File System (Typical)          |
+-------------------------------+-------------------------------+
|MS-Windows-NT                  |File System (Typical)          |
+-------------------------------+-------------------------------+
|NDMP                           |NDMP (Typical)                 |
+-------------------------------+-------------------------------+
|Standard                       |File System (Typical)          |
+-------------------------------+-------------------------------+

The _Number of Clients_ column indicates the number of clients
represented in this workload. If the workload type is VMware, this
number will represent the total number of virtual machines even though
there may be only one VMware vCenter server. If the workload type is
any other workload type, this number will represent each installed
client.

The _FETB (TiB)_ column indicates the total amount of front-end
terabytes of the workload. This represents the production data only
and does not include backup data. Enter this value as _tebibytes
(TiB)_, not _terabytes (TB)_.

The _Storage Lifecycle Policy_ column indicates the storage lifecycle
policy that is assigned to this workload. The data from the policy will
be used during sizing of this workload. To change the assigned policy
of this workload, click the drop-down list in the _Storage Lifecycle
Policy_ column and choose one policy from the list of SLPs. The data
derived from the selected SLP will be automatically updated when a new
SLP is chosen.

The _Workload Isolation_ column indicates that the workload should be
placed on a dedicated appliance, which will not be shared with other
workloads.

<!-- Uncomment below when Universal Share is ready
The _Universal Share?_ column indicates that the workload is backed up
through the Universal Share.
-->

The _Annual Growth Rate (%)_ column indicates the anticipated
year-over-year growth rate percentage of the workload. This column
will be populated with a default value that is common to the workload
type, but should be updated to reflect the customer’s environment.

The _Daily Change Rate (%)_ column indicates the anticipated daily data
change rate percentage of the workload. This column will be populated
with a default value that is common to the selected workload type, and
should be updated to reflect the actual customer’s environment.

The rest of the columns in the _Workloads_ sheet are populated from the
common workload characteristic data in the _Default Workload
Attributes_ sheet based on the selected workload type under the
_Workload Type_ column of this workload. It is possible to enter these
values directly and override the derived value from the selected
workload type, but this should only be done if that value is truly
unique to the workload. Once a value is overridden, it will no longer
be updated when changing the workload type. The definitions of the
columns updated by the default workload attributes can be found in
[Default Workload Attributes](#default-workload-attributes-sheet).

## Sites {#sites-sheet}

The Sites sheet contains the sites that were defined under _Site_ and
_DR-dest_ columns in the [Storage Lifecycle
Policies](#storage-lifecycle-policies-sheet) sheet. The site entries
are automatically generated from values under _Site_ and _DR-dest_
columns in the _Storage Lifecycle Policies_ sheet.

**Note: No site should be manually added into this sheet.**

Each site can be customized in three ways. The first is to
accept the default values without making any modification.

The second option is to select an appliance configuration from the
drop-down menu of the _Appliance Configuration_ column. In the
_Appliance Configuration_ column, the drop-down menu has a list of
available appliances.

![](images/sites-sheet.png)

The third option is to configure four columns: the Appliance
Model; Site Network Type; WAN Network Type; and CC Network Type.

_Appliance Configuration_, _Appliance Model_, _Site Network Type_, _WAN
Network Type_, and _CC Network Type_ fields are all optional fields and
depend on customer needs. If _Site Network Type_, _WAN Network
Type_, and _CC network Type_ are left blank, USE will choose the
default configuration of 10GbE SFP. **Note: If the _Appliance
Configuration_ or Appliance Model_ fields are left blank, USE will
choose an appropriate appliance using heuristics.**

- If the site is not a DR destination and the total disk capacity
  requirements can be satisfied by a single 5150, a 5150 is
  chosen
- If the site is a DR destination, the 5150 is excluded. Only
  5240/5250/5340 models are considered eligible for the DR site

After the model is decided, the specific configuration for the model
is selected by calculating the disk capacity requirements for the
workloads. If an appliance configuration exists that can cover all of
the workloads, that configuration is chosen. Otherwise, the sizer will
pick a configuration with the largest usable disk capacity, so that
the overall number of appliances is minimized.

**Note: If an appliance configuration is selected from the _Appliance
Configuration_ drop-down menu for a site, the selected appliance
configuration will override any selections that have been made for
_Appliance Model_, _Site Network Type_, _WAN Network Type_, and _CC
Network Type_ fields of that site.**

The _Appliance Configuration_ column indicates the appliance
configuration that will be used for the calculation of the workloads
at each site. If you want to specify which appliance configuration to
use for a site, select the drop-down menu of this column and choose a
configuration. The drop-down selection will be limited to the
appliance configuration list from the [Appliance
Definitions](#appliance-definitions-sheet) sheet. If this column is
left blank, a default appliance configuration will be chosen
automatically.

The _Appliance Model_ column indicates the list of appliance models.

The _Site Network Type_ column determines the network configuration of
the appliances assigned to the site. If the Site Network Type is left
blank, the calculations will use 10GbE SFP network interfaces for the
chosen default appliance model.

The _WAN Network Type_ column determines the WAN network configuration
of appliances assigned to the site. If left blank, the sizer will
assume the site does not require a specific network interface for WAN.

The _CC Network Type_ column determines the Cloud Catalyst or
MSDP-Cloud network configuration of the appliances assigned to the
site.

The _Appliance Bandwidth for CC (Gbps)_ column indicates how much
network bandwidth is available at each site for Cloud Catalyst or
MSDP-Cloud replication on the customer’s network. If the Cloud Catalyst
or MSDP-Cloud target is a public cloud service like AWS or Azure, take
into consideration the customer’s internet upload speed and how much of
that bandwidth is being used by other services. If the Cloud Catalyst
or MSDP-Cloud target is a local Access Appliance, this number may be
significantly larger.

# Configuration Sheets {#configuration-sheets}

The configuration sheets define configuration options of the
application as well as the prepopulated values of workload attributes.
Values in the configuration sheets generally do not need to be
changed. Adjust these values only when the customer environment has
different requirements and you understand the impact of the change.

Configuration sheets are hidden by default. They can be unhidden in two
ways. Unhide sheets by right-clicking on any worksheet tab at the
bottom of the page and select `Unhide...`. A dialog will appear. Select
the sheet you want to unhide and click OK.

![](images/unhide-dialog.png)

Most sheets have two buttons at the top of the page to unhide or hide
tabs. Click _Unhide All Tabs_ to unhide the hidden tabs. Click _Hide
Tabs_ to hide all but the four primary tabs.

## Settings {#settings-sheet}

The settings sheet lets you configure several aspects of the sizer
operation. The settings are grouped into categories, each of which has
parameters that can be modified as required.

![](images/settings-sheet.png)

### Sizer options

The parameters in the Sizer Options category are:

- **Site Bandwidth for CC (Gbps)**: This setting sets the default value
  of _Appliance Bandwidth for CC (Gbps)_ for each site in the _Sites_
  sheet for Cloud Catalyst or MSDP-Cloud replication.
  The default value is **1.6**.

- **Primary Server Sizing**: This setting controls whether the sizer
  will account for primary servers. If disabled, the sized appliances
  will not account for resource utilization by primary servers. This
  may be suitable for scenarios where an existing primary server is
  being used.
  The default is **enabled** for the tool to size for primary servers.

- **Cloud Target Type**: This setting controls the type of LTR target
  to size for the LTR replication. Selecting "Access" uses the
  performance characteristics of the Access Appliance for cloud
  replication, and additionally sizes Access appliances.
  The default is **Access**.

- **Display Resource Tip**: This setting controls the producing of
  resource safety constraint(s) tip in "Workload Assignments" sheet.
  Selecting "Disable" can reduce the sizing time for large workload
  entries on some systems.
  The default is **enabled** for the tool to display resource tip.

<!-- Uncomment below when Universal Share is ready
- **Files per Universal Share**: This setting sets the number of
  maximum files that a Universal Share contains.
  The default value is **5000000**.
-->

- **Worst case excess space usage for MSDP-C**: This setting sets the
  percentage of excess space occupied by the cloud storage when using
  MSDP-C to send data to the cloud.
  The default value is **50%**.

### Time Frame options

The parameters in the Time Frame category are:

- **Sizing Time Frame**: This is the year which the sizer will size
  appliances for. Appliances will be chosen and workloads allocated to
  keep resource utilization within safe boundaries at the end of this
  year.
  The default value is **3**.

- **Planning Horizon**: This is the number of years to project
  appliance utilization out to. This must be greater than the
  configured _Sizing Time Frame_.
  The default value is **5**.

## Default Workload Attributes {#default-workload-attributes-sheet}

The _Default Workload Attributes_ sheet defines the prepopulated
attributes of the workloads. The workload attributes are used when
defining the workloads in the Workloads sheet. The values in this sheet
are derived from a number of different sources and have been found to
be accurate for the vast majority of customers. Do not change these
values. If any of these values needs to be customized for a workload,
only change the column in the [Workloads](#workloads-sheet) sheet for
that particular workload. If a new default custom workload is needed,
it can be added by pressing the _Copy Workload Type_ button located on
the top header. To delete a custom default workload, ensure at least
one cell on that row is highlighted and press the _Delete Workload
Type_ button.

![](images/default-workload-attributes-sheet.png)

- **Client-Side Dedupe**: Not currently being used
- **Changed Block Tracking**: Not currently being used
- **Enable Single File Recovery**: Not currently being used
- **Accelerator**: Not currently being used
- **Annual Growth Rate (%)**: Average growth rate of workload year
  over year
- **Daily Change Rate (%)**: Average daily data change rate
- **Initial Dedup Rate (%)**: Initial full backup deduplication rate
- **Dedupe Rate (%)**: Daily incremental backup deduplication rate
- **Dedupe Rate Adl Full (%)**: Subsequent full backup deduplication
  rate
- **Number of Files per FETB**: Average number of files per FETB per
  client
- **Number of Channels**: Number of backup channels
- **Files per Channel**: Average number of files per channel
- **Log Backup Capable**: Indicates if the workload supports
  transaction log backups
<!-- Uncomment below when Universal Share is ready
- **Universal Share?**: Indicates that the workload is backed up
  through the Universal Share.
-->

## Safety Considerations {#safety-considerations-sheet}

The _Safety Consideration_ sheet identifies the thresholds and
constraints of a number of metrics in the application per appliance.
**Note: The capacity of 5340 and 5340-HA Appliances are capped at 960TB
due to MSDP pool capacity.** There is generally no need to change any
of the constraints.

The cells starting with `Max` are constraints used by the calculations.
The constraints indicate that once a metric reaches this limit, the
appliance is considered full. This makes sure that the appliance does
not degrade in performance when it is considered full. It also creates
an allowance for deviation from the calculated predictions.

![](images/safety-considerations-sheet.png)

- **Max Capacity Utilization (%)**: Indicates that an appliance is
  considered full when the storage reaches this number
- **Max CPU Utilization (%)**: Indicates that an appliance is
  considered full when the CPU utilization at any point during a steady
  state will reach this number
- **Max NW Utilization (%)**: Indicates that an appliance is considered
  full when the network utilization at any point during a steady state
  will reach this number
- **Max MBPs Utilization (%)**: Indicates that an appliance is
  considered full when the disk I/O utilization at any point during a
  steady state will reach this number
- **Max Memory Utilization (%)**: Indicates that an appliance is
  considered full when the memory utilization at any point during a
  steady state will reach this number
- **Max Jobs/Day**: Indicates the maximum number of jobs per day the
  calculations will assign to an appliance after determining how many
  jobs are required for a given workload
- **Max DBs with 15 Min RPO**: Indicates the maximum number of
  databases with a 15-minute transaction log backup the calculations
  will assign to an appliance (only applies to workloads with a log
  backup)
- **Max VM Clients**: Indicates the maximum number of virtual machines
  the calculations will assign to an appliance, regardless of the
  appliance hardware metric constraints above
- **Max Concurrent Streams**: Indicates the maximum number of
  concurrent streams/channels the calculations will assign to an
  appliance, regardless of the appliance hardware metric constraints
  above
- **Max Number of Files**: Indicates the maximum number of files of a
  group of workloads the calculations will assign to an appliance,
  regardless of the appliance hardware metric constraints above
- **MSDP Max Size (TB)**: Indicates the maximum MSDP pool size
  for the Appliances 5340 and 5340-HA. It is a fixed value that is not
  intended to be changed.
- **Max Number of Images**: Indicates the maximum number of backup
  images of an appliance will hold. A value of 0 to disable this
  setting.
- **LUN Size for Flex appliance (TiB)**: Indicates the maximum LUN size
  of a Flex Appliance is configured, this value is used for storage
  rounding up during sizing to prevent containers being sharing the
  same LUN to achieve the optimal I/O performance. A value of 1 can
  reduce the effect of this setting.
- **Max Number of Primary Server Containers**: Indicates the maximum
  number of Primary Server containers of a Flex Appliance will hold.
- **Max Number of Media Server Containers**: Indicates the maximum
  number of Media Server containers of a Flex Appliance will hold.
- **Max Catalog Size (TB)**: Indicates the maximum catalog size of a
  Primary Server or Primary Server containers will hold.
<!-- Uncomment below when Universal Share is ready
- **Max Number of Universal Shares**: Indicates the maximum number of
  Universal Shares of an Appliance will have.
-->

## Windows {#windows-sheet}

Each row represents the number of hours per week available for each
operation. These time constraints are then used to determine if a
given workload’s operations can be completed within that time window.
The total number of hours in the Windows sheet must not exceed the
total number of hours available in a week (168). For a more detailed
explanation of time windows, refer to [Time Windows](#time-windows).

![](images/windows-sheet.png)
