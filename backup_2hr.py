import subprocess
import configparser
import os
import glob
from datetime import datetime
import logging
logging.basicConfig(filename='backup_log.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def create_backup():
    data = load_config()
    admin_password = data['admin_password']
    backup_dir = data['backup_dir']
    databases_to_backup = data['databases_to_backup']
    server_origin = data['server_url']
    server_origin = server_origin+"/web/database/backup"

    try:
        # Ejecutar el comando CURL para respaldar la base de datos
        backup_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={databases_to_backup}' -F 'backup_format=dump' -o {backup_dir}/{databases_to_backup}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.dump {server_origin}"
        print("Ejecutando el comando CURL para respaldar la base de datos: "+backup_command)
        subprocess.run(backup_command, shell=True, check=True)

        # Eliminar los respaldos antiguos, manteniendo solo los 3 más recientes
        backup_files = glob.glob(
            f"{backup_dir}/{databases_to_backup}_backup_*.dump")
        backup_files.sort(key=os.path.getctime, reverse=True)
        for old_backup in backup_files[8:]:
            if os.path.exists(old_backup):
                os.remove(old_backup)
        logging.info("Respaldo de la base de datos creado correctamente")
    except subprocess.CalledProcessError as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)

def load_config():
    config = configparser.ConfigParser()
    config_file= os.path.join(os.path.dirname(__file__), 'config.ini')
    config.read(config_file)
    data = {
            'admin_password': config.get('Server', 'AdminPassword'),
            'backup_dir': config.get('Server', 'BackupDir'),
            'databases_to_backup': config.get('Server', 'DataBase'),
            'local_url': config.get('Server', 'LocalURL'),
            'local_folder': config.get('Server', 'LocalFolder'),
            'server_url': config.get('Server', 'ServerURL'),
            'server_user': config.get('Server', 'ServerUser'),
            'server_ip': config.get('Server', 'ServerIP'),
            'server_folder': config.get('Server', 'ServerFolder'),
            'name_database': config.get('Server', 'NameDataBase'),
        }
    return data
