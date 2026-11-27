<#
.SYNOPSIS
Prepares a clean, read-only Dohna Dohna v1.1 payload folder for iOS import via Aether.
Source files are NEVER modified.
#>
[CmdletBinding()]
param(
    [string]$SourceDir = $env:DOHNA_SOURCE_DIR,
    [string]$OutputDir = '',
    [switch]$IncludeUserCharacters,
    [switch]$IncludeSaveData,
    [string]$SaveSourceDir = '',
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SourceDir)) {
    throw "Please specify -SourceDir '<path-to-DohnaDohna-v1.1>' (or set `$env:DOHNA_SOURCE_DIR)."
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'ios_game_payload\DohnaDohna'
}

if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
    throw "Source game directory not found: $SourceDir"
}

$requiredFiles = @(
    'AliceStart.ini',
    'dohnadohna.ain',
    'dohnadohnaCG.afa',
    'dohnadohnaPact.afa',
    'dohnadohnaSound.afa',
    'dohnadohnaVoice.afa',
    'dohnadohnaEx.ex',
    'Data\Shader.slk',
    'Movie\Op.apeg'
)

$totalBytes = [int64]0
$missing = @()
$plan = @()

foreach ($rel in $requiredFiles) {
    $srcPath = Join-Path $SourceDir $rel
    if (-not (Test-Path -LiteralPath $srcPath -PathType Leaf)) {
        $missing += $rel
        continue
    }
    $item = Get-Item -LiteralPath $srcPath
    $totalBytes += $item.Length
    $plan += [PSCustomObject]@{
        RelativePath = $rel
        SourcePath   = $srcPath
        SizeBytes    = $item.Length
    }
}

if ($missing.Count -gt 0) {
    throw ("Missing required Dohna Dohna runtime file(s): " + ($missing -join ', '))
}

Write-Host "Source : $SourceDir"
Write-Host "Output : $OutputDir"
Write-Host ("Payload: {0} files, {1:N2} GB ({2:N0} bytes)" -f $plan.Count, ($totalBytes / 1GB), $totalBytes)
foreach ($entry in $plan) {
    Write-Host ("  - {0,-24} {1,12:N0} bytes" -f $entry.RelativePath, $entry.SizeBytes)
}

$xsys4rcContent = "encoding = `"gbk`"`n"

$resolvedSaveSrc = $SaveSourceDir
if ([string]::IsNullOrWhiteSpace($resolvedSaveSrc)) {
    $localSave = Join-Path $SourceDir 'SaveData'
    $docsSave = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'AliceSoft\多娜多娜'
    if (Test-Path -LiteralPath $localSave -PathType Container) {
        $resolvedSaveSrc = $localSave
    } elseif (Test-Path -LiteralPath $docsSave -PathType Container) {
        $resolvedSaveSrc = $docsSave
    }
}

if ($DryRun) {
    Write-Host "DryRun: would generate .xsys4rc (`encoding = `"gbk`"`)."
    if ($IncludeSaveData -or $IncludeUserCharacters) {
        if ($resolvedSaveSrc -and (Test-Path -LiteralPath $resolvedSaveSrc -PathType Container)) {
            Write-Host "DryRun: detected save/character source at $resolvedSaveSrc"
        } else {
            Write-Host "DryRun: no local SaveData directory found (skipping save copy)."
        }
    }
    exit 0
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

foreach ($entry in $plan) {
    $dstPath = Join-Path $OutputDir $entry.RelativePath
    $dstParent = Split-Path -Parent $dstPath
    New-Item -ItemType Directory -Path $dstParent -Force | Out-Null

    $needCopy = $true
    if (Test-Path -LiteralPath $dstPath -PathType Leaf) {
        $dstItem = Get-Item -LiteralPath $dstPath
        if ($dstItem.Length -eq $entry.SizeBytes) {
            $needCopy = $false
        }
    }
    if ($needCopy) {
        Write-Host "Copying $($entry.RelativePath)..."
        Copy-Item -LiteralPath $entry.SourcePath -Destination $dstPath -Force
    } else {
        Write-Host "Skipping existing $($entry.RelativePath) (matching size)."
    }
}

$xsys4rcPath = Join-Path $OutputDir '.xsys4rc'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($xsys4rcPath, $xsys4rcContent, $utf8NoBom)
Write-Host "Wrote $xsys4rcPath"

if ($resolvedSaveSrc -and (Test-Path -LiteralPath $resolvedSaveSrc -PathType Container)) {
    if ($IncludeSaveData) {
        $dstSave = Join-Path $OutputDir 'SaveData'
        New-Item -ItemType Directory -Path $dstSave -Force | Out-Null
        Copy-Item -Path (Join-Path $resolvedSaveSrc '*') -Destination $dstSave -Recurse -Force
        Write-Host "Copied full SaveData to $dstSave (note: Aether stores active saves inside app container Home/Documents)."
    } elseif ($IncludeUserCharacters) {
        $userSrc = Join-Path $resolvedSaveSrc 'User'
        if (Test-Path -LiteralPath $userSrc -PathType Container) {
            $userDst = Join-Path $OutputDir 'SaveData\User'
            New-Item -ItemType Directory -Path $userDst -Force | Out-Null
            Copy-Item -Path (Join-Path $userSrc '*') -Destination $userDst -Recurse -Force
            Write-Host "Copied SaveData\User to $userDst"
        }
    }
}

Write-Host "Done. Package/AirDrop/Files-copy the folder '$OutputDir' (or zip it first without Windows .exe files) to iPhone/iPad and import in Aether."
