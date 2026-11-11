<#
  Agenda o pipeline no Agendador de Tarefas do Windows (todo dia às 06:00).

  Uso (PowerShell, na pasta do projeto):
      .\agendar_pipeline.ps1                     # agenda só o pipeline
      .\agendar_pipeline.ps1 -SimularChegada     # modo demonstração: a cada dia "chega" um mês novo
      .\agendar_pipeline.ps1 -Remover            # remove o agendamento

  Depois de agendado, teste na hora com:
      Start-ScheduledTask -TaskName "RadarPerdas-Pipeline"

  O resultado de cada execução fica em logs\ e na tabela dw.LogExecucao (página "Pipeline" do Power BI).
#>
param(
    [switch]$SimularChegada,
    [switch]$Remover,
    [string]$Horario = "06:00"
)

$nome = "RadarPerdas-Pipeline"
$pasta = $PSScriptRoot

if ($Remover) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false
    Write-Host "Agendamento '$nome' removido."
    return
}

$python = (Get-Command python -ErrorAction Stop).Source
$comando = "`"$python`" src\pipeline.py"
if ($SimularChegada) {
    $comando = "`"$python`" src\simular_chegada.py --meses 1 && $comando"
}

$acao = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $comando" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -Daily -At $Horario
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Radar de Perdas: carga diária dos arquivos de entrada no SQL Server e cálculo do score." -Force | Out-Null

Write-Host "Agendado: '$nome' todo dia às $Horario"
Write-Host "Comando: $comando"
