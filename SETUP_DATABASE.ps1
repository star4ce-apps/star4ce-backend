# PostgreSQL Database Setup Script
# Run this in PowerShell (as Administrator)

$psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

Write-Host "PostgreSQL Database Setup" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""

# Get password from user
$postgresPassword = Read-Host "Enter PostgreSQL 'postgres' user password"

# Create database and user
Write-Host "Creating database and user..." -ForegroundColor Yellow

$sqlCommands = @"
CREATE DATABASE star4ce_db;
CREATE USER star4ce_user WITH PASSWORD 'star4ce123';
GRANT ALL PRIVILEGES ON DATABASE star4ce_db TO star4ce_user;
"@

# Connect and run commands
$env:PGPASSWORD = $postgresPassword
& $psqlPath -U postgres -c $sqlCommands

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Database created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Granting schema privileges..." -ForegroundColor Yellow
    
    # Grant schema privileges
    $schemaCommands = @"
\c star4ce_db
GRANT ALL ON SCHEMA public TO star4ce_user;
"@
    
    & $psqlPath -U postgres -d star4ce_db -c "GRANT ALL ON SCHEMA public TO star4ce_user;"
    
    Write-Host ""
    Write-Host "✅ Setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Add this to your .env file:" -ForegroundColor Cyan
    Write-Host "DATABASE_URL=postgresql://star4ce_user:star4ce123@localhost:5432/star4ce_db" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Error creating database. Check if database/user already exists." -ForegroundColor Red
}

