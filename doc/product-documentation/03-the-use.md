# THE UNIFIED SIZING ESTIMATOR (USE)

It is recommended that all appliance sales use this application to
help accurately size customer environments. USE combines historical
performance information along with customer provided input to provide
deployment options for a wide variety of operating conditions.

## Obtaining USE

Download the current version of USE from
[https://vtools.veritas.com/#/library](https://vtools.veritas.com/#/library).

## Installing USE

Once USE has been downloaded, a number of steps need to be performed
before running the application. USE is supported for Windows and Mac
OS.

### Installing on Microsoft Windows

Instructions for installing the tool on Windows are detailed below.

1. Extract the USE zip file to `%USERPROFILE%`, which will very likely
  be your home directory, such as `C:\Users\first.lastname`. This will
  create a directory named `%USERPROFILE%\vps-backend`.

2. Open PowerShell Terminal with the user account (**not**
  administrator). **All Windows operating systems are equipped with
  PowerShell. If you need help locating your PowerShell, install
  [click here](https://docs.microsoft.com/en-us/powershell/scripting/install/installing-windows-powershell?view=powershell-7).**
  Navigate to the directory where the files were extracted by running
  the command below:

      `cd $env:USERPROFILE\vps-backend`.

3. Start the setup process by running the command below:

      `.\setup-use.ps1`.

### Upgrading USE on Microsoft Windows

Instructions for upgrading the tool on Windows are detailed below.

1. Close all opened USE workbooks.

2. (Optional) Quit all Excel application instances.

3. (Optional) Delete the existing `%USERPROFILE%\vps-backend`
  directory.

4. Extract the USE zip file to `%USERPROFILE%`. This will create a
  directory named `%USERPROFILE%\vps-backend`.

5. (Optional) Remove the older version of `USE-<version>.xlsm` and
  `USE-<version>.pdf` files from the `%USERPROFILE%\vps-backend`
  directory.

6. Follow steps (2) & (3) of the Installing on Microsoft Windows
  section above to download and update the dependent libraries.

### Troubleshooting for Windows

- Error: [Errno 13] Permission denied: '`<path>\envs\vupc\vcruntime140.dll`'

  The above error happens when there is interference with your
  antivirus, re-running the script will resolve that error.

### Installing on Mac OS

Instructions for installing the tool on Mac OS are detailed below.

1. Extract the USE zip file to `$HOME`. This will create a directory
  named `$HOME/vps-backend`.

2. Open Terminal, navigate to where the files were extracted by running
  the command below:

      `cd $HOME/vps-backend`.

3. Start the setup process by running the command below with the user 
  account (**not** root or sudo):

      `bash setup-use.sh`.

### Upgrading USE on Mac OS

Instructions for upgrading the tool on Mac OS are detailed below.

1. Close all opened USE workbooks.

2. (Optional) Quit all Excel application instances.

3. (Optional) Delete the existing `$HOME/vps-backend` directory.

4. Extract the USE zip file to `$HOME`. This will re-create the
  directory named `$HOME/vps-backend`.

5. (Optional) Remove the older version of `USE-<version>.xlsm` and
  `USE-<version>.pdf` files from the `$HOME/vps-backend` directory.

6. Follow steps (2) & (3) of the Installing on Mac OS section above to
  download and update the dependent libraries.

## Using USE after install

After following the installation process, locate a fresh USE 4.1
Excel workbook by navigating to `vps-backend` directory, and
double click `USE-4.1.xlsm`.
