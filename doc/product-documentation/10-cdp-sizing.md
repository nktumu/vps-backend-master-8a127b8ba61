# SIZING CDP FOR VMWARE

NBU 9.1 introduces Continuous Data Protection (CDP) feature for
VMware.  In order to protect virtual machines with the feature, a CDP
gateway configuration is required on a media server, and the gateway
needs hardware resources to function. The USE package includes two
worksheets to calculate hardware resource requirements for the CDP
gateway. Those worksheets are in the CDP sizing workbook
`CDP-sizing-calculator.xlsx` file.

The CDP sizing workbook suppors sizing in two different scenarios:

- the customer has a certain number of virtual machines that need
  protection, and the requirement is to find out what the resource
  requirements would be

- the customer has a particular configuration of servers for use as
  CDP gateways, and the requirement is to find out how many virtual
  machines could be protected

The following sections describe worksheet usage for each of these
scenarios.

## CDP Sizing For Known VMs

The first sheet in the workbook (`Calculate #CDP Gateways`) supports
the first scenario.  To understand this sheet, let us take an example
where a customer has 1000 VMs, each 1TB in size and generating data
with change rate of 10% everyday. The required RPO is 30 minutes with
retention of 1 month.  The goal is to estimate the resource
requirement in terms of storage, network, and compute.

The following information can be provided on this sheet:

- **Number of VMs**: Number of virtual machines to protect with CDP.
- **RPO(hr)**: Backup frequency in hours. Currently, CDP supports a
  minimum RPO of 30 minutes.
- **Retention period**: The number of days to retain backup images.
- **VM Size**: Virtual machine average VMDK size.
- **Change rate**: Daily data change rate in %.

Apart from this, the following additional NetBackup related fields can
also be configured if required for the environment.

### MSDP parameters

- **Max concurrent Jobs for dedicated MSDP**: Customer may have a
  dedicated media server for MSDP. The MSDP may process data for other
  workloads. Based on the load, how many CDP jobs, a MSDP can process
  can be entered here.
- **MSDP Throughput local(MB/s)**: This indicates that data transfer
  (backup) rate for MSDP. Higher at local, slower at remote.

### CDP gateway parameters

The CDP gateway parameters are set to the default values as configured
in software.

- **Maxm VMs one CDP can handle**: This is a read-only field. Software
  limit on How many maximum number of VMs one CDP GW can handle
  irrespective of hardware configuration. Currently, limit is set to
  400 VMs.
- **Memory Fragment size(MBs)/VM**: This indicates minimum RAM needed
  for each VM to store incoming IOs. More memory improves in-memory IO
  performance.
- **VM Quota Size(GBs)**: The CDP gateway has a staging area quota per
  VM. Default value is 10GB. User can change this value in
  `/usr/openv/netbackup/nbcct/nbcct.conf`.
- **Number of parallel full sync**: The CDP gatway restricts parallel
  full sync to reduce resources utilization at a time. Default value
  is 5. Which means, when customer is subscribing VMs to CDP, at a
  time only 5 VMs will receive its initial full sync data. This value
  can be changed in `/usr/openv/netbackup/nbcct/nbcct.conf`. This
  value is not considered in the sizing calculation but is known to
  impact gateway resources in terms of memory and CPU usage.

Based on the above input, the worksheet will compute CDP gateway and a
high level MSDP requirements.

**Note**: CDP gateway and MSDP can be co-located, so it is important
to consider MSDP sizing along with CDP.  This sizing worksheet only
produces a rough guideline for MSDP.

### Sizing Results

In the output, the worksheet reports number of CDP gateways, memory,
network and storage requirements along with some additional
information. Also MSDP sizing is computed based on number of VMs,
their size, RPO, retention period, and change rate.

The following parameters are reported for CDP gateways:

- **Total CDP Deployment**: Number of CDP gateways that customer need
  to provision.
- **Total Memory Requirements(GBs)**: Combined RAM requirement across
  gateways.
- **Storage for Staging(TB)**: Total staging area across gateways.
- **CDP Ingestion Speed(MB/s)**: Total data ingestion speed across
  gateways.
- **Total data per VM per RPO(TB)**: Data size to be backed up in the
  given RPO.

The following parameters are reported for media servers:

- **Number of MSDP**: Number of MSDP configured media servers.
- **MSDP Size(TBs)**: Combined storage requirement across media
  servers.
- **MSDP Memory Requirement(in GBs)**: Combined RAM requirement across
  media servers.
- **Backup Time per VM**: Backup time per VM considering data to be
  backed up in the given RPO and standard execution time for Snapshot
  and Discovery jobs.
- **Total data per VM per RPO(TB)**: Data size to be backed up in the
  given RPO.
- **Backup host memory Requirements(GBs)**: Total RAM required to
  execute backup jobs considering standard factors & total number of
  VMs & concurrent jobs on MSDP.

In addition, the worksheet also calculates the number of servers
required:

- **MSDP**: Number of media servers required
- **CDP**: Number of CDP gateways required
- **Total**: Total number of media servers

Total system requirements:

- **Total Memory requirement (GiB)**: Total RAM required (CDP + MSDP)
- **Total Staging requirement (TiB)**: Total storage required (CDP + MSDP)
- **Network(MiB/s)**: Network speed (ingest)

## CDP Sizing for Known Servers

The worksheet referred to as `Calculate #VMs protected` allows users
to compute number of virtual machines that can be protected with the
given configuration.

In this worksheet, users can specify the following inputs:

- RPO (hr)
- Retention of backup image (days)
- VM Size (TiB)
- Change Rate of VM per day (%)

In addition, users can also specify the configuration of the server
intended to be used as the CDP gateway.  The parameters that can be
specified here are:

- physical memory
- number of CPU cores
- available storage

The worksheet will report the number of VMs that can be protected
using this server as CDP gateway.

The result also depends on whether the CDP gateway will be co-located
with MSDP on the same server.  This affects the number of VMs that can
be supported.  The worksheet models this be reducing the amount of
memory that can be assumed to be dedicated for CDP:

- if CDP gateway is co-located with MSDP, the worksheet assumes 20% of
  the host memory will be available for CDP.
- if CDP gateway is dedicated, the worksheet assumes 50% of the host
  memory will be available for CDP.

## Additional Assumptions

The CDP sizing workbook does not estimate utilization of CPU cores.
Performance tests for those parameters will be published separately.

Performance testing for CDP has used SSD storage.  Performance with
HDDs may be lower.

The CDP gateway requires memory buffer to host I/O incoming from ESX.
The software assumes a minimum of 200MiB buffer per ESX server being
protected.  If the environment is capable of sending I/O at higher
rates, the amount of memory allocated for CDP may need to be higher.
