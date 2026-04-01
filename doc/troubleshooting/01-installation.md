# Installation

## Setup script reports: Not able to create /var/root/Library/Containers/com.microsoft.Excel/Data/xlwings.conf (MacOS)

This problem can indicate the root account is used for the installation
instead of the user account. A possible cause of this could be the user
switched to the root account prior to the installation. The Microsoft
Office application is not installed with the root account; hence the
required configuration file is not available for the installation
script to update.

To resolve this issue, exit from the root account and switch back to
the user account before resuming the installation.

## Setup script reports: Not able to remove the previous installation directory (MacOS)

This problem can indicate an issue of a previous installation of
Anaconda. A possible cause of this could be an installation directory
owner not being the current user account.

1. Check the script output to see the if owner of the Anaconda
   directory is the same as the current user account:

    `drwxr-xr-x  15 <owner>  COMMUNITY\Domain Users  4096 May  7 16:25 /Users/<current user account>/opt/anaconda3/`

2. If the owner of the Anaconda directory is not the current user
   account, use the command below to remove the directory. Restart the
   installation script to proceed with the installation.

   **Note: The `sudo` command will prompt for the password of the
   current user account:**

    `cd $HOME/opt`

    `sudo rm -rf anaconda3`

## Setup script reports: setup-use.ps1 cannot be loaded or setup-use.ps1 is not digitally signed (Windows)

This problem can indicate the system policy prevents the execution of
unsigned PowerShell scripts. To allow the USE setup script to install
the required packages:

1. Run the following command to unblock the script, then start the
   installation again:

    `Unblock-File -Path ./setup-use.ps1`

If script execution is not permitted after execution of the above
command:

1. Run the following command to record the current execution policy:

	  `$original_policy = Get-ExecutionPolicy`

2. Run the following command and retry the installation:

	  `Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser`

3. After the setup process is completed, the original execution policy
   (recorded in step 1) can be restored by running:

	  `Set-ExecutionPolicy -ExecutionPolicy $original_policy -Scope CurrentUser`

## Setup script reports: The system cannot find the path specified (Windows)

This problem can indicate an issue with incorrectly set environment
variables. A possible cause of this could be an interrupted Anaconda
installation. To resolve this:

1. Start the Anaconda PowerShell Prompt and run the following command:

    `conda init --reverse`

2. The command will prompt you to close and restart the shell. Do so,
   and in the new shell, run the command:

    `conda init`

## Setup script reports: Anaconda installation failed, conda command not available (Windows)

This problem can occur if there was a previous USE installation that
was removed. In such cases, a previous config file can be left over
that causes the Miniconda installation to fail.

To resolve this problem, delete the file `%USERPROFILE%\.condarc`
after uninstalling any existing Anaconda/Miniconda installation.

## Setup script reports: \<File Name\>.exe is not a valid win32 application (Windows)

Rebuilding a corrupted conda environment might be needed for this type
of error. This is not a problem in the USE Tool itself. It may be due
to anti-virus or other external factors.

A corrupted conda env can be recovered from by deleting the env and
recreating it. To do this:

1. Deactivate the vupc env:

    `conda deactivate`

2. Delete the vupc env:

    `conda env remove --name vupc`

3. Switch current directory to the vps-backend directory and create
   the vupc env again:

    `conda env create`

## Setup script reports: failed to change safety_checks configuration (Windows)

This problem can indicate an issue of a previous installation of
Anaconda. However, if the same error persists with the uninstallation
and reinstallation of Anaconda, it is possible the Command Prompt
(cmd.exe) of the operating system is not working properly. To verify
this:

1. Open a Command Prompt by entering the command below in the Windows'
   search box:

    `cmd`

2. Highlight the Command Prompt selection and click on it to open

3. If the Command Prompt does not open, contact IT Department to
   resolve the Command Prompt issue.

4. After IT resolved the issue, proceed with the USE installation.

## Setup script fails with: "failed to update base anaconda environment" (Windows)

This error can result from several issues.  Some of these can be
resolved by attempting a full reinstall of USE and its dependencies.

1. Navigate to the Apps & features control panel by searching for `Add
   or remove programs` in Windows' search box

2. Search for `miniconda`

3. Click the `Uninstall` button and complete the uninstallation by
   following the prompts

4. Re-run the USE setup script

## Setup script fails with: "Failed to create environment after retries" (Windows)

This error can result from several issues.  Some of these can be
resolved by attempting a full reinstall of USE and its dependencies.

1. Navigate to the Apps & features control panel by searching for `Add
   or remove programs` in Windows' search box

2. Search for `miniconda`

3. Click the `Uninstall` button and complete the uninstallation by
   following the prompts

4. Re-run the USE setup script
