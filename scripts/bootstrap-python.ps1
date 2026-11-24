# Project-local CPython; does not require any preinstalled Python or package manager.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimeRoot = Join-Path $projectRoot '.runtime'
$pythonRoot = Join-Path $runtimeRoot 'python-3.10.20'
$pythonExe = Join-Path $pythonRoot 'python.exe'
$venvRoot = Join-Path $projectRoot '.venv'
$archive = Join-Path $runtimeRoot 'cpython-3.10.20-20260303-windows-x64.tar.gz'
# Astral python-build-standalone release asset and GitHub-published SHA-256.
$downloadUrl = 'https://github.com/astral-sh/python-build-standalone/releases/download/20260303/cpython-3.10.20%2B20260303-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$expectedHash = '738f9a7f046405947748558acf7c24a087baf7a7cb68bf791d240c8c942ba2a0'
$lock = $null

function Test-Archive {
    return (Test-Path -LiteralPath $archive -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -eq $expectedHash)
}

function Assert-Python([string]$executable) {
    & $executable -I -X utf8 -c "import sys, struct, ssl, sqlite3, venv, ensurepip; assert sys.version_info[:3] == (3, 10, 20) and struct.calcsize('P') == 8"
    if ($LASTEXITCODE -ne 0) { throw 'Project-local Python validation failed.' }
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    # Prevent two simultaneous first launches from downloading/extracting together.
    $lock = [IO.File]::Open((Join-Path $runtimeRoot 'python-bootstrap.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if (Test-Path -LiteralPath $venvRoot) {
        throw 'A .venv already exists. Keep it, or rename it before preparing a new environment.'
    }
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        if (Test-Path -LiteralPath $pythonRoot) {
            throw 'The local Python directory is incomplete. Rename .runtime/python-3.10.20 and retry.'
        }
        $tar = Get-Command tar.exe -ErrorAction Stop
        if (-not (Test-Archive)) {
            Write-Host 'Downloading pinned Python 3.10.20 (Windows x64, about 22 MB)...'
            $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
            if ($curl) {
                & $curl.Source --fail --location --retry 3 --connect-timeout 30 --output $archive $downloadUrl
                if ($LASTEXITCODE -ne 0) { throw 'Python download failed. Check your connection to GitHub and retry.' }
            } else {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $archive
            }
        }
        if (-not (Test-Archive)) { throw 'Python archive SHA-256 mismatch. Nothing was extracted. Run again to download a fresh copy.' }
        Write-Host 'SHA-256 verified. Extracting Python...'
        $stage = Join-Path $runtimeRoot ('python-extract-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage | Out-Null
        # Windows tar may misdecode non-ASCII arguments. Use ASCII relative paths
        # from the runtime directory so Chinese/space-containing project paths work.
        Push-Location -LiteralPath $runtimeRoot
        try {
            & $tar.Source -xzf ([IO.Path]::GetFileName($archive)) -C ([IO.Path]::GetFileName($stage))
            if ($LASTEXITCODE -ne 0) { throw 'Python extraction failed. Check free disk space and retry.' }
        } finally {
            Pop-Location
        }
        $extracted = Join-Path $stage 'python'
        Assert-Python (Join-Path $extracted 'python.exe')
        # Verify both resolved paths before moving the extracted directory.
        $boundary = [IO.Path]::GetFullPath($runtimeRoot) + [IO.Path]::DirectorySeparatorChar
        foreach ($target in @($extracted, $pythonRoot)) {
            if (-not [IO.Path]::GetFullPath($target).StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Unsafe Python installation path.'
            }
        }
        Move-Item -LiteralPath $extracted -Destination $pythonRoot
    }
    Assert-Python $pythonExe
    Write-Host 'Creating .venv with project-local Python...'
    & $pythonExe -I -X utf8 -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed. Rename the incomplete .venv before retrying.' }
    Assert-Python (Join-Path $venvRoot 'Scripts/python.exe')
    Write-Host 'Project-local Python and .venv are ready.'
} catch {
    [Console]::Error.WriteLine('Python setup failed: ' + $_.Exception.Message)
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
}
