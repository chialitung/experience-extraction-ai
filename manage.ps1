#!/usr/bin/env pwsh
<#
.SYNOPSIS
    经验萃取AI系统 - 项目进程管理脚本
.DESCRIPTION
    一键启动、停止、重启前后端服务，自动检测并清理重复/残留进程。
    后端: FastAPI (uvicorn) @ 端口 8000
    前端: Vite (React)   @ 端口 5173
.PARAMETER Command
    要执行的命令: start / stop / restart / status / kill / logs
    不传参数时默认为 start
.EXAMPLE
    .\manage.ps1
    .\manage.ps1 start
    .\manage.ps1 stop
    .\manage.ps1 restart
    .\manage.ps1 status
    .\manage.ps1 kill
    .\manage.ps1 logs backend
    .\manage.ps1 logs frontend
#>
param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "kill", "logs")]
    [string]$Command = "start",

    [Parameter(Position=1)]
    [ValidateSet("backend", "frontend", "all")]
    [string]$Target = "all"
)

# ==================== 配置区 ====================
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$LogDir      = Join-Path $ProjectRoot ".logs"

$BackendPort  = 8000
$FrontendPort = 5173

$BackendLog  = Join-Path $LogDir "backend.log"
$FrontendLog = Join-Path $LogDir "frontend.log"
$BackendPidFile  = Join-Path $LogDir "backend.pid"
$FrontendPidFile = Join-Path $LogDir "frontend.pid"

# 颜色定义
$ColorInfo    = "Cyan"
$ColorSuccess = "Green"
$ColorWarn    = "Yellow"
$ColorError   = "Red"
$ColorDim     = "DarkGray"

# ==================== 工具函数 ====================

function Ensure-LogDir {
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
}

function Write-Info    { param([string]$msg) Write-Host "[INFO]    $msg" -ForegroundColor $ColorInfo }
function Write-Success { param([string]$msg) Write-Host "[OK]      $msg" -ForegroundColor $ColorSuccess }
function Write-Warn    { param([string]$msg) Write-Host "[WARN]    $msg" -ForegroundColor $ColorWarn }
function Write-Error   { param([string]$msg) Write-Host "[ERROR]   $msg" -ForegroundColor $ColorError }
function Write-Dim     { param([string]$msg) Write-Host "          $msg" -ForegroundColor $ColorDim }

function Get-ProcessByPort {
    param([int]$Port)
    $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING\s+(\d+)"
    foreach ($line in $lines) {
        $match = [regex]::Match($line, "LISTENING\s+(\d+)")
        if ($match.Success) {
            $pidVal = [int]$match.Groups[1].Value
            try {
                $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
                if ($proc) { return $proc }
            } catch {
                continue
            }
        }
    }
    return $null
}

function Get-ProcessByPidFile {
    param([string]$PidFile)
    if (Test-Path $PidFile) {
        $pidVal = Get-Content $PidFile -Raw
        if ($pidVal -match '^\d+$') {
            try {
                return Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
            } catch {
                return $null
            }
        }
    }
    return $null
}

function Get-RelatedProcesses {
    $results = @()
    $seenIds = @{}

    # 通过端口查找
    $backendProc  = Get-ProcessByPort -Port $BackendPort
    $frontendProc = Get-ProcessByPort -Port $FrontendPort

    if ($backendProc) {
        $results += @{ Name = "backend";  Process = $backendProc; Source = "port:$BackendPort" }
        $seenIds[$backendProc.Id] = $true
    }
    if ($frontendProc) {
        $results += @{ Name = "frontend"; Process = $frontendProc; Source = "port:$FrontendPort" }
        $seenIds[$frontendProc.Id] = $true
    }

    # 通过PID文件查找
    $backendPidProc  = Get-ProcessByPidFile -PidFile $BackendPidFile
    $frontendPidProc = Get-ProcessByPidFile -PidFile $FrontendPidFile

    $backendPortId = 0
    if ($backendProc) { $backendPortId = $backendProc.Id }
    $frontendPortId = 0
    if ($frontendProc) { $frontendPortId = $frontendProc.Id }

    if ($backendPidProc -and $backendPidProc.Id -ne $backendPortId) {
        $results += @{ Name = "backend";  Process = $backendPidProc; Source = "pidfile" }
        $seenIds[$backendPidProc.Id] = $true
    }
    if ($frontendPidProc -and $frontendPidProc.Id -ne $frontendPortId) {
        $results += @{ Name = "frontend"; Process = $frontendPidProc; Source = "pidfile" }
        $seenIds[$frontendPidProc.Id] = $true
    }

    # 通过命令行特征查找（兜底）
    $allProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and (
            ($_.CommandLine -match "uvicorn\s+main:app") -or
            ($_.CommandLine -match "vite\b") -or
            ($_.CommandLine -match "node.*vite") -or
            ($_.CommandLine -match "python.*main:app")
        )
    }
    foreach ($p in $allProcesses) {
        if (-not $seenIds.ContainsKey($p.ProcessId)) {
            $svc = "frontend"
            if ($p.CommandLine -match "uvicorn|python") { $svc = "backend" }
            $procObj = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
            if ($procObj) {
                $results += @{ Name = $svc; Process = $procObj; Source = "cmdline" }
                $seenIds[$p.ProcessId] = $true
            }
        }
    }

    return $results | Where-Object { $_.Process -ne $null }
}

