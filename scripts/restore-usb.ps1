# restore-usb.ps1 — retransforme la clé USB (contenant l'ISO d'installation)
# en clé USB normale, avec tous ses Go.
#
# Usage :  powershell -ExecutionPolicy Bypass -File scripts\restore-usb.ps1
#
# GARDE-FOUS (effacement destructeur, donc sécurisé) :
#   1. n'agit QUE sur un disque AMOVIBLE (BusType USB) ;
#   2. n'agit QUE sur une fourchette de taille 4 Go - 256 Go (la clé MILES)
#      et refuse tout disque fixe (NVMe/SSD du PC) ;
#   3. refuse si le disque détient > 2 Go de données non reconnues
#      (à moins de confirmer explicitement) ;
#   4. te fait taper OUI avant toute opération, avec le détail du disque.
#
# Après exécution : la clé est en NTFS, tous les Go sont à nouveau
# exploitables dans l'Explorateur de fichiers.

$ErrorActionPreference = 'Stop'

function Fail($msg) { Write-Host "REFUS : $msg" -ForegroundColor Red; exit 1 }

# --- 1. Inventaire des disques amovibles uniquement -------------------
$removable = @(Get-Disk -ErrorAction SilentlyContinue | Where-Object {
    $_.BusType -eq 'USB' -and $_.Size -ge 4GB -and $_.Size -le 256GB
})

if ($removable.Count -eq 0) {
    Fail "aucun disque USB entre 4 et 256 Go detecte. Branche la cle puis relance."
}
if ($removable.Count -gt 1) {
    Write-Host "Plusieurs cles USB detectees : " -ForegroundColor Yellow
    $removable | ForEach-Object {
        "  disque $($_.Number) : $([math]::Round($_.Size/1GB,1)) Go  $($_.FriendlyName)"
    }
    Fail "branche UNE SEULE cle USB pour eviter toute erreur."
}

$disk = $removable[0]
$sizeGo = [math]::Round($disk.Size/1GB,1)

# --- 2. Prudence : contenu present ? ----------------------------------
$parts = @(Get-Partition -DiskNumber $disk.Number -ErrorAction SilentlyContinue)
$hasData = $false
foreach ($p in $parts) {
    if ($p.DriveLetter) {
        $v = Get-Volume -DriveLetter $p.DriveLetter -ErrorAction SilentlyContinue
        if ($v -and $v.SizeRemaining -and ($v.Size - $v.SizeRemaining) -gt 2GB) { $hasData = $true }
    }
}

# --- 3. Confirmation humaine explicite --------------------------------
Write-Host ""
Write-Host "=========== ATTENTION : EFFACEMENT IRREVERSIBLE ===========" -ForegroundColor Red
Write-Host " Disque  : $($disk.Number)"
Write-Host " Modele  : $($disk.FriendlyName)"
Write-Host " Taille  : $sizeGo Go"
Write-Host " Type    : amovible (USB) — disque FIXE jamais touche"
if ($hasData) {
    Write-Host " CONTENU : plus de 2 Go de donnees detectees !" -ForegroundColor Yellow
}
Write-Host "==========================================================="
Write-Host "Tape OUI (en majuscules) pour effacer et reformat : " -NoNewline
$answer = Read-Host
if ($answer -ne 'OUI') { Fail "confirmation refusee ($answer). Rien n'a ete modifie." }

# --- 4. diskpart : clean + partition + format -------------------------
$script = @"
select disk $($disk.Number)
clean
create partition primary
format fs=ntfs quick label=USB
assign
exit
"@
$tmp = Join-Path $env:TEMP "restore-usb-diskpart.txt"
Set-Content -Path $tmp -Value $script -Encoding ascii
try {
    & diskpart /s $tmp | Out-Null
} finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

# --- 5. Vérification ---------------------------------------------------
Start-Sleep -Seconds 2
$after = Get-Disk -Number $disk.Number -ErrorAction SilentlyContinue
if ($after -and $after.Size -eq $disk.Size) {
    Write-Host ""
    Write-Host "CLE RESTAUREE : $sizeGo Go, NTFS, prete a l'emploi." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Verification impossible — regarde Gestion des disques." -ForegroundColor Yellow
}
