# Uninstallation

## Uninstalling USE (Windows)

1. Start an Anaconda Shell

2. Activate the vupc environment by running `conda activate vupc`

3. Remove the xlwings Add-in by running `xlwings addin remove`. If the
   Add-in is not already installed, this command will fail. This
   failure can be safely ignored.

4. Navigate to the `%USERPROFILE%\AppData\Local\Continuum\anaconda3`
   directory and remove the envs directory if it exists

5. Run the `Uninstall-Anaconda3` (or `Uninstall-Miniconda3`) command
   present in the above directory

6. Delete the `%USERPROFILE%\.condarc` file
