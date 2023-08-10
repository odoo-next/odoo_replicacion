from flask import Flask, render_template, request
from flask import send_file
from flask import redirect, url_for
import subprocess
import configparser
import os
import glob
from datetime import datetime
import logging

app = Flask(__name__)

# Configuración de registro
logging.basicConfig(filename='backup_log.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/')
def index():
    backups = get_backups_list()
    message = request.args.get('message', None)
    error_message = request.args.get('error_message', None)
    return render_template('index.html', backups=backups, message=message, error_message=error_message)



@app.route('/restore/<backup_file>')
def restore(backup_file):
    data = load_config()
    remote_odoo_url = data['server_url']
    admin_password = data['admin_password']

    restore_command = f"curl -F 'master_pwd={admin_password}' -F backup_file=@{backup_file} -F 'copy=true' -F 'name=db3' {remote_odoo_url}/web/database/restore"

    try:
        subprocess.run(restore_command, shell=True, check=True)
        return "Restauración iniciada con éxito."
    except subprocess.CalledProcessError as e:
        error_message = f"Error al restaurar la base de datos: {e}"
        logging.error(error_message)
        return f"Error al restaurar la base de datos: {e}"


def get_backups_list():
    data = load_config()
    backup_dir = data['backup_dir']
    backup_files = glob.glob(f"{backup_dir}/*.zip")
    return [os.path.basename(file) for file in backup_files]


@app.route('/create_backup/')
def create_backup():
    data = load_config()
    admin_password = data['admin_password']
    backup_dir = data['backup_dir']
    databases_to_backup = data['databases_to_backup']
    server_origin = data['local_url']

    try:
        # Ejecutar el comando CURL para respaldar la base de datos
        backup_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={databases_to_backup}' -F 'backup_format=dump' -o {backup_dir}/{databases_to_backup}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip {server_origin}"
        subprocess.run(backup_command, shell=True, check=True)

        # Eliminar los respaldos antiguos, manteniendo solo los 3 más recientes
        backup_files = glob.glob(
            f"{backup_dir}/{databases_to_backup}_backup_*.zip")
        backup_files.sort(key=os.path.getctime, reverse=True)
        for old_backup in backup_files[3:]:
            if os.path.exists(old_backup):
                os.remove(old_backup)
        return redirect(url_for('index', message='Se ha creado correctamente el backup'))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=f"Error al respaldar la base de datos {databases_to_backup}: {e}"))


@app.route('/copy_folder')
def copy_folder():
    data = load_config()
    remote_folder = data['server_folder']
    local_folder = data['local_folder']
    server_user = data['server_user']
    server_ip = data['server_ip']

    rsync_command = f"rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}"
    try:
        subprocess.run(rsync_command, shell=True, check=True)
        return "Carpeta copiada exitosamente."
    except subprocess.CalledProcessError as e:
        error_message = f"Error al copiar la carpeta: {e}"
        logging.error(error_message)
        return f"Error al copiar la carpeta: {e}"
    
@app.route('/download_backup/<backup_file>')
def download_backup(backup_file):
    data = load_config()
    backup_dir = data['backup_dir']
    return send_file(f"{backup_dir}/{backup_file}", as_attachment=True)


def load_config(config_file='config.ini'):
    config = configparser.ConfigParser()

    try:
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
        }
        return data
    except configparser.Error as e:
        raise ValueError(f"Error al cargar la configuración: {e}")


if __name__ == '__main__':
    data=load_config()
    backup_dir = data['backup_dir']
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    app.run(host='0.0.0.0', debug=True)
