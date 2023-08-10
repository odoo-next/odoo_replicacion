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
    local_url = data['local_url']
    admin_password = data['admin_password']
    backup_dir = data['backup_dir']
    backup_file = backup_dir+"/"+backup_file
    nameDB = data['name_database']

    drop_db_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={nameDB}' {local_url}/web/database/drop"
    try:
        subprocess.run(drop_db_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        error_message = f"Error al borrar la base de datos existente: {e}"
        logging.error(error_message)
        return redirect(url_for('index', message=error_message))


    restore_command = f"curl -F 'master_pwd={admin_password}' -F backup_file=@{backup_file} -F 'copy=true' -F 'name={nameDB}' {local_url}/web/database/restore"
    try:
        subprocess.run(restore_command, shell=True, check=True)
        #copy_folder
        copy_folder()
        return redirect(url_for('index', message="Restauración iniciada con éxito."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al restaurar la base de datos: {e}"
        logging.error(error_message)
        return redirect(url_for('index', message=f"Error al restaurar la base de datos: {e}"))



def get_backups_list():
    data = load_config()
    backup_dir = data['backup_dir']
    backup_files = glob.glob(f"{backup_dir}/*.dump")
    
    backups = []
    for file in backup_files:
        backup_name = os.path.basename(file)
        backup_date = get_backup_creation_date(file)  # Nueva función
        backups.append({'name': backup_name, 'date': backup_date})
    
    return backups

def get_backup_creation_date(backup_file):
    return datetime.fromtimestamp(os.path.getctime(backup_file)).strftime('%Y-%m-%d %H:%M:%S')


@app.route('/create_backup/')
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
        subprocess.run(backup_command, shell=True, check=True)

        # Eliminar los respaldos antiguos, manteniendo solo los 3 más recientes
        backup_files = glob.glob(
            f"{backup_dir}/{databases_to_backup}_backup_*.dump")
        backup_files.sort(key=os.path.getctime, reverse=True)
        for old_backup in backup_files[3:]:
            if os.path.exists(old_backup):
                os.remove(old_backup)
        return redirect(url_for('index', message='Se ha creado correctamente el backup'))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=f"Error al respaldar la base de datos {databases_to_backup}: {e}"))


def copy_folder():
    data = load_config()
    remote_folder = data['server_folder']
    local_folder = data['local_folder']
    server_user = data['server_user']
    server_ip = data['server_ip']
    logging.info(f"Se copiará la carpeta {remote_folder} desde el servidor {server_ip} al directorio {local_folder}")
    logging.info(f"Comando a ejecutar: rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}")    
    rsync_command = f"rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}"
    try:
        subprocess.run(rsync_command, shell=True, check=True)
        #sudo chown -R oodoo:odoo /odoo/.local/share
        chown_command = f"sudo chown -R odoo:odoo {local_folder}"
        subprocess.run(chown_command, shell=True, check=True)
        print(f"Comando a ejecutar: rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}")
        return redirect(url_for('index', message= "Carpeta copiada exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al copiar la carpeta: {e}"
        logging.error(error_message)
        return redirect(url_for('index', message=f"Error al copiar la carpeta: {e}"))


@app.route('/download_backup/<backup_file>')
def download_backup(backup_file):
    data = load_config()
    backup_dir = data['backup_dir']
    return send_file(f"{backup_dir}/{backup_file}", as_attachment=True)




@app.route('/restart_odoo')
def restart_odoo():
    try:
        subprocess.run(['sudo', 'service', 'odoo-server', 'restart'], check=True)
        return redirect(url_for('index', message="Odoo reiniciado exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al reiniciar Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


@app.route('/stop_odoo')
def stop_odoo():
    try:
        subprocess.run(['sudo', 'service', 'odoo-server', 'stop'], check=True)
        return redirect(url_for('index', message="Odoo detenido exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al detener Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


@app.route('/start_odoo')
def start_odoo():
    try:
        subprocess.run(['sudo', 'service', 'odoo-server', 'start'], check=True)
        return redirect(url_for('index', message="Odoo iniciado exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al iniciar Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


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
            'name_database': config.get('Server', 'NameDataBase'),
        }
        return data
    except configparser.Error as e:
        raise ValueError(f"Error al cargar la configuración: {e}")


if __name__ == '__main__':
    data = load_config()
    backup_dir = data['backup_dir']
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    app.run(host='0.0.0.0', debug=True)
