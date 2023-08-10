import subprocess
import configparser
import os
import glob
from datetime import datetime
import logging

logging.basicConfig(filename='backup_log.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Cargar configuración desde el archivo de configuración
config = configparser.ConfigParser()
config.read('config.ini')

# Obtener los valores de la configuración
admin_password = config.get('Server', 'AdminPassword')
backup_dir = config.get('Server', 'BackupDir')
databases_to_backup = config.get('Server', 'DataBase')
server_origin = config.get('Server', 'ServeURL')


try:
    # Ejecutar el comando CURL para respaldar la base de datos
    backup_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={databases_to_backup}' -F 'backup_format=dump' -o {backup_dir}/{databases_to_backup}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip {server_origin}"
    subprocess.run(backup_command, shell=True, check=True)

    # Eliminar los respaldos antiguos, manteniendo solo los 3 más recientes
    backup_files = glob.glob(f"{backup_dir}/{databases_to_backup}_backup_*.zip")
    backup_files.sort(key=os.path.getctime, reverse=True)
    for old_backup in backup_files[3:]:
            os.remove(old_backup)
except subprocess.CalledProcessError as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)
        print(error_message)


