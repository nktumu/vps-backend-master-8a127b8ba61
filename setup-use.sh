#!/bin/bash
# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

CMD_BASENAME="/usr/bin/basename"
CMD_BASH="/bin/bash"
CMD_CAT="/bin/cat"
CMD_CLEAR="/usr/bin/clear"
CMD_CP="/bin/cp"
CMD_CURL="/usr/bin/curl"
CMD_DIRNAME="/usr/bin/dirname"
CMD_DSCL="/usr/bin/dscl"
CMD_FILE="/usr/bin/file"
CMD_FIND="/usr/bin/find"
CMD_GREP="/usr/bin/grep"
CMD_HASHER="/usr/bin/shasum"
CMD_LS="/bin/ls"
CMD_MKDIR="/bin/mkdir"
CMD_PRINTF="/usr/bin/printf"
CMD_PWD="/bin/pwd"
CMD_RM="/bin/rm"
CMD_SED="/usr/bin/sed"
CMD_TOUCH="/usr/bin/touch"
CMD_UNIQ="/usr/bin/uniq"
CMD_WC="/usr/bin/wc"
CMD_WHICH="/usr/bin/which"
CMD_WHOAMI="/usr/bin/whoami"

install_file="$0"
install_path="$HOME/opt/anaconda3"
activate_path="$install_path/bin/activate"
conda_bin="$install_path/condabin/conda"
envs_path="$install_path/envs/vupc"
script_path="$HOME/Library/Application Scripts/com.microsoft.Excel"
script_file="xlwings.applescript"
onedrive_path="/dev/null"
config_path="$HOME/Library/Containers/com.microsoft.Excel/Data/xlwings.conf"
config_content1="\"INTERPRETER_MAC\",\"$envs_path/bin/python\""
config_content2="\"ONEDRIVE_MAC\",\"$onedrive_path\""

installer_url="https://repo.anaconda.com/miniconda/Miniconda3-py39_4.11.0-MacOSX-x86_64.sh"
installer_hash="7717253055e7c09339cd3d0815a0b1986b9138dcfcb8ec33b9733df32dd40eaa"

conda_pip="$envs_path/bin/pip"
local_path=`$CMD_PWD -P`
cert_file="$local_path/root-certs.pem"
title=true
same_config=false
core_path="$local_path/src/core"
xl_path="$local_path/src/xl"

log_file="$local_path/setup-log.txt"

function Setup-Logfile() {
    if [ -f "$log_file" ]; then
        rm -f "$log_file"
    fi

    exec 3>&1
    exec 4>&2

    exec 1>>"$log_file" 2>>"$log_file"

    set -x
}

function Report-Status() {
    Status=$1

    if [ $title = true ]; then
        $CMD_PRINTF "%s\n" "$1" >&3
        title=false
    else
        $CMD_PRINTF "\33[2K\r\t%s" "$1" >&3
    fi
}

function Say() {
    $CMD_PRINTF "$@" >&3
}

function Incomplete-Install() {
    incomplete_message="Installation is incomplete. Resolve the reported issue before resuming installation"
    Say "\n\n%s\n" "$incomplete_message"
}

