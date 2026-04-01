# Usage

## A cell value of "#N/A" is shown under the _Workload Name_ column of a row in _Workloads_ sheet

This problem can indicate that the policy name under the _Storage
Lifecycle Policy_ column of the row does not exist in _Storage
Lifecycle Polices_ sheet. Create a policy with the matching policy name
in _Storage Lifecycle Polices_ sheet.

## A cell value of "#REF!" is shown under the _Workload Name_ column of a row in _Workloads_ sheet

This problem can indicate that the policy name under the _Storage
Lifecycle Policy_ column of the row does not exist in the _Storage
Lifecycle Polices_ sheet, and there is no policy in the _Storage
Lifecycle Polices_ sheet. Create a policy with the matching policy
name in the _Storage Lifecycle Polices_ sheet.

## Not able to scroll to certain rows or columns

1. Disable the pane freeze: click `Unfreeze Panes`

2. Scroll to show the top left-most cells: In the top left quadrant
   (quadrant 2), scroll to make cell A1 appear in that quadrant

3. Re-enable the pane freeze: click `Freeze Panes`

## Manually entered site entries in _Sites_ sheet disappear after switching to another sheet

The site entries are automatically generated from values under _Site_
and _DR-dest_ columns in the _Storage Lifecycle Policies_ sheet. **Do
not manually enter any site in _Sites_ sheet.**

## Sizing process reports: float division by zero

This problem can indicate that there are empty cells under the hidden
columns in the _Storage Lifecycle Policies_ sheet, and is usually
caused by manually creating entries in this sheet. Unhide the hidden
columns in the sheet, and ensure no cells are empty by filling in the
data.

## Sizing process reports: float() argument must be a string or a number, not 'NoneType'

This problem can indicate that there are empty cells under the hidden
columns in the _Storage Lifecycle Policies_ sheet, and is usually
caused by manually creating entries in this sheet. Unhide the hidden
columns in the sheet, and ensure no cells are empty by filling in the
data.

## Sizing process reports: \<Column Heading\> must not be empty

This problem can indicate that there are empty cells under the hidden
columns in the _Workloads_ sheet, and is usually caused by manually
creating entries in this sheet. Unhide the hidden columns in the sheet,
and ensure no cells are empty by filling in the data.

## Sizing process reports: <File Name>.exe is not a valid win32 application (Windows)


Rebuilding a corrupted conda environment might be needed for this type
of error. This is not a problem in the USE Tool itself. It may be due
to anti-virus or other external factors.


Recover a corrupted conda env as described for the similar error
message in the Installation section.

## Sizing process reports: Invalid procedure call or argument (macOS)

This issue may happen if a sizing workbook is moved from a Windows
environment to a macOS environment.  The following steps should
resolve the problem:

- Navigate to the `xlwings.conf` sheet.  This sheet is hidden by
  default.

- Locate the cell containing `PYTHONPATH`.

- Delete the contents of the located cell and the value in the column
  to its right.
