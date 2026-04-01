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

$install_path = "$env:USERPROFILE\AppData\Local\Continuum\anaconda3"
$env_path = "$install_path\envs\vupc"
$conda_bin = "$install_path\condabin\conda.bat"
$openssl_bin = "$install_path\Library\bin\openssl.exe"

$install_file = $MyInvocation.MyCommand
$local_path = "$PSScriptRoot"
$onedrive_path = "C:\nul"
$user_local_path = "$env:USERPROFILE\AppData\Local\temp"

$installer_url = "https://repo.anaconda.com/miniconda/Miniconda3-py39_4.11.0-Windows-x86_64.exe"
$installer_hash = "6013152b169c2c2d4bcd75bb03a1b8bf208b8545d69116a59351af695d9a0081"

$cpp_redist_subject = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"

$logfile = "$local_path\setup-log.txt"

$stdoutTempFile = "$user_local_path\use-setup-stdout"
$stderrTempFile = "$user_local_path\use-setup-stderr"

$config_files = @(
    "$env:USERPROFILE\.condarc",
    "$install_path\.condarc"
)

Function Report-Status {
    param($operation)
    Write-Progress -Activity "Installing __version__" -Status $operation
}

Function Log {
    param($message)

    $d=$(Get-Date -UFormat "%Y-%m-%d %H:%M:%S")
    Write-Output "$d $message" >> $logfile
}

Function Log-Exception {
    param($exc, $message)

    $exc_details = $exc | Format-List -Force | Out-String
    Log $message
    Log $exc_details
}

Function Log-Configs {
    $config_files | ForEach-Object {
	try {
	    $cfgContent = Get-Content -Path $_ -Raw
	    Log "config file: $_"
	    Log $cfgContent
	} catch [Exception] {
	    Log-Exception $_.Exception "unable to read $_"
	}
    }
}

Function Log-Mitm-Certs {
    $arguments = $("s_client", "-connect", "repo.anaconda.com:443", "-showcerts")
    try {
	Check-Output $openssl_bin $local_path $arguments "failed to fetch repo certs"
    } catch [Exception] {
	Log-Exception $_.Exception "running openssl failed"
    }
}

Function Remove-If-Exists {
    param($filename)

    try {
	Remove-Item -Path $filename -Recurse
    } catch [Exception] {
	Log-Exception $_.Exception "removing $filename failed"
    }
}

Function Check-Output {
    param($command, $working_directory, [string[]]$arguments, $error_message)

    $emptyFile = New-TemporaryFile

    $startProcessParams = @{
	FilePath = $command
	WorkingDirectory = $working_directory
	ArgumentList = $arguments
	RedirectStandardInput = $emptyFile
	RedirectStandardOutput = $stdoutTempFile
	RedirectStandardError = $stderrTempFile
	Wait = $true
	PassThru = $true
	NoNewWindow = $true
    }

    Log "running command $command $arguments"
    $process = Start-Process @startProcessParams

    Remove-Item $emptyFile

    $stdout = Get-Content -Path $stdoutTempFile -Raw
    $stderr = Get-Content -Path $stderrTempFile -Raw

    Log @"
command exitcode $($process.ExitCode)

output:
$stdout

errors:
$stderr
"@
    if ($process.ExitCode -ne 0) {
	$full_error_message = @"
$error_message

output:
$stdout

errors:
$stderr
"@
	throw $full_error_message
    }
}

Function Download-File {
    param($url, $local, $expected_hash)
    Invoke-WebRequest -Uri $url -OutFile $local
    $calculated_hash = Get-FileHash -Path $local -Algorithm SHA256
    if ($calculated_hash.Hash -ne $expected_hash) {
	$error_message = @"
Downloaded file is corrupt.

Downloaded URL: $url
Expected Hash: $expected_hash
Calculated Hash: $calculated_hash
"@
	throw $error_message
    }
}

Function Install-Anaconda {
    if (Test-Path -LiteralPath $conda_bin) {
	Log "conda command exists, skipping anaconda installation"
	return
    }

    Report-Status "downloading installer"
    Log "downloading miniconda installer"

    $installer_local = "$PSScriptRoot/miniconda.exe"
    Download-File $installer_url $installer_local $installer_hash

    $arguments = $("/InstallationType=JustMe", "/AddToPath=1",
		   "/RegisterPython=0", "/S",
		   "/D=$install_path")
    Report-Status "installing miniconda"
    Log "starting miniconda installation"
    Start-Process -Wait -FilePath $installer_local -ArgumentList $arguments

    if ( -not (Test-Path -LiteralPath $conda_bin)) {
	Log "conda command does not exist after installation"
	throw "Anaconda installation failed, conda command not available"
    }
}

Function Setup-SslVerify {
    Log "disabling ssl certificate verification because of intermittent MITM issues"

    $arguments = $("config", "--system", "--set", "ssl_verify", "False")
    Check-Output $conda_bin $local_path $arguments
}

