# What's new in USE 4.1

## Overview for 4.1

New features of USE 4.1 include additional workload types, performance
and storage sizing for Flex Scale Appliances, and changes and
enhancements to the user interface and experience. This document is
meant to provide an overview of these differences, for a thorough look
at these features, please see the USE 4.1 documentation.

## More supported workload types

- Oracle-TDE
- PostgreSQL
- SharePoint
- SQL-TDE

<!-- Uncomment below when Universal Share is ready
## Universal Share

USE 4.1 adds the option of supporting Universal Share backup. Workloads
that require Universal Share backup can select the option.
-->

## More supported Appliance models

USE 4.1 adds support for Flex Scale Appliance 5551 and 5562. It
provides performance and storage sizing support for Flex Scale
Appliance 5551 and 5562. The guard rail values of those models are also
available in _Safety Considerations_ sheet.

## 5250 and Flex 5250 Calculated Capacity change

The _Calculated Capacity_ value in the _Appliance Definitions_ sheet is
updated to include the internal storage (9TB/36TB) for 5250 and Flex
5250 Appliance configurations.

## 5350 and Flex 5350 Memory size change

The _Memory_ value in the _Appliance Definitions_ sheet is updated from
1536GB to 768GB for 5350 and Flex 5350 Appliance configurations with
less than 960TB of capacity.

## Optimize sizing time of large workload entries

The USE 4.1 provides the option to turn off the resource tip generation
to shorten the sizing time required for large workload entries on some
systems.

## User interface changes

- Report _Allocated Capacity (TiB)_ and _Allocated Capacity (%)_ of
  allocated appliance capacity usage in the _Appliance Summary_ sheet
- Add _Display Resource Tip_ and _Worst case excess space usage for
  MSDP-C_ parameters in the _Settings_ sheet
- Add _Flex Scale Sizing_ button in the _Sites_ sheet
- Display success or fail status window after a workload or
  NBDeployUtil import operation
