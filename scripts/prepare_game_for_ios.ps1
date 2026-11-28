<#
.SYNOPSIS
Prepares a clean, read-only Dohna Dohna v1.1 payload folder for iOS deployment.
Source files are NEVER modified.
#>
[CmdletBinding()]
param(
    [string]$SourceDir = $env:DOHNA_SOURCE_DIR,
    [string]$OutputDir = '',
    [switch]$IncludeUserCharacters,
    [switch]$IncludeSaveData,
    [switch]$IncludePrinnyMod,
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

function Get-Xsystem4ScriptIdentity {
    param([Parameter(Mandatory)][string]$RootDir)
    $ainFiles = @(Get-ChildItem -LiteralPath $RootDir -File -Filter '*.ain' |
        Sort-Object { $_.Name.ToLowerInvariant() })
    if ($ainFiles.Count -eq 0) {
        return ''
    }
    if (-not ('DohnaFnv1a' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
public static class DohnaFnv1a {
    public static ulong HashStep(ulong seed, byte[] data, int count) {
        unchecked {
            ulong h = seed;
            for (int i = 0; i < count; i++) {
                h = (h ^ data[i]) * 1099511628211UL;
            }
            return h;
        }
    }
    public static string ComputeXsystem4Identity(string[] filePaths) {
        unchecked {
            ulong h = 14695981039346656037UL;
            byte[] buf = new byte[65536];
            foreach (string p in filePaths) {
                var fi = new FileInfo(p);
                byte[] nameBytes = Encoding.UTF8.GetBytes(fi.Name.ToLowerInvariant());
                h = HashStep(h, nameBytes, nameBytes.Length);
                byte[] lenBytes = Encoding.UTF8.GetBytes(fi.Length.ToString());
                h = HashStep(h, lenBytes, lenBytes.Length);
                using (var fs = File.OpenRead(p)) {
                    int n = fs.Read(buf, 0, Math.Min(65536, buf.Length));
                    h = HashStep(h, buf, n);
                }
            }
            return h.ToString("x");
        }
    }
}
'@
    }
    $paths = @($ainFiles | ForEach-Object { $_.FullName })
    return [DohnaFnv1a]::ComputeXsystem4Identity($paths)
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

$scriptIdentity = Get-Xsystem4ScriptIdentity -RootDir $SourceDir

# Collect optional save files (*.asd / *.rsm / *.msk / SystemData)
$saveFiles = @()
if ($IncludeSaveData) {
    $saveDirs = @()
    if (-not [string]::IsNullOrWhiteSpace($SaveSourceDir) -and (Test-Path -LiteralPath $SaveSourceDir -PathType Container)) {
        $saveDirs += $SaveSourceDir
    } else {
        $siblingFullCg = Join-Path (Split-Path -Parent $SourceDir) '官方中文版适用全CG存档'
        $localSave = Join-Path $SourceDir 'SaveData'
        $docsRoot = [Environment]::GetFolderPath('MyDocuments')
        $docsCandidates = @(
            (Join-Path $docsRoot 'AliceSoft\多娜多娜'),
            (Join-Path $docsRoot 'AliceSoft\ドーナドーナ いっしょにわるいことをしよう')
        )
        foreach ($cand in (@($siblingFullCg, $localSave) + $docsCandidates)) {
            if ($cand -and (Test-Path -LiteralPath $cand -PathType Container)) {
                $saveDirs += $cand
            }
        }
    }
    $seenNames = @{}
    foreach ($dir in $saveDirs) {
        Get-ChildItem -LiteralPath $dir -File | Where-Object { $_.Extension -in '.asd', '.rsm', '.msk' } | ForEach-Object {
            if (-not $seenNames.ContainsKey($_.Name)) {
                $seenNames[$_.Name] = $true
                $saveFiles += $_
            }
        }
    }
}

# Collect optional User/ custom characters
$userFiles = @()
if ($IncludeUserCharacters -or $IncludePrinnyMod) {
    $userDirs = @()
    if (-not [string]::IsNullOrWhiteSpace($SaveSourceDir)) {
        $customUser = Join-Path $SaveSourceDir 'User'
        if (Test-Path -LiteralPath $customUser -PathType Container) { $userDirs += $customUser }
    }
    if ($IncludeUserCharacters) {
        foreach ($cand in @(
            (Join-Path $SourceDir 'SaveData\User'),
            (Join-Path $SourceDir '附件\User')
        )) {
            if (Test-Path -LiteralPath $cand -PathType Container) { $userDirs += $cand }
        }
    }
    if ($IncludePrinnyMod) {
        $prinnyUser = Join-Path $SourceDir '普利尼MOD备份\[20.11.27.V3] 普利尼MOD\User'
        if (Test-Path -LiteralPath $prinnyUser -PathType Container) { $userDirs += $prinnyUser }
    }
    $seenUser = @{}
    foreach ($dir in $userDirs) {
        Get-ChildItem -LiteralPath $dir -File | Where-Object { $_.Extension -in '.png', '.txt' } | ForEach-Object {
            if (-not $seenUser.ContainsKey($_.Name)) {
                $seenUser[$_.Name] = $true
                $userFiles += $_
            }
        }
    }
}

Write-Host "Source   : $SourceDir"
Write-Host "Output   : $OutputDir"
Write-Host "Identity : xsystem4/$scriptIdentity"
$planList = @($plan)
$saveList = @($saveFiles)
$userList = @($userFiles)
Write-Host ("Payload  : {0} runtime files, {1:N2} GB ({2:N0} bytes)" -f $planList.Count, ($totalBytes / 1GB), $totalBytes)
foreach ($entry in $planList) {
    Write-Host ("  - {0,-24} {1,12:N0} bytes" -f $entry.RelativePath, $entry.SizeBytes)
}
Write-Host ("Saves    : {0} file(s)" -f $saveList.Count)
foreach ($f in $saveList) { Write-Host ("  - {0} ({1:N0} bytes)" -f $f.Name, $f.Length) }
Write-Host ("User     : {0} file(s)" -f $userList.Count)
foreach ($f in $userList) { Write-Host ("  - User/{0} ({1:N0} bytes)" -f $f.Name, $f.Length) }

$xsys4rcContent = "encoding = `"gbk`"`n"

if ($DryRun) {
    Write-Host "DryRun: would generate .xsys4rc (`encoding = `"gbk`"`), SaveData/, and savedata/xsystem4/$scriptIdentity/."
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

# Stage saves and custom User characters into BOTH SaveData/ (PC-friendly)
# and savedata/xsystem4/<identity>/ (Aether runtime save_dir).
$targetSaveRoots = @(
    (Join-Path $OutputDir 'SaveData')
)
if ($scriptIdentity) {
    $targetSaveRoots += (Join-Path $OutputDir "savedata\xsystem4\$scriptIdentity")
}

foreach ($saveRoot in $targetSaveRoots) {
    if ($saveList.Count -gt 0) {
        New-Item -ItemType Directory -Path $saveRoot -Force | Out-Null
        foreach ($f in $saveList) {
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $saveRoot $f.Name) -Force
        }
    }
    if ($userList.Count -gt 0) {
        $userDst = Join-Path $saveRoot 'User'
        New-Item -ItemType Directory -Path $userDst -Force | Out-Null
        foreach ($f in $userList) {
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $userDst $f.Name) -Force
        }
    }
    if ($saveList.Count -gt 0 -or $userList.Count -gt 0) {
        Write-Host "Staged $($saveList.Count) save(s) and $($userList.Count) User file(s) -> $saveRoot"
    }
}

Write-Host "Done. Copy '$OutputDir' (or place its contents) directly into iPhone Files -> On My iPhone -> 多娜多娜."
