# Prerequisites

Have USE 4.1 installed, you can find USE 4.1
[here](https://vtools.veritas.com/#/library).

Install USE 4.1 by extracting the archive to your home directory and
running the `setup-use.ps1` script in PowerShell (for Windows) or the
`setup-use.sh` script in Terminal (for MacOS). Refer to the full
product documentation for detailed steps.

# Workflow

![](images/sizing-workflow.png)

# Step 1

On the _Storage Lifecycle Policies_ sheet (SLP), customize the existing
default policy types by selecting the _Backup Image Location_ on column
E. After selecting the desired _Backup Image Location_ you can
change the retention values to meet your needs.

![](images/quick-start-slp.png)

- You can create a new custom SLP by highlighting an existing SLP name
  and clicking _Copy SLP_ button. After doing so, change the newly
  created SLP name by clicking column A and typing in a name of your
  choice.

# Step 2

After clicking the _Go to Workload_ button on the _Storage Lifecycle
Policies_ sheet, you are shown the _Workloads_ Sheet, where you
are able to enter in the different workloads your customer may have.

![](images/quick-start-workloads.png)

- The _Workloads_ sheet will have a pre-existing row filled
  out. Customize the existing column by selecting the storage policy
  you defined in the _Storage Lifecycle Policies_ sheet.
- Change the existing fields (_Workload Type_, _Number of Clients_,
  _FETB_, etc.) to meet your customer needs. Please note the retention
  values are obtained by SLP defined on the previous SLP sheet.
- Create a new workload entry by clicking the _New Workload_ button.

# Step 3

- After clicking the _Go to Sites_ button on the _Workloads_ sheet, you
  are shown the _Sites_ sheet where you are able to select a
  different appliance model for each site.
- If you need to, select _Appliance Configuration_ or _Appliance Model_
  on columns B or C for each site.
- Click one of the buttons on the upper left on column A to initiate
  the sizing calculation process:

  - click the _Sizing Results_ button to size for standard Appliances,
  - click the _Flex Sizing_ button to size for Flex Appliances, or
  - click the _Flex Scale Sizing_ button to size for Flex Scale
    Appliances

# Step 4

Analyze the results given on the _Results_ sheet.

![](images/quick-start-results.png)

- In column A, under each of the server config headers, the chosen
  appliance configurations are shown. To the right of each
  configuration is shown the number of that appliance configuration
  being allocated to the site.

![](images/resource-utilization-chart.png)

- The _Resource Utilization_ graph shows the total resources used year
  over year for all appliances.
- For more detailed information, click the _Unhide All Tabs_ button,
  then click the _Appliance Summary_ tab from the bottom.