- Add _Raw Appliance Summary_ and _Workload Summary_ sheets
- Update terminalogy
  [click here for reference](https://www.veritas.com/content/support/en_US/doc/103228346-147321331-0/v149833249-147321331)
<!-- Uncomment below when Universal Share is ready
- Add _Files per Universal Share_ parameter in the _Settings_ sheet
- Add _Universal Share?_ column in the _Workloads_ and _Default
  Workload Attributes_ sheets
- Add _Max Number of Universal Shares_ column in the _Safety
  Considerations_ sheet
-->

# What's new in USE 4.0

## Overview for 4.0

New features in USE 4.0 include workload isolation, LTR target addition
with Access appliances, and changes and enhancements to the user
interface and experience. This document is meant to provide an overview
of these differences, for a thorough look at these features, please see
the USE 4.0 documentation.

## Workload Isolation

USE 4.0 adds the option of flagging workloads to be "isolated." The
"isolated" workloads are placed on the dedicated appliances that are
not shared with other workloads.

## LTR target with Access Appliances

USE 4.0 adds the option of having Access appliances as LTR targets.
Workloads that need LTR will default to have Access appliances as the
LTR target. The sizing result reports the configuration, number of
Access Appliances required and their year-over-year utilization.

## User interface changes

- Filter the required Appliance models through the _Model_ column in
  the _Appliance Definitions_ sheet for USE to only size with

# What’s new in USE 3.1

## Overview for 3.1

New features of USE 3.1 include optional sizing for NetBackup Primary
servers, optimized selection of Appliances, performance and storage
sizing for Appliances and Flex Appliances, changes and enhancements to
the user interface and experience. This document is meant to provide an
overview of these differences, for a thorough look at these features,
please see the USE 3.1 documentation.

## Optional Sizing for Primary Server

USE 3.1 allows skipping sizing for NetBackup Primary servers, for
scenarios where an existing appliance or server is to be used as a
primary server.

## Optimized Selection of Appliances

USE 3.1 proposes appliances that are optimal for the required storage.

## More supported Appliance models

USE 3.1 adds support for Appliance 5350, and Flex Appliance 5350. It
provides performance and storage sizing support for Appliance 5350, and
Flex Appliances 5350. For Appliance 5350, and Flex Appliance 5340-HA,
only capacity modeling is supported. The guard rail values of those
models are also available in _Safety Considerations_ sheet.

## Changes to NBDeployUtil Import

Importing workloads from an NBDeployUtil Itemization report now asks
for the name of an SLP and associates imported workloads with that
SLP.  This allows for grouping of batches of imported workloads and
sharing attributes such as domain name among the workloads in a single
imported batch.

## User interface changes

- Report _I/O (MB/s)_ usage in addition to _I/O (%)_ in the _Appliance
  Summary_ sheet
- Report _Full Backup_, _Incremental Backup_, _Size Before
  Deduplication_, and _Size After Deduplication_ images size usage in
  the _Appliance Summary_ sheet

# What’s new in USE 3.0

## Overview for 3.0

New features of USE 3.0 include additional workload types, backup
domain designation, client-side deduplication, capability to import
NBDeployUtil itemization output into workloads and import policies and
workloads from the existing workbooks of USE 2.1 and later releases,
performance and storage sizing for NetBackup Primary servers, MSDP
Cloud, Flex Appliances, and changes and enhancements to the user
interface and experience. This document is meant to provide an overview
of these differences, for a thorough look at these features, please see
the USE 3.0 documentation.

## More supported workload types

- File System (Large Files)
- File System (Small Files)
- File System (Typical)
- Informix-On-Bar
- MySQL
- NCR-Teradata
- NDMP (Large Files)
- NDMP (Small Files)
- NDMP (Typical)
- SAP
- Splunk

## Granular support of backup domains

USE 3.0 adds support for designating backup domains, to distinguish
workloads from different domains.

To specify a backup domain, enter it in the _Domain_ column of the
_Storage Lifecycle Policies_ sheet. If workloads exceed the capacity of
one domain or no domain is specified, USE will assign a new domain
automatically.

![](images/whats-new-storage-lifecycle-policies-domain.png)

## More supported Appliance models

USE 3.0 adds support for Flex Appliance models. It provides performance
and storage sizing support for Flex Appliances 5250 and 5340. For Flex
Appliance 5340-HA, only capacity modeling is supported. The guard rail
values of those models are also available in the _Safety
Considerations_ sheet.

## Import NBDeployUtil Itemization output

USE now can import NBDeployUtil itemization output, and convert it
into the workloads in the _Workloads_ sheet.

To import NBDeployUtil itemization output, click the _Import
NBDeployUtil_ button in the _Workloads_ sheet, and select the
NBDeployUtil report Excel file from the File Navigation window.

## Import policies and workloads from existing USE workbooks

USE now can import policies from _Storage Lifecycle Policies_ in
addition of workloads from _Workloads_ sheets of an existing USE 2.1
or later release. The imported policies and workloads are entered into
the _Storage Lifecycle Policies_ and _Workloads_ sheets respectively.

To import policies and workloads, click the _Import Workload_ button in
the _Workloads_ sheet, then select the USE workbook from the File
Navigation window.

## User interface changes

- The local, DR, and LTR retention columns are now colorized for better
  visibility
- The _Appliances Needed_ sheet is renamed to _Results_ sheet
- A _Results Tab_ button to activate the _Results_ sheet within the USE
  workbook
- The _Number of Files_ columns are renamed to  _Number of Files per
  FETB_ columns

# What’s new in USE 2.1

## Overview for 2.1

USE 2.1 added performance and storage sizing support for appliance
model 5250.

# What’s new in USE 2.0

## Overview for 2.0

New features of USE 2.0 include changes and enhancements to the user
interface and experience. This document is meant to provide an
overview of these differences. For a thorough look at these features,
please see the USE 2.0 documentation.

## Simplified install procedure for Windows

USE 2.0 includes a new method of installation that shortens the
procedure to get up and running with the steps below:

1. Extract the USE zip file to `%USERPROFILE%`. This will create a
   directory named `%USERPROFILE%\vps-backend`.

2. Open PowerShell Terminal with the user account (**not**
   administrator), navigate to the directory where the USE 2.0 zip
   package file was extracted by running the command below:

      `cd $env:USERPROFILE\vps-backend`

3. Start the setup process by running by running the command below:

      `.\setup-use.ps1`

## Simplified install procedure for MacOS

USE 2.0 includes a new method of installation that shortens the
procedure to get up and running with the steps below:

1. Extract the USE zip file to `$HOME`. This will create a directory
   named `$HOME/vps-backend`.

2. Open Terminal, navigate to the directory where the USE 2.0 zip
   package file was extracted by running the command below:

      `cd $HOME/vps-backend`

3. Start the setup process by running the command below with the user
   account (**not** root or sudo):

      `bash setup-use.sh`

## More supported Appliance models

USE now includes broader support for other appliance models. With
version 2.0, it provides capacity and performance modeling support for
5240 and 5340 appliance models. For 5340-HA, only capacity modeling is
supported.

To choose a specific appliance model, you can use one of two methods.

### 1. Explicitly select Appliance configuration

Select an appliance configuration from the list of available
appliances in the dropdown menu.

![](images/whats-new-appliance-configuration.png)

![](images/whats-new-appliance-definitions.png)

You can also choose a filter in the _Appliance Definitions_ sheet to
limit the appliance models shown.

### 2. Automatically select Appliance configuration

Configure the requirement columns and allow USE to select the
appliance model. As inputs, you can use

- Appliance Model
- Site Network Type
- WAN Network Type
- CC Network Type

The appliance configuration will allocate sufficient capacity and
memory available based on the Appliance Model and Site Network Type.

For example, if appliance model `5240` is chosen and `1GbE` is chosen
for Site Network Type, the appliance configuration utilized for sizing
purposes will be `5240 299TB_Capacity 6_Shelves 256_RAM 4x1GbE
2x10GbE_Copper`.

Please note that if the _Appliance Configuration_ dropdown is selected
it will override any selections for _Appliance Model_, _Site Network
Type_, _WAN Network Type_, and _CC Network Type_.

## Addition of custom Sizing Time Frame

Now you can easily set the time frame to size for by clicking the
_Sizing Time Frame_ button which activates a pop up on the _Storage
Lifecycle Policies_ sheet.

## Update To Safety Considerations sheet

The values in the Safety Considerations sheet are now listed under each
appliance model to reflect the strength of each model. A new safety
field called _MSDP Max Size (TB)_ is introduced, and the default
values of _Max CPU Utilization (%)_ and _Max NW Utilization (%)_ are
updated in this release.

## Change in user experience of results presentation

Several User experience improvements were made in presenting results of
sizing on the _Results_ sheet and _Appliance Summary_ sheets.

To the right of the _Total_ column are the lists of sites and the
number of appliances of each appliance model assigned to each. Based
on the site utilization for the maximally utilized appliance, the
color will change. For example, as capacity utilization gets higher
the shade of yellow gets darker.

![](images/shades-of-yellow.png)

The _Appliance Summary Chart_ now shows every appliance resource per
site. The added benefit to this is that it paints a holistic picture
of the resources used per site.

![](images/whats-new-appliance-summary.png)

## Default unit change from terabyte (TB) to tebibyte (TiB)

Across the USE tool, values and inputs expressed in terabytes (TB) are
changed to instead be displayed in tebibytes (TiB). Both measure
storage in units of bytes; one tebibyte is $2^{40}$, or
1,099,511,627,776 bytes, and one terabyte is $10^{12}$, or
1,000,000,000,000 bytes. This change allows the USE tool to align with
other documentation for appliance models as well as gives you a more
accurate sizing indication when using fractional values.

## Added workload storage requirements

To give a more detailed analysis on workload capacity growth year over
year a table of all the workloads and its disk usage has been added on
the _Workload Assignment Details_ sheet

![](images/whats-new-workload-disk-usage.png)
