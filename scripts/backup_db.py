import os
import subprocess
from datetime import datetime
import sys
from pathlib import Path
import glob
import shutil

def find_pg_dump():
    if shutil.which("pg_dump"):
        return "pg_dump"
    pg_paths = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe")
    if pg_paths:
        return sorted(pg_paths, reverse=True)[0]
    return None

def run_backup():
    root_dir = Path(__file__).parent.parent
    backup_dir = root_dir / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = backup_dir / f"galaxy_db_backup_{timestamp}.sql"
    
    pg_dump_exe = find_pg_dump()
    if not pg_dump_exe:
        print("❌ CRÍTICO: No se encontró 'pg_dump.exe' en el sistema.")
        sys.exit(1)
        
    print(f"📦 Iniciando backup usando: {pg_dump_exe}")
    
    # Configuramos el entorno con la contraseña que me diste
    env = os.environ.copy()
    env["PGPASSWORD"] = "Jmax0052"
    
    # Parámetros de conexión explícitos para evitar conflictos con el usuario del sistema
    db_host = "localhost"
    db_port = "5432"
    db_user = "postgres"
    db_name = "galaxy_db"
    
    try:
        cmd = [
            pg_dump_exe,
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "-f", str(filename)
        ]
        subprocess.run(cmd, env=env, check=True)
        print("✅ Backup completado exitosamente. ¡Datos asegurados!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error durante la ejecución del backup: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    run_backup()