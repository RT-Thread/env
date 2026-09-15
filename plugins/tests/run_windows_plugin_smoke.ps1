[CmdletBinding()]
param(
    [string]$LogRoot,
    [switch]$Worker,
    [switch]$Status,
    [switch]$Stop,
    [string]$TaskName
)

$ErrorActionPreference = 'Stop'
$repository = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

if (-not $LogRoot) {
    $runId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), ([Guid]::NewGuid().ToString('N').Substring(0, 8))
    $LogRoot = Join-Path $env:TEMP ('env-plugin-windows-' + $runId)
}
$LogRoot = [System.IO.Path]::GetFullPath($LogRoot)

$statusPath = Join-Path $LogRoot 'status.json'
$summaryPath = Join-Path $LogRoot 'summary.json'
$runnerLogPath = Join-Path $LogRoot 'runner.log'
$runnerPidPath = Join-Path $LogRoot 'runner.pid'
$launchPath = Join-Path $LogRoot 'launch.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Write-AtomicJsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $temporary = '{0}.{1}.tmp' -f $Path, [Guid]::NewGuid().ToString('N')
    try {
        $json = $Value | ConvertTo-Json -Depth 12
        [System.IO.File]::WriteAllText($temporary, $json, $script:utf8)
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } catch {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

if ($Status) {
    $current = Read-JsonFile $statusPath
    if ($null -eq $current) {
        $current = Read-JsonFile $launchPath
        if ($null -eq $current) {
            Write-Error ('No valid status file: {0}' -f $statusPath)
            exit 2
        }
    }
    $workerAlive = $false
    if ($current.pid) {
        $workerProcess = Get-Process -Id ([int]$current.pid) -ErrorAction SilentlyContinue
        $workerAlive = $null -ne $workerProcess
    }
    $taskState = $null
    if ($current.task_name) {
        $scheduledTask = Get-ScheduledTask -TaskName ([string]$current.task_name) -ErrorAction SilentlyContinue
        if ($scheduledTask) {
            $taskState = [string]$scheduledTask.State
        }
    }
    $observed = [ordered]@{}
    foreach ($property in $current.PSObject.Properties) {
        $observed[$property.Name] = $property.Value
    }
    $observed.observed_at = (Get-Date).ToString('o')
    $observed.worker_alive = $workerAlive
    $observed.task_state = $taskState
    $observed.stale = ([string]$current.state -eq 'running' -and -not $workerAlive)
    $observed | ConvertTo-Json -Depth 12
    exit 0
}

if ($Stop) {
    $statusValue = Read-JsonFile $statusPath
    $launchValue = Read-JsonFile $launchPath
    $taskToStop = $TaskName
    if (-not $taskToStop -and $statusValue -and $statusValue.task_name) {
        $taskToStop = [string]$statusValue.task_name
    }
    if (-not $taskToStop -and $launchValue -and $launchValue.task_name) {
        $taskToStop = [string]$launchValue.task_name
    }
    if ($taskToStop) {
        Stop-ScheduledTask -TaskName $taskToStop -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskToStop -Confirm:$false -ErrorAction SilentlyContinue
    }
    $pidValue = if ($statusValue) { $statusValue.pid } else { $null }
    if (-not $pidValue -and (Test-Path -LiteralPath $runnerPidPath -PathType Leaf)) {
        $rawPid = Get-Content -LiteralPath $runnerPidPath -Raw
        if ($rawPid -match '^\d+$') {
            $pidValue = [int]$rawPid
        }
    }
    if ($pidValue) {
        Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
    }
    Write-Output ('Stop requested for {0}' -f $LogRoot)
    exit 0
}

if (-not $Worker) {
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    if (-not $TaskName) {
        $TaskName = 'EnvPluginSmoke-' + [Guid]::NewGuid().ToString('N')
    }
    $powershellExecutable = Join-Path $PSHOME 'powershell.exe'
    $actionArguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -LogRoot "{1}" -Worker -TaskName "{2}"' -f $PSCommandPath, $LogRoot, $TaskName
    $launchPayload = [ordered]@{
        schema = 1
        state = 'registered'
        task_name = $TaskName
        script = $PSCommandPath
        powershell = $powershellExecutable
        repository = $repository
        log_root = $LogRoot
        launcher_pid = $PID
        started_at = (Get-Date).ToString('o')
    }
    try {
        $action = New-ScheduledTaskAction -Execute $powershellExecutable -Argument $actionArguments
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -User $env:USERNAME -RunLevel Limited -Force | Out-Null
        Write-AtomicJsonFile -Path $launchPath -Value $launchPayload
        Start-ScheduledTask -TaskName $TaskName
        $launchPayload.state = 'started'
        $launchPayload.started_task_at = (Get-Date).ToString('o')
        Write-AtomicJsonFile -Path $launchPath -Value $launchPayload
    } catch {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        $launchPayload.state = 'launch_failed'
        $launchPayload.error = $_.Exception.Message
        try { Write-AtomicJsonFile -Path $launchPath -Value $launchPayload } catch { }
        throw
    }
    Write-Output ('Started Windows plugin smoke worker through Task Scheduler.')
    Write-Output ('Task: {0}' -f $TaskName)
    Write-Output ('LogRoot: {0}' -f $LogRoot)
    Write-Output ('Status: {0}' -f $statusPath)
    exit 0
}

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$python = (Get-Command python -ErrorAction Stop).Source
$workspace = Join-Path $LogRoot 'workspace'
$distribution = Join-Path $LogRoot 'distribution'
$envRoot = Join-Path $LogRoot 'env-root'
$projectWorkspace = Join-Path $LogRoot 'project-workspace'
New-Item -ItemType Directory -Path $workspace,$distribution,$envRoot,$projectWorkspace -Force | Out-Null
$results = New-Object System.Collections.Generic.List[object]
$overall = 0
$startedAt = Get-Date
$currentName = ''
$currentIndex = 0
$totalSteps = 0
$script:overall = $overall
$script:startedAt = $startedAt
$script:currentName = $currentName
$script:currentIndex = $currentIndex
$script:totalSteps = $totalSteps
$script:taskName = $TaskName
$script:results = $results
[int]$PID | Set-Content -LiteralPath $runnerPidPath -Encoding ASCII

function Append-Text {
    param([string]$Path,[string]$Text)
    [System.IO.File]::AppendAllText($Path, $Text + [Environment]::NewLine, $utf8)
}

function Write-RunnerLog {
    param([string]$Message)
    Append-Text $runnerLogPath ('[{0}] {1}' -f (Get-Date).ToString('o'), $Message)
}

function Write-Status {
    param(
        [string]$State = 'running',
        [int]$ExitCode = -1,
        [string]$Message = ''
    )
    $now = (Get-Date).ToString('o')
    $payload = [ordered]@{
        schema = 1
        pid = $PID
        task_name = $script:taskName
        state = $State
        exit_code = $ExitCode
        message = $Message
        current = $script:currentName
        completed = $script:currentIndex
        total = $script:totalSteps
        started_at = $script:startedAt.ToString('o')
        updated_at = $now
        heartbeat = $now
        log_root = $LogRoot
    }
    try {
        Write-AtomicJsonFile -Path $statusPath -Value $payload
    } catch {
        Write-RunnerLog ('status write failed: ' + $_.Exception.Message)
    }
}

function Quote-WindowsArgument {
    param([string]$Value)
    if ($null -eq $Value -or $Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $slashes++
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * ($slashes * 2 + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) {
            [void]$builder.Append(('\' * $slashes))
            $slashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($slashes -gt 0) {
        [void]$builder.Append(('\' * ($slashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $repository,
        [hashtable]$Environment = @{}
    )

    $safeName = ($Name -replace '[^A-Za-z0-9_.-]', '_')
    $outputPath = Join-Path $LogRoot ($safeName + '.log')
    $stdoutPath = Join-Path $LogRoot ($safeName + '.stdout.log')
    $stderrPath = Join-Path $LogRoot ($safeName + '.stderr.log')
    $started = Get-Date
    $commandLine = ('"{0}" {1}' -f $FilePath, (($Arguments | ForEach-Object { Quote-WindowsArgument $_ }) -join ' ')).Trim()
    $script:currentName = $Name
    Write-RunnerLog ('START ' + $Name)
    Append-Text $outputPath ('[START] ' + $started.ToString('o'))
    Append-Text $outputPath ('[CWD] ' + $WorkingDirectory)
    Append-Text $outputPath ('[CMD] ' + $commandLine)
    Write-Status -Message ('running ' + $Name)

    $info = New-Object System.Diagnostics.ProcessStartInfo
    $processFilePath = $FilePath
    $processArguments = (($Arguments | ForEach-Object { Quote-WindowsArgument $_ }) -join ' ')
    if ($FilePath -match '\.(cmd|bat)$') {
        $processFilePath = $env:ComSpec
        $commandText = ('"{0}" {1}' -f $FilePath, (($Arguments | ForEach-Object { Quote-WindowsArgument $_ }) -join ' ')).Trim()
        $processArguments = '/d /s /c "' + $commandText + '"'
    }
    $info.FileName = $processFilePath
    $info.Arguments = $processArguments
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($key in $Environment.Keys) {
        if ($null -eq $Environment[$key]) {
            [void]$info.EnvironmentVariables.Remove($key)
        } else {
            $info.EnvironmentVariables[$key] = [string]$Environment[$key]
        }
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    $exitCode = 1
    $stdout = ''
    $stderr = ''
    try {
        if (-not $process.Start()) {
            throw ('could not start process: ' + $FilePath)
        }
        Append-Text $outputPath ('[PID] ' + $process.Id)
        Write-RunnerLog ('PID ' + $process.Id + ' ' + $Name)
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        while (-not $process.HasExited) {
            Start-Sleep -Milliseconds 500
            Write-Status -Message ('running ' + $Name)
        }
        $process.WaitForExit()
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        [System.IO.File]::WriteAllText($stdoutPath, $stdout, $utf8)
        [System.IO.File]::WriteAllText($stderrPath, $stderr, $utf8)
        Append-Text $outputPath '[STDOUT]'
        if ($stdout) { Append-Text $outputPath $stdout.TrimEnd("`r", "`n") }
        Append-Text $outputPath '[STDERR]'
        if ($stderr) { Append-Text $outputPath $stderr.TrimEnd("`r", "`n") }
        $exitCode = $process.ExitCode
    } catch {
        $errorText = $_ | Out-String
        [System.IO.File]::WriteAllText($stderrPath, $errorText, $utf8)
        Append-Text $outputPath '[RUNNER_ERROR]'
        Append-Text $outputPath $errorText.TrimEnd("`r", "`n")
        Write-RunnerLog ('ERROR ' + $Name + ': ' + $_.Exception.Message)
        $exitCode = 1
    } finally {
        $process.Dispose()
    }

    $finished = Get-Date
    $duration = ($finished - $started).TotalSeconds
    Append-Text $outputPath ('[END] ' + $finished.ToString('o'))
    Append-Text $outputPath ('[EXIT] ' + $exitCode)
    Append-Text $outputPath ('[DURATION_SECONDS] ' + $duration)
    $script:results.Add([pscustomobject]@{
        name = $Name
        exit_code = [int]$exitCode
        duration_seconds = [math]::Round($duration, 3)
        output = $outputPath
        stdout = $stdoutPath
        stderr = $stderrPath
    })
    $script:currentIndex++
    if ($exitCode -ne 0) { $script:overall = 1 }
    Write-RunnerLog ('END ' + $Name + ' exit=' + $exitCode)
    Write-Status -Message ('finished ' + $Name) -ExitCode $exitCode
    return [int]$exitCode
}

try {
    $proxyNames = @(
        'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'FTP_PROXY', 'PIP_PROXY',
        'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ftp_proxy',
        'pip_proxy', 'no_proxy'
    )
    foreach ($name in $proxyNames) {
        Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
    }
    $env:NO_PROXY = '127.0.0.1,localhost'
    $env:no_proxy = $env:NO_PROXY

    $excludedPathPattern = '(?i)[\\/]\.env[\\/]\.venv[\\/]Scripts(?:[\\/]|$)'
    $cleanPath = (($env:PATH -split ';') | Where-Object { $_ -and ($_ -notmatch $excludedPathPattern) }) -join ';'
    $testEnvironment = @{ PATH = $cleanPath }
    $steps = @(
        'unittest-plugins.tests.test_launchers',
        'unittest-plugins.tests.test_manifest_package',
        'unittest-plugins.tests.test_epack_cli',
        'unittest-plugins.tests.test_env_cli',
        'unittest-plugins.tests.test_lifecycle',
        'unittest-plugins.tests.test_webui_package',
        'unittest-plugins.tests.test_webui_server',
        'epack-help',
        'epack-validate-build-insight',
        'epack-build-build-insight',
        'epack-inspect-build-insight',
        'epack-build-official',
        'plugin-install-epack',
        'plugin-list',
        'plugin-info',
        'plugin-doctor',
        'installed-epack-init',
        'installed-epack-validate',
        'installed-epack-build',
        'installed-epack-inspect',
        'plugin-disable',
        'plugin-enable',
        'plugin-uninstall'
    )
    $script:totalSteps = $steps.Count
    Write-RunnerLog ('worker started; total steps=' + $totalSteps)
    Write-Status -Message 'worker started'

    $buildInsight = Join-Path $repository 'plugins\examples\build-insight-1.0.0'
    $insightPackage = Join-Path $distribution 'org.rt-thread.build-insight-1.0.0-py3-none-any.epack'
    Invoke-Logged $steps[0] $python @('-m','unittest','plugins.tests.test_launchers') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[1] $python @('-m','unittest','plugins.tests.test_manifest_package') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[2] $python @('-m','unittest','plugins.tests.test_epack_cli') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[3] $python @('-m','unittest','plugins.tests.test_env_cli') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[4] $python @('-m','unittest','plugins.tests.test_lifecycle') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[5] $python @('-m','unittest','plugins.tests.test_webui_package') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[6] $python @('-m','unittest','plugins.tests.test_webui_server') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[7] $python @('-m','plugins.epack.cli','--help') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[8] $python @('-m','plugins.epack.cli','validate',$buildInsight,'--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[9] $python @('-m','plugins.epack.cli','build',$buildInsight,'--output',$distribution,'--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[10] $python @('-m','plugins.epack.cli','inspect',$insightPackage,'--json') -Environment $testEnvironment | Out-Null

    $officialOutput = Join-Path $distribution 'official'
    New-Item -ItemType Directory -Path $officialOutput -Force | Out-Null
    $officialPackage = Join-Path $officialOutput 'org.rt-thread.epack-1.0.0-py3-none-any.epack'
    Invoke-Logged $steps[11] $python @('plugins\epack\build_epack.py','--output',$officialOutput,'--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[12] $python @('env.py','plugin','--env-root',$envRoot,'install',$officialPackage,'--yes','--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[13] $python @('env.py','plugin','--env-root',$envRoot,'list','--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[14] $python @('env.py','plugin','--env-root',$envRoot,'info','org.rt-thread.epack','--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[15] $python @('env.py','plugin','--env-root',$envRoot,'doctor','org.rt-thread.epack','--json') -Environment $testEnvironment | Out-Null

    $epackLauncher = Join-Path $envRoot '.venv\Scripts\epack.cmd'
    Invoke-Logged $steps[16] $epackLauncher @('init','created','--id','org.example.created','--name','Created') -WorkingDirectory $projectWorkspace -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[17] $epackLauncher @('validate','created','--json') -WorkingDirectory $projectWorkspace -Environment $testEnvironment | Out-Null
    $createdOutput = Join-Path $projectWorkspace 'dist'
    $createdPackage = Join-Path $createdOutput 'org.example.created-0.1.0-py3-none-any.epack'
    Invoke-Logged $steps[18] $epackLauncher @('build','created','--output',$createdOutput,'--json') -WorkingDirectory $projectWorkspace -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[19] $epackLauncher @('inspect',$createdPackage,'--json') -WorkingDirectory $projectWorkspace -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[20] $python @('env.py','plugin','--env-root',$envRoot,'disable','org.rt-thread.epack','--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[21] $python @('env.py','plugin','--env-root',$envRoot,'enable','org.rt-thread.epack','--json') -Environment $testEnvironment | Out-Null
    Invoke-Logged $steps[22] $python @('env.py','plugin','--env-root',$envRoot,'uninstall','org.rt-thread.epack','--yes','--json') -Environment $testEnvironment | Out-Null
} catch {
    $script:overall = 1
    Write-RunnerLog ('FATAL ' + $_.Exception.Message)
    Write-Status -State 'failed' -ExitCode 1 -Message $_.Exception.Message
} finally {
    try {
        $finalState = if ($script:overall -eq 0) { 'completed' } else { 'failed' }
        $finalPayload = [ordered]@{
            schema = 1
            state = $finalState
            exit_code = $script:overall
            pid = $PID
            task_name = $script:taskName
            started_at = $script:startedAt.ToString('o')
            finished_at = (Get-Date).ToString('o')
            log_root = $LogRoot
            results = @($script:results.ToArray())
        }
        Write-AtomicJsonFile -Path $summaryPath -Value $finalPayload
    } catch {
        try {
            Write-RunnerLog ('finalization failed: ' + $_.Exception.ToString())
            Write-Status -State 'failed' -ExitCode 1 -Message ('finalization failed: ' + $_.Exception.Message)
        } catch { }
        $script:overall = 1
        $finalState = 'failed'
    }
    if ($finalState) {
        Write-Status -State $finalState -ExitCode $script:overall -Message 'worker finished'
        Write-RunnerLog ('worker finished exit=' + $script:overall)
    }
    if ($script:taskName) {
        Unregister-ScheduledTask -TaskName $script:taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}

exit $script:overall
