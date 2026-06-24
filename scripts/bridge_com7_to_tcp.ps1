param(
  [string]$PortName = "COM7",
  [int]$BaudRate = 12000000,
  [string]$HostAddress = "172.27.156.240",
  [int]$HostPort = 17007,
  [int]$DurationSeconds = 8
)

$ErrorActionPreference = "Stop"

$serial = New-Object System.IO.Ports.SerialPort $PortName, $BaudRate, "None", 8, "One"
$serial.ReadTimeout = 100
$client = New-Object System.Net.Sockets.TcpClient
$buffer = New-Object byte[] 8192
$sent = 0

try {
  Write-Host "Connecting TCP ${HostAddress}:${HostPort}..."
  $client.Connect($HostAddress, $HostPort)
  $stream = $client.GetStream()

  Write-Host "Opening $PortName at $BaudRate baud..."
  $serial.Open()
  Write-Host "Forwarding COM data for $DurationSeconds second(s)..."

  $deadline = [DateTime]::UtcNow.AddSeconds($DurationSeconds)
  while ([DateTime]::UtcNow -lt $deadline) {
    try {
      $count = $serial.Read($buffer, 0, $buffer.Length)
      if ($count -gt 0) {
        try {
          $stream.Write($buffer, 0, $count)
          $sent += $count
        } catch [System.IO.IOException] {
          if ($sent -gt 0) {
            Write-Host "TCP peer closed after bytes_sent=$sent"
            break
          }
          throw
        }
      }
    } catch [System.TimeoutException] {
    }
  }

  Write-Host "COM_TCP_BRIDGE_OK bytes_sent=$sent"
} finally {
  if ($serial.IsOpen) {
    $serial.Close()
  }
  if ($client.Connected) {
    $client.Close()
  }
}
