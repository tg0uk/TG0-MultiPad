param(
  [string]$PortName = "COM7",
  [int]$BaudRate = 12000000
)

$ErrorActionPreference = "Stop"

function Get-Crc16Xmodem([byte[]]$Data, [int]$Offset, [int]$Length) {
  [int]$crc = 0
  for ($i = 0; $i -lt $Length; $i++) {
    $crc = $crc -bxor ([int]$Data[$Offset + $i] -shl 8)
    for ($bit = 0; $bit -lt 8; $bit++) {
      if (($crc -band 0x8000) -ne 0) {
        $crc = (($crc -shl 1) -bxor 0x1021) -band 0xffff
      } else {
        $crc = ($crc -shl 1) -band 0xffff
      }
    }
  }
  return $crc
}

function Read-Int16Le([byte]$Low, [byte]$High) {
  $value = [int]$Low -bor ([int]$High -shl 8)
  if ($value -ge 32768) {
    return $value - 65536
  }
  return $value
}

$port = New-Object System.IO.Ports.SerialPort $PortName, $BaudRate, "None", 8, "One"
$port.ReadTimeout = 50
$buffer = New-Object byte[] 8192
$rx = New-Object System.Collections.Generic.List[byte]
$validFrames = 0
$resyncSteps = 0
$lastReport = [DateTime]::UtcNow
$lastValidFrames = 0

Write-Host "Opening $PortName at $BaudRate baud..."
Write-Host "Press Ctrl+C to stop."

try {
  $port.Open()
  Write-Host "Opened. Waiting for frames..."

  while ($true) {
    try {
      $count = $port.Read($buffer, 0, $buffer.Length)
      for ($i = 0; $i -lt $count; $i++) {
        $rx.Add($buffer[$i])
      }
    } catch [System.TimeoutException] {
    }

    while ($rx.Count -ge 10) {
      $arr = $rx.ToArray()
      if ((Get-Crc16Xmodem $arr 0 10) -eq 0) {
        $d0 = Read-Int16Le $arr[0] $arr[1]
        $d1 = Read-Int16Le $arr[2] $arr[3]
        $d2 = Read-Int16Le $arr[4] $arr[5]
        $d3 = Read-Int16Le $arr[6] $arr[7]
        $crc = ([int]$arr[8] -shl 8) -bor [int]$arr[9]
        $tag = $d0 -shr 1
        $marker = ($d0 -band 1) -eq 1
        $validFrames++

        if (($validFrames % 200) -eq 1) {
          Write-Host ("frame={0} tag={1} encoded={2} marker={3} data=[{4}, {5}, {6}, {7}] crc={8}" -f `
            $validFrames, $tag, $d0, $marker, $d0, $d1, $d2, $d3, $crc)
        }

        $rx.RemoveRange(0, 10)
      } else {
        $rx.RemoveAt(0)
        $resyncSteps++
      }
    }

    $now = [DateTime]::UtcNow
    if (($now - $lastReport).TotalSeconds -ge 1.0) {
      $fps = $validFrames - $lastValidFrames
      Write-Host ("stats fps={0} total_frames={1} resync_steps={2} buffered_bytes={3}" -f `
        $fps, $validFrames, $resyncSteps, $rx.Count)
      $lastReport = $now
      $lastValidFrames = $validFrames
    }
  }
} finally {
  if ($port.IsOpen) {
    $port.Close()
  }
  Write-Host "Closed $PortName."
}
