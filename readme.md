# VPS-backend
VPS-backend is the backend logic for correctly sizing applainces.

## Development Environment Using Anaconda/Miniconda
1. Install [Anaconda](https://www.anaconda.com/distribution/) or
   [Miniconda](https://docs.conda.io/en/latest/miniconda.html).

2. Install `git`, and `git-lfs` from the Anaconda repository if they
   are not present in the development environment already.

        conda install git git-lfs

3. Configure `git-lfs` by running

        git lfs install

4. Clone this repo from Bitbucket.

5. Navigate to the root directory (`vps-backend/`).

6. Run `make env` to create the `vupc` virtual environment.

7. Use `conda activate vupc` to activate the environment. Use `conda
   deactivate` to deactivate it.

### Windows users

Windows users need to install `make`, which is available from the
Anaconda repository.  Install it by running

    conda install -c conda-forge make

from an Anaconda shell.  Installing it in the base environment will be
sufficient.

## Adding Additional Packages
1. Add the package you want, together with its version, to
   `environment.yml` or `dev-environment.yml`.  If the package is a
   development dependency, it should go into `dev-environment.yml`.
   If it is a dependency that is required by users, it should go into
   `environment.yml`.
2. Navigate to the root directory of this repo and run `conda env
   update` while the `vupc` environment is active.

## Help with Conda Environments
1. [Official
   documentation](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html).
2. [Blogpost](https://tdhopper.com/blog/my-python-environment-workflow-with-conda/)
   describing one data scientist's Conda-based workflow.

## Extract VBA Project

The VBA project is checked in to the source tree as a compiled binary.
There are no readily-available tools to generate this directly from
source text other than Excel itself.  If you need to make changes to
the VBA code for any reason, you'll need to use this procedure:

1. Generate the current workbook

        make generate-excel

2. Load the workbook in Excel and make the changes you need to the VBA
   modules.

3. Extract the VBA project using the `vba_extract.py` utility.  The
   binary is checked in at `src/xlwriter/use_xlwriter/`, so it must be
   moved prior to commit or diff.

        vba_extract.py USE-1.0.xlsm
        mv vbaProject.bin src/xlwriter/use_xlwriter/

   The `vba_extract.py` script is part of the `xlsxwriter` package.
   If you don't have the command available, you can just use `unzip`
   to examine the workbook directly and extract the `vbaProject.bin`
   file from it.

4. Commit the changed VBA project.

## Configure Git to Show VBA Diff

The `olevba` command can be used to extract the source text of the
binary VBA.  The `show-vba-text.py` script is a thin wrapper over
`olevba` that removes some extraneous output.  This can be integrated
into git by running:

        git config diff.olevba.textconv 'python3 tools/show-vba-text.py'

With this config change, git will automatically run the text
conversion when showing diffs.

**Troubleshooting Tip:** This will only work when executed from the
repo directory and with the appropriate environment is activated.

**Note:** The MacOS and Windows editors do not have the same policies
for capitalization, and will modify existing code when opened.  It's
expected to see diff outputs with `.Row` changed to `.row` and
`.count` changed to `.Count`.

## Running Tests

    make

This will verify formatting and run linting, in addition to running
the testcases.

If the formatting check fails, run

    black src

to reformat.

### Disabling VBA Execution prompts

When running the test suite, a large number of Excel files are created
and opened with VBA execution.  These prompts will pause test
execution while waiting for user confirmation.

[Windows instructions](https://support.microsoft.com/en-us/office/enable-or-disable-macros-in-office-files-12b036fd-d140-4e74-b45e-16fed1a7e5c6)

[MacOS instructions](https://support.microsoft.com/en-us/office/enable-or-disable-macros-in-office-for-mac-c2494c99-a637-4ce6-9b82-e02cbb85cb96)

## Reviewing Pull Requests

Each pull request needs successful builds on both Windows and macOS
before it can be merged.  After a pull request is created, the
`report.py` script discovers the PR and automates the process of
running tests and posting results to stash.

### Setup credentials

Set the STASH_USERNAME environment variable to contain your stash
username.  `report.py` will prompt you for your stash password if
necessary, and you will be asked for MFA confirmation.  Upon
successful authentication, the token for REST API access will be
stored in `~/.vupc-stash-rest-token` and used.  You will not be asked
for the password again as long as the token remains valid.  The REST
API token stays valid for much longer than the SCM token.

### Reviewing VBA changes

Since the VBA code is checked in as a binary file, the web diff tool
does not produce the typical diff output for the pull request review.
As a workaround, be sure that the diff output is added as a comment
for any pull requests that change `vbaProject.bin`.

### Run build

Checkout the branch under review and run

    make publish

to post build results for your platform.  This script will connect to
Stash and post comments and test status updates to your pull request.

**Troubleshooting Tip:** If tests fail unexpectedly (for example, on
the known-good master branch) you you may not have the required
benchmark files.  This command may resolve the issue.

    make download-benchmarks

## VS Code IDE settings

If you would like to use VS Code, there are a few settings you may
need to change when working with `conda`.

### Conda environments in VSCode terminals (MacOS)

VS Code can [reorder the
`$PATH`](https://github.com/microsoft/vscode/issues/70248#issuecomment-472582012)
leading to [issues activating a conda
environment](https://github.com/microsoft/vscode-python/issues/5764#issuecomment-515709089).
This can be resolved by adding this to your `settings.json`.

    // Choose your preferred shell, such as "zsh" or "bash"
    "terminal.integrated.defaultProfile.osx": "zsh",
    "terminal.integrated.inheritEnv": false,

### Auto-activate conda environment

Adding this line will automatically activate the environment to match
your VSCode workspace.  Only the active terminal is effected on
creation.

    "python.terminal.activateEnvInCurrentTerminal": true,

Other options are to manually activate or install a directory-based
environment management like `direnv`.

## Releasing Packages

Checkout the tag for which the package needs to be built and run

    make package

The source tree must be clean for the packaging to not mess up.  The
makefile explicitly checks for this.  Run

    git clean -dfx

to clean up the source tree.  Note that you will lose any files that
are not checked in when you run this command.

## Xlwings Upgrading Process

When updating the xlwings dependency, we also need to update the
xlwings VBA module. To do this:

1. Generate a fresh `USE-1.0.xlsm` file by running `make
   generate-excel`

2. Install the new xlwings package using `conda env update` while the
   `vupc` environment is active.

3. Create a new project by running `xlwings quickstart --standalone
   temp-project` this creates the file named
   `temp-project/temp-project.xlsm`

4. Open this new xlsm file in Excel and open the VBA editor. Locate
   the xlwings module and export it to a file.

5. Open `USE-1.0.xlsm` in Excel and open the VBA editor. Remove the
   current xlwings module and import the new `xlwings.bas` module.

6. Follow the usual process to save the file and extract the VBA
   project.