function Kill-RelatedProcesses {
    param([string]$Reason = "cleanup")
    $procs = Get-RelatedProcesses
    if (-not $procs) {
        Write-Dim "未发现需要清理的进程"
        return
    }

    Write-Warn "发现 $($procs.Count) 个相关进程 (原因: $Reason):"
    foreach ($item in $procs) {
        $p = $item.Process
        $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue
        $cmdline = "N/A"
        if ($cmdlineObj) { $cmdline = $cmdlineObj.CommandLine }
        Write-Host "          PID=$($p.Id) [$($item.Name)] 来源=$($item.Source)" -NoNewline
        Write-Host "  $cmdline" -ForegroundColor $ColorDim
    }

    foreach ($item in $procs) {
        $p = $item.Process
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction Stop
            Write-Success "已终止 PID=$($p.Id) [$($item.Name)]"
        } catch {
            Write-Error "终止 PID=$($p.Id) 失败: $_"
        }
    }

    # 清理PID文件
    if (Test-Path $BackendPidFile)  { Remove-Item $BackendPidFile -Force }
    if (Test-Path $FrontendPidFile) { Remove-Item $FrontendPidFile -Force }
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSec = 30,
        [string]$ServiceName
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        $proc = Get-ProcessByPort -Port $Port
        if ($proc) {
            Write-Success "$ServiceName 已在端口 $Port 启动 (PID=$($proc.Id))"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Error "$ServiceName 在 ${TimeoutSec}s 内未能在端口 $Port 启动"
    return $false
}

function Start-Backend {
    Write-Info "启动后端服务..."
    Ensure-LogDir

    # 检查端口占用
    $existing = Get-ProcessByPort -Port $BackendPort
    if ($existing) {
        Write-Warn "端口 $BackendPort 已被 PID=$($existing.Id) 占用，准备清理..."
        Kill-RelatedProcesses -Reason "port conflict"
    }

    # 检查虚拟环境
    $venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
    $pythonCmd = "python"
    if (Test-Path $venvPython) { $pythonCmd = $venvPython }

    # 构建启动命令（用单引号包裹路径避免嵌套引号地狱）
    $cmd = "cd '$BackendDir'; & '$pythonCmd' -m uvicorn main:app --host 0.0.0.0 --port $BackendPort --reload 2>&1 | Tee-Object -FilePath '$BackendLog' -Append"

    # 在新窗口中启动（优先用 pwsh，回退到 powershell）
    $shell = "powershell.exe"
    if (Get-Command "pwsh.exe" -ErrorAction SilentlyContinue) { $shell = "pwsh.exe" }
    $proc = Start-Process -FilePath $shell -ArgumentList "-NoExit","-Command",$cmd -PassThru

    if ($proc) {
        $proc.Id | Out-File $BackendPidFile -Encoding utf8 -NoNewline
        Write-Success "后端进程已创建 (PID=$($proc.Id))"
        Wait-ForPort -Port $BackendPort -TimeoutSec 30 -ServiceName "后端"
    } else {
        Write-Error "后端进程启动失败"
    }
}

function Start-Frontend {
    Write-Info "启动前端服务..."
    Ensure-LogDir

    # 检查端口占用
    $existing = Get-ProcessByPort -Port $FrontendPort
    if ($existing) {
        Write-Warn "端口 $FrontendPort 已被 PID=$($existing.Id) 占用，准备清理..."
        Kill-RelatedProcesses -Reason "port conflict"
    }

    # 构建启动命令
    $cmd = "cd '$FrontendDir'; npm run dev 2>&1 | Tee-Object -FilePath '$FrontendLog' -Append"

    # 在新窗口中启动（优先用 pwsh，回退到 powershell）
    $shell = "powershell.exe"
    if (Get-Command "pwsh.exe" -ErrorAction SilentlyContinue) { $shell = "pwsh.exe" }
    $proc = Start-Process -FilePath $shell -ArgumentList "-NoExit","-Command",$cmd -PassThru

    if ($proc) {
        $proc.Id | Out-File $FrontendPidFile -Encoding utf8 -NoNewline
        Write-Success "前端进程已创建 (PID=$($proc.Id))"
        Wait-ForPort -Port $FrontendPort -TimeoutSec 30 -ServiceName "前端"
    } else {
        Write-Error "前端进程启动失败"
    }
}