function Check-Account() {
    Report-Status "checking account"
    cmd_out=$($CMD_WHOAMI 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to check the account used for installation"
        Incomplete-Install
        exit 1
    fi  
    if [ $cmd_out == "root" ]; then
        Report-Status "The root account is not supported. A valid user account is required"
        Incomplete-Install
        exit 1
    fi  
}

function Check-Anaconda() {
    $CMD_WHICH conda > /dev/null 2>&1
    cmd_stat=$?

    return $cmd_stat
}

function Download-File() {
    url="$1"
    local_binary="$2"
    expected_hash="$3"

    CURL_ARGS="--silent --show-error --fail --location"
    cmd_out1=$($CMD_CURL $CURL_ARGS --output "$local_binary" "$url" 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        cmd_out2=$($CMD_CURL $CURL_ARGS --output "$local_binary" --cacert "$cert_file" "$url" 2>&1)
        cmd_stat=$?
    fi

    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to download installer"
        Say "\n\n"
        Say "%s\n" "$cmd_out1"
        Say "%s\n" "$cmd_out2"
        Incomplete-Install
        exit 1
    fi

    local_basename=$($CMD_BASENAME "$local_binary")
    $CMD_PRINTF "%s  %s\n" "$expected_hash" "$local_basename" | $CMD_HASHER --check --status
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Downloaded installer is corrupt"
        Say "\n\n"
        Say "Downloaded URL: %s\n" $url
        Say "Expected Hash: %s\n" $expected_hash
        Incomplete-Install
        exit 1
    fi
}

function Install-Anaconda() {
    binary_path="$local_path/miniconda.sh"
    Report-Status "downloading installer"
    Download-File "$installer_url" "$binary_path" $installer_hash

    Prepare-Installation-Directory
    Report-Status "installing miniconda"
    cmd_out=$($CMD_BASH "$binary_path" -b -p $install_path 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to install miniconda"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    Report-Status "activate miniconda"
    cmd_out=$(source $activate_path 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to activate miniconda"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    Report-Status "init shell"
    shell_config=`$CMD_DSCL . -read $HOME UserShell | $CMD_SED 's/UserShell: //'`
    if [ $shell_config == "/bin/zsh" ]; then
        cmd_out=$($conda_bin init zsh 2>&1)
        cmd_stat=$?
    else
        cmd_out=$($conda_bin init 2>&1)
        cmd_stat=$?
    fi
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to init shell"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
}

function Remove-Anaconda() {
    Report-Status "removing conda"

    conda install --yes anaconda-clean > /dev/null 2>&1
    cmd_stat=$?
    if [ $cmd_stat -eq 0 ]; then
        anaconda-clean --yes > /dev/null 2>&1
    fi
    conda_path=$($CMD_DIRNAME $($CMD_DIRNAME $($CMD_WHICH conda)))
    $CMD_RM -rf "$conda_path"
    if [ -d "$conda_path" ]; then
        cmd_out=$($CMD_LS -ld "$conda_path" 2>&1)
        Report-Status "Not able to remove conda directory"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    Prepare-Installation-Directory
}

function Prepare-Installation-Directory() {
    Report-Status "preparing installation directory"

    $CMD_RM -rf $install_path
    if [ -d $install_path ]; then
        cmd_out=$($CMD_LS -ld $install_path 2>&1)
        Report-Status "Not able to remove the previous installation directory"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    $CMD_RM -rf $HOME/.condarc $HOME/.conda $HOME/.continuum
}

function Setup-SslVerify() {
    config_value=$1

    Report-Status "configuring SSL certificate validation"
    cmd_out=$($conda_bin config --set ssl_verify "$config_value" 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to change SSL verification configuration"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
}

function Setup-Anaconda-Configuration() {
    Report-Status "configuring anaconda configuration"

    cmd_out=$($conda_bin config --set safety_checks enabled 4>&3)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to change safety_checks configuration"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    cmd_out=$($conda_bin config --set extra_safety_checks true 4>&3)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to change extra_safety_checks configuration"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
}

function Do-Update-Base() {
    $conda_bin update --yes --name base --channel defaults conda
}

function Update-Base() {
    Setup-SslVerify "False"

    Report-Status "updating base anaconda environment"
    Do-Update-Base
    cmd_stat=$?
    if [ $cmd_stat -eq 0 ]; then
        return
    fi

    Report-Status "Not able to update base environment"
    Incomplete-Install
    exit 1
}

function Create-Environment() {
    Report-Status "preparing environment for running USE"

    $conda_bin list --name vupc > /dev/null 2>&1
    cmd_stat=$?
    if [ $cmd_stat -eq 0 ]; then
    # env already exists, remove env
        cmd_out=$($conda_bin env remove --name vupc 2>&1)
        cmd_stat=$?
        if [ $cmd_stat -ne 0 ]; then
            Report-Status "Not able to remove env VUPC"
            Say "\n\n%s\n" "$cmd_out"
            Incomplete-Install
            exit 1
        fi
    fi
    # creating new env
    cmd_out=$($conda_bin env create 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to create env VUPC"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
}

function Configure-Script() {
    Report-Status "configuring apple script"

    script_content=$($CMD_FIND "$envs_path" -name "$script_file" -print -quit 2>&1 | head -n1)
    if [ -z "$script_content" ]; then
        Report-Status "Not able to locate script file"
        Say "\n\n\n"
        Incomplete-Install
        exit 1
    fi
    cmd_out=$($CMD_MKDIR -p "$script_path" 2>&1)
    if [ ! -d "$script_path" ]; then
        cmd_out=$($CMD_LS -ld "$script_path" 2>&1)
        Report-Status "Not able to create script directory"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
    cmd_out=$($CMD_CP "$script_content" "$script_path" 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
        Report-Status "Not able to create script file"
        Say "\n\n%s\n" "$cmd_out"
        Incomplete-Install
        exit 1
    fi
}

function Create-Config() {
    Report-Status "configuring xlwings"

    if [ ! -f "$config_path" ]; then
        cmd_out=$($CMD_TOUCH "$config_path" 2>&1)
        cmd_stat=$?
        if [ $cmd_stat -ne 0 ]; then
            Report-Status "Not able to create $config_path"
            Say "\n\n%s\n" "$cmd_out"
            Incomplete-Install
            exit 1
        fi
    fi

    $CMD_CAT << EOF > "$config_path"
$config_content1
$config_content2
EOF
}

function Install-Setup() {
    Report-Status "installing packages"
    Report-Status "Core package installation initiated"
    cmd_out=$($conda_pip install -e "$core_path" 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
	Report-Status "Not able to install sizer core package $core_path"
	$CMD_PRINTF "\n\n%s\n" "$cmd_out"
    Incomplete-Install
	exit 1
    fi
    Report-Status "xl package installation initiated"
    cmd_out=$($conda_pip install -e "$xl_path" 2>&1)
    cmd_stat=$?
    if [ $cmd_stat -ne 0 ]; then
	Report-Status "Not able to install sizer xl package $xl_path"
	$CMD_PRINTF "\n\n%s\n" "$cmd_out"
    Incomplete-Install
	exit 1
    fi

    $conda_bin list --name vupc
}

function End-Install() {
    Report-Status "happy USEing"
    Say "\n"
}

$CMD_CLEAR

Setup-Logfile

Report-Status "Installing __version__"
Report-Status "Installation script: $install_file"
Check-Account
Check-Anaconda
cmd_stat=$?
if [ $cmd_stat -eq 0 ]; then
    cmd_out=$($CMD_GREP -E "^$config_content1$|^$config_content2$" $config_path | $CMD_UNIQ | $CMD_WC -l 2>&1)
    if [ $cmd_out -eq 2 ]; then
        # Configuration matches
        same_config=true
    else
        # Configuration not matching
        Remove-Anaconda
        Install-Anaconda
    fi
else
    Install-Anaconda
fi
Setup-Anaconda-Configuration
Update-Base
Create-Environment
Configure-Script
if [ $same_config == false ]; then
    Create-Config
fi
Install-Setup
End-Install