Function Setup-Anaconda-Configuration {
    Report-Status "configuring anaconda"

    $cfg_files = @("$install_path\.condarc", "$env:USERPROFILE\.condarc")
    foreach ($cfg in $cfg_files) {
	if (Test-Path -Path $cfg) {
	    Remove-If-Exists $cfg
	}
    }

    $arguments = $("config", "--set", "safety_checks", "enabled")
    Check-Output $conda_bin $local_path $arguments "failed to change safety_checks configuration"

    $arguments = $("config", "--set", "extra_safety_checks", "true")
    Check-Output $conda_bin $local_path $arguments "failed to change extra_safety_checks configuration"

    $env:PATH = "$env:PATH;$install_path\Library\bin"
}

Function Update-Base {
    Report-Status "updating base anaconda environment"
    Log "updating base environment"
    $arguments = $("update", "--yes", "--name", "base", "--channel", "defaults", "conda")
    Check-Output $conda_bin $local_path $arguments "failed to update base anaconda environment"
}

Function Install-Vcredist {
    $vcredist_url = "https://aka.ms/vs/16/release/VC_redist.x64.exe"
    $local_path = "$user_local_path/VC_redist.x64.exe"

    Log "downloading VC++ libraries"
    Report-Status "downloading microsoft visual C++ redistributable"
    if ( -not (Test-Path -LiteralPath $local_path -PathType Leaf)) {
	Invoke-WebRequest -Uri $vcredist_url -OutFile $local_path
    }

    Log "verifying signature on C++ redist installer"
    $cert = Get-AuthenticodeSignature $local_path
    $msg = $cert.StatusMessage
    Log "certificate status: $msg"
    $subj = $cert.SignerCertificate.Subject
    Log "certificate issuer: $subj"
    if ($subj -ne $cpp_redist_subject) {
	throw "Signature on downloaded installer is not valid"
    }

    Log "installing VC++ libraries"
    Report-Status "installing VC++ redistributable (watch for background UAC prompt)"
    $arguments = $("/install", "/quiet", "/norestart")
    Check-Output $local_path $user_local_path $arguments "failed to install pre-requisites"
}

Function Pre-Reqs {
    if (Get-Package -Name "Microsoft Visual C++ 2015*" -MinimumVersion 14.0 -ErrorAction:SilentlyContinue) {
	Log "required version of VC++ libraries installed already"
    } else {
	Install-Vcredist
    }
}

Function Do-Create-Environment {
    param($attempt)

    if ($attempt -gt 2) {
	throw "Failed to create environment after retries"
    }

    Report-Status "preparing environment for running USE attempt $attempt"

    $existing_environment = $false
    try {
	Log "checking for existing vupc environment"
	$arguments = @("list", "--name", "vupc")
	Check-Output $conda_bin $local_path $arguments "no existing environment"
	Log "existing environment found"
	$existing_environment = $true
    } catch [Exception] {
	Log-Exception $_.Exception "listing environment failed"
	Log "no existing environment found"
	$existing_environment = $false
    }

    if ($existing_environment) {
	Log "removing existing environment"
	$arguments = $("env", "remove", "--name", "vupc")
	Check-Output $conda_bin $local_path $arguments "failed to remove old environment"
    }

    if (Test-Path -Path $env_path) {
	Remove-If-Exists $env_path
    }

    $arguments = $("env", "create")
    try {
	Check-Output $conda_bin $local_path $arguments "failed to create vupc environment"
	Log "environment create succeeded"
    } catch {
	Log "environment create failed on attempt $attempt"
	$new_attempt = $attempt + 1
	Do-Create-Environment $new_attempt
    }
}

Function Create-Environment {
    Do-Create-Environment 1
}

Function Create-Config {
    Log "creating xlwings config file"
    Report-Status "configuring xlwings"

    New-Item -Path $env:USERPROFILE\.xlwings -ItemType Directory -Force | Out-Null

    $config_path = "$env:USERPROFILE\.xlwings\xlwings.conf"

    $config_content = @"
"CONDA PATH",$install_path
"CONDA ENV",vupc
"INTERPRETER_WIN",$install_path\envs\vupc\python.exe
"ONEDRIVE_WIN",$onedrive_path
"@
    $config_content | New-Item -Path $env:USERPROFILE\.xlwings\xlwings.conf -ItemType File -Force | Out-Null
}

Function Enable-Logging {
    if (Test-Path -LiteralPath $logfile -PathType Leaf) {
	Remove-Item $logfile
    }
}

Function Install-Setup {
    param($attempt)

    Log "installing use packages"
    Report-Status "Package installation initiated"
    $local_path1 = "$PSScriptRoot/src/core"
    $local_path2 = "$PSScriptRoot/src/xl"
    $arguments = $("install" , "-e", ".")
    $pip_bin = "$install_path\envs\vupc\Scripts\pip.exe"

    Check-Output $pip_bin $local_path1 $arguments "failed to create core package"
    Check-Output $pip_bin $local_path2 $arguments "failed to create xl package"
}

Function Cleanup {
    Log "cleaning up tempfiles"
    Remove-If-Exists $stdoutTempFile
    Remove-If-Exists $stderrTempFile
    Log "finished tempfile cleanup"

    Write-Output "happy USEing"
}

Clear-Host

Enable-Logging

Log "Installing __version__"
Log "Installation script: $install_file"

Pre-Reqs
Install-Anaconda
Setup-Anaconda-Configuration
Log-Mitm-Certs
Setup-SslVerify
Update-Base
Create-Environment
Create-Config
Install-Setup

Cleanup
