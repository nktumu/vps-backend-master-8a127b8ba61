# WORKING WITH USE FOR SIZING

The user interface for USE is a customized Excel workbook. Start USE
by opening the USE workbook in Excel. The USE workbook can be found in
the `vps-backend` directory by navigating into `src`.
After navigating into the directory, double click on the file
`USE-4.1.xlsm`. There are four main input sheets visible in the
workbook:

- Appliance Definitions (optional input sheet)
- Storage Lifecycle Policies
- Workloads
- Sites

The [Appliance Definitions](#appliance-definitions-sheet) sheet
contains a filterable list of available appliance configurations, and
the filtered rows of this sheet make up the list in the drop-down menu
under the _Appliance Configuration_ column of the [Sites](#sites-sheet)
sheet. **Note: Unless your customer needs a specific appliance model or
configuration, ignore this sheet for now. It can be customized later.**

The [Storage Lifecycle Policies](#storage-lifecycle-policies-sheet)
(SLP) sheet contains the storage lifecycle characteristics assigned to
the customer workloads. Before defining customer workloads, the SLPs
must be defined so that they can be assigned to the workloads. Once
the SLPs have all been defined, click the _Go to Workloads_ button in
the upper left to move to the _Workloads_ sheet.

The [Workloads](#workloads-sheet) sheet contains the customer
workloads and their corresponding storage lifecycle characteristics.
Define each workload on a separate line and assign them an SLP. Once
the customer workloads have all been defined, click the _Go to Sites_
button in the upper left to move to the _Sites_ sheet.

The [Sites](#sites-sheet) sheet contains the sites that were defined
in the _SLP_ sheet and subsequently assigned to the workloads in the
_Workloads_ sheet. Each site can be customized to define the appliance
model, site network type, or appliance bandwidth for Cloud Catalyst or
MSDP-Cloud. Any cell that is left blank will use a default value for
the sizing calculations. After customizing the sites, click one of the
buttons on the upper left to initiate the sizing calculation process:

- click the _Sizing Results_ button to size for standard Appliances,
- click the _Flex Sizing_ button to size for Flex Appliances, or
- click the _Flex Scale Sizing_ button to size for Flex Scale
  Appliances

The results will not be immediately displayed. Once the calculations
are complete, the [Results](#results-sheet) sheet details appliance
options by showing a resource utilization graph and sized appliance
configurations. There are a number of [hidden sheets](#output-sheets)
that reveal additional details.

**Note: _Flex Sizing_ follows the best practice of preventing
containers from sharing the same LUN, thus achieving better I/O
performance. This can result in larger calculated allocated capacities
than _Sizing Results_ and require more or larger capacity Flex
Appliances than for standard Appliances.** 

To save the results, save the workbook as a normal Excel file with a
different name. Ensure the newly saved file is located in the same
directory. To run another calculation, click the _Go to Workloads_
button in the upper left to start the process over.

Below Is a diagram of the intended workflow for using USE 4.1:

![](images/sizing-workflow.png)

## Current Limitations {#current-limitations}

There are limitations in regard to appliance support, this section will
highlight them.

USE performance models are built with data obtained from the following
appliance configurations:

- 5240 appliances with 256GiB RAM
- 5250 appliances with 256GiB RAM
- 5340 appliances with 768GiB RAM
- 5350 appliances with 768GiB RAM

When appliances with a different quantity of physical memory are chosen
for sizing, the reported memory utilization may be higher or lower
than what is expected in practice:

- If the chosen appliance has less memory than the qualified value,
  the memory utilization reported by USE will be higher than in
  practice
- If the chosen appliance has more memory than the qualified value,
  the memory utilization reported by USE will be lower than in
  practice

This is a limitation that is expected to be lifted in a future version
which will be qualified with performance data from additional
appliance configurations.

The table below indicates the appliance model supported per version of
USE.

+---------------+-----------------+-----------------------------+
|Version        |Model            |Support                      |
+===============+=================+=============================+
|USE 1.0        |5150             |Storage Sizing, Performance, |
|               |                 |Cloud Catalyst: 5150         |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 2.0        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA    |Cloud Catalyst: 5150         |
|               |                 |                             |
|               |                 |Storage Sizing, Performance: |
|               |                 |5240, 5340                   |
|               |                 |                             |
|               |                 |Storage Sizing: 5340-HA      |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 2.1        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA,   |Cloud Catalyst: 5150         |
|               |5250             |                             |
|               |                 |Storage Sizing, Performance: |
|               |                 |5240, 5340, 5250             |
|               |                 |                             |
|               |                 |Storage Sizing: 5340-HA      |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 3.0        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA,   |Cloud Catalyst, MSDP-C: 5150 |
|               |5250, Flex 5250, |                             |
|               |Flex 5340,       |Storage Sizing, Performance, |
|               |Flex 5340-HA     |MSDP-C: 5240, 5340, 5250,    |
|               |                 |Flex 5250, Flex 5340         |
|               |                 |                             |
|               |                 |Storage Sizing, MSDP-C:      |
|               |                 |5340-HA, Flex 5340-HA        |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 3.1        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA,   |Cloud Catalyst, MSDP-C: 5150 |
|               |5250, Flex 5250, |                             |
|               |Flex 5340,       |Storage Sizing, Performance, |
|               |Flex 5340-HA     |MSDP-C: 5240, 5340, 5250,    |
|               |5350, Flex 5350, |Flex 5250, Flex 5340, 5350,  |
|               |Flex 5350-HA     |Flex 5350                    |
|               |                 |                             |
|               |                 |Storage Sizing, MSDP-C:      |
|               |                 |5340-HA, Flex 5340-HA,       |
|               |                 |Flex 5350-HA                 |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 4.0        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA,   |Cloud Catalyst, MSDP-C: 5150 |
|               |5250, Flex 5250, |                             |
|               |Flex 5340,       |Storage Sizing, Performance, |
|               |Flex 5340-HA     |MSDP-C: 5240, 5340, 5250,    |
|               |5350, Flex 5350, |Flex 5250, Flex 5340, 5350,  |
|               |Flex 5350-HA     |Flex 5350                    |
|               |                 |                             |
|               |                 |Storage Sizing, MSDP-C:      |
|               |                 |5340-HA, Flex 5340-HA,       |
|               |                 |Flex 5350-HA                 |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
|USE 4.1        |5150, 5240,      |Storage Sizing, Performance, |
|               |5340, 5340-HA,   |Cloud Catalyst, MSDP-C: 5150 |
|               |5250, Flex 5250, |                             |
|               |Flex 5340,       |Storage Sizing, Performance, |
|               |Flex 5340-HA     |MSDP-C: 5240, 5340, 5250,    |
|               |5350, Flex 5350, |Flex 5250, Flex 5340, 5350,  |
|               |Flex 5350-HA,    |Flex 5350                    |
|               |Flex Scale 5551, |                             |
|               |Flex Scale 5562  |Storage Sizing, MSDP-C:      |
|               |                 |5340-HA, Flex 5340-HA,       |
|               |                 |Flex 5350-HA                 |
|               |                 |                             |
|               |                 |Storage Sizing, Performance: |
|               |                 |Flex Scale 5551, Flex Scale  |
|               |                 |5562                         |
|               |                 |                             |
+---------------+-----------------+-----------------------------+
