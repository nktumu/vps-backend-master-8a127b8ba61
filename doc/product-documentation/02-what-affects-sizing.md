# WHAT AFFECTS THE SIZING

USE provides accurate appliance sizing by employing a complex
mathematical engine that uses hundreds of variables. This section
describes some of the high-level concepts that the user should be
aware of when providing input and analyzing the output of USE.

## Time windows {#time-windows}

There are different data protection job types performed at different
times. Each job type consumes resources on the appliance a little
differently. A time window can be described as a period during which
an appliance may perform a specific type of task for one or more
clients.

### Backup Windows

A backup window is the time during which the appliance is performing
backup operations, moving data from the client machines to a media
server. Differences between backup types will also impact the backup
appliance differently. For example, during a full backup window, a
database can be backed up entirely in a single full backup
operation. During an incremental backup window, a database’s changes
since a previous backup can be backed up in an incremental backup
operation.

### Replication Windows

A replication window is the time during which the appliance is
replicating backup sets to another media server or to a cloud service.

### Concurrency of Windows

While it is common practice for windows to overlap, USE is limited in
this version to only one active window at a time. This will likely
change in a future version.

## The Steady State

USE makes its calculations based on an appliance steady state. An
appliance in a steady state runs regular garbage collection, data
defragmentation, and compaction tasks. In a steady state, dedupe of
the various data types have a low variance. It is assumed that it will
take about six months on average for an appliance to reach a steady
state.

When an appliance has reached a steady state, the I/O size will also
have a low variance. Backup streams are partitioned within the
appliance and packed into large containers. When restores are
performed, the restore streams read the entire container. The I/O size
is dictated mainly by the amount of available memory and will be
relatively constant. All I/O seen while in the steady state will be
random in nature. The steady state is calculated for the size of
workloads based on the initial data size, the growth rate, and the
average amount of time that it takes for an appliance to get to a
steady state.

## Files per FETB of a Workload Type

One of the factors that USE employs to calculate the number of
NetBackup Primary servers is the NetBackup catalog size; the more files
are being backed up by a NetBackup Primary server, the larger the
catalog size. At the same FETB (Front-End TiB) size, different
workload types can consist of smaller or larger number of files. USE
has predetermined values listed under the _Number of Files per FETB_
column for each default workload type in the _Default Workload
Attributes_ sheet.

