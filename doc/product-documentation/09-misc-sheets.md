# MISCELLANEOUS SHEETS {#miscellaneous-sheets}

There are additional hidden sheets in USE that are used by the
application and should not be modified by a user, except when
specifically instructed to do so by a Veritas Support Engineer.

## Appliance Chart Data

The _Appliance Chart Data_ sheet is the data used to create the
_Resource Utilization_ line graph in the [Results](#results-sheet)
sheet. Never make changes to this sheet.

## Flex Scale Totals

The _Flex Scale Totals_ sheet is internally used as part of the Flex
Scale sizing calculation.  Do not make changes here; it may break
sizer operation.

## Logs {#logs-sheet}

The _Logs_ sheet is a verbose log of the application. This sheet will
not be created until a sizing result is calculated and will be
recreated every time a new sizing result is calculated. Logging
results are not preserved between runs. If you want to save the
logging output, save a copy of the Excel workbook. In cases where the
user is seeing errors or inaccurate results, the output from this
sheet is invaluable to Veritas Support Engineers.

## Raw Appliance Summary

The _Raw Appliance Summary_ sheet shows utilization of each appliance
used per year. The values in each year column are as of the end of the
specified year, i.e, the _Year 1_ columns refer to the state at the end
of the first year of operation.

## Site Data

The _Site Data_ sheet is used by the application during workload
distribution calculations. Never make changes to this sheet.

## xlwings.conf

The _xlwings.conf_ sheet is used as a workaround to manipulate the path
for the application. Do not make changes to this sheet unless
specifically instructed to do so by a Veritas Support Engineer.

## Workload Summary

The _Workload Summary_ sheet shows utilization of each workload used
per year. The values in each year column are as of the end of the
specified year, i.e, the _Year 1_ columns refer to the state at the end
of the first year of operation.