function Show-Status {
    Write-Info "服务状态检查"
    $any = $false

    # 后端状态
    $backendProc = Get-ProcessByPort -Port $BackendPort
    if ($backendProc) {
        Write-Success "后端 运行中  PID=$($backendProc.Id)  端口=$BackendPort"
        $any = $true
    } else {
        Write-Warn "后端 未运行"
    }

    # 前端状态
    $frontendProc = Get-ProcessByPort -Port $FrontendPort
    if ($frontendProc) {
        Write-Success "前端 运行中  PID=$($frontendProc.Id)  端口=$FrontendPort"
        $any = $true
    } else {
        Write-Warn "前端 未运行"
    }

    # 其他相关进程
    $others = Get-RelatedProcesses
    $backendId = 0
    if ($backendProc) { $backendId = $backendProc.Id }
    $frontendId = 0
    if ($frontendProc) { $frontendId = $frontendProc.Id }
    $extra = @()
    foreach ($o in $others) {
        if ($o.Process -and $o.Process.Id -ne $backendId -and $o.Process.Id -ne $frontendId) {
            $extra += $o
        }
    }
    if ($extra.Count -gt 0) {
        Write-Warn "发现额外的相关进程（可能是重复实例）:"
        foreach ($item in $extra) {
            $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$($item.Process.Id)" -ErrorAction SilentlyContinue
            $cmdline = "N/A"
            if ($cmdlineObj) { $cmdline = $cmdlineObj.CommandLine }
            Write-Host "          PID=$($item.Process.Id) [$($item.Name)] 来源=$($item.Source)" -NoNewline
            Write-Host "  $cmdline" -ForegroundColor $ColorDim
        }
    }

    if (-not $any) {
        Write-Dim "当前没有运行中的服务"
    }
}

function Show-BackendLogs {
    Write-Info "后端日志 ($BackendLog):"
    Get-Content $BackendLog -Tail 50 | ForEach-Object { Write-Dim $_ }
}

function Show-FrontendLogs {
    Write-Info "前端日志 ($FrontendLog):"
    Get-Content $FrontendLog -Tail 50 | ForEach-Object { Write-Dim $_ }
}

# ==================== 命令分发 ====================

Write-Host ""
Write-Host "========================================" -ForegroundColor $ColorInfo
Write-Host "  经验萃取AI系统 - 项目管理脚本" -ForegroundColor $ColorInfo
Write-Host "========================================" -ForegroundColor $ColorInfo
Write-Host ""

$cmdLower = $Command.ToLower()

if ($cmdLower -eq "start") {
    Ensure-LogDir
    if ($Target -eq "all" -or $Target -eq "backend")  { Start-Backend }
    if ($Target -eq "all" -or $Target -eq "frontend") { Start-Frontend }
    Write-Host ""
    Write-Success "启动完成！"
    Write-Dim "后端地址: http://localhost:$BackendPort"
    Write-Dim "前端地址: http://localhost:$FrontendPort"
}
elseif ($cmdLower -eq "stop") {
    Kill-RelatedProcesses -Reason "user requested stop"
    Write-Success "已停止所有服务"
}
elseif ($cmdLower -eq "restart") {
    Kill-RelatedProcesses -Reason "restart"
    Start-Sleep -Seconds 2
    if ($Target -eq "all" -or $Target -eq "backend")  { Start-Backend }
    if ($Target -eq "all" -or $Target -eq "frontend") { Start-Frontend }
    Write-Host ""
    Write-Success "重启完成！"
    Write-Dim "后端地址: http://localhost:$BackendPort"
    Write-Dim "前端地址: http://localhost:$FrontendPort"
}
elseif ($cmdLower -eq "status") {
    Show-Status
}
elseif ($cmdLower -eq "kill") {
    Kill-RelatedProcesses -Reason "force kill"
    Write-Success "已强制清理所有相关进程"
}
elseif ($cmdLower -eq "logs") {
    if ($Target -eq "backend" -and (Test-Path $BackendLog)) {
        Show-BackendLogs
    } elseif ($Target -eq "frontend" -and (Test-Path $FrontendLog)) {
        Show-FrontendLogs
    } elseif ($Target -eq "all") {
        Show-BackendLogs
        Show-FrontendLogs
    } else {
        Write-Warn "未找到日志文件"
    }
}
else {
    Write-Error "未知命令: $Command"
    Write-Dim "可用命令: start, stop, restart, status, kill, logs"
}

Write-Host ""
