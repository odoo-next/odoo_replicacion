from flask import Flask, render_template, request
from flask import send_file
from flask import redirect, url_for
import subprocess
import configparser
import os
import glob
from datetime import datetime
import logging
import shutil
import time


from flask_httpauth import HTTPBasicAuth
app = Flask(__name__)
auth = HTTPBasicAuth()

MASTER_PASSWORD = "Montero25"
MASTER_PASSWORD_RESTORE = "SI"

# Configuración de registro
logging.basicConfig(filename='backup_log.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

@auth.verify_password
def verify_password(username, password):
    return password == MASTER_PASSWORD
"""
Routas de la aplicación
"""


@app.route('/')
@auth.login_required
def index():
    backups = get_backups_list()
    message = request.args.get('message', None)
    error_message = request.args.get('error_message', None)
    return render_template('index.html', backups=backups, message=message, error_message=error_message)


@app.route('/restore/<backup_file>')
@auth.login_required
def restore(backup_file):
    data = load_config()
    local_url = data['local_url']
    admin_password = data['admin_password']
    backup_dir = data['backup_dir']
    backup_file = backup_dir+"/"+backup_file
    nameDB = data['name_database']
    #rename_local_folder(rename_to_backup=True)  # Renombrar antes de restaurar
    print("Renobrado el filestore a filestore_backup")
    # Eliminar la base de datos
    drop_db_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={nameDB}' {local_url}/web/database/drop"
    print(
        f"Eliminando la base de datos {nameDB} con  el comando: {drop_db_command}")

    try:
        subprocess.run(drop_db_command, shell=True, check=True)
        print("Base de datos eliminada exitosamente")
    except:
        pass

    restore_command = f"curl -F 'master_pwd={admin_password}' -F backup_file=@{backup_file} -F 'copy=true' -F 'name={nameDB}' {local_url}/web/database/restore"

    try:
        print(
            f"Restaurando la base de datos {nameDB} con el comando: {restore_command}")
        subprocess.run(restore_command, shell=True, check=True)
        print("Renobrado el filestore a filestore al nombre original")
        # Renombrar después de restaurar y evitar traerme de vuelta todos los archivos del filestore
        #rename_local_folder(rename_to_backup=False)
        print("Copiar la carpeta filestore_ del servidor remoto al servidor local")
        copy_folder()
        return redirect(url_for('index', message="Restauración iniciada con éxito."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al restaurar la base de datos: {e}"
        logging.error(error_message)
        return redirect(url_for('index', message=f"Error al restaurar la base de datos: {e}"))


@app.route('/create_backup/')
@auth.login_required
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
        return redirect(url_for('index', message='Se ha creado correctamente el backup'))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=f"Error al respaldar la base de datos {databases_to_backup}: {e}"))


@app.route('/download_backup/<backup_file>')
@auth.login_required
def download_backup(backup_file):
    data = load_config()
    backup_dir = data['backup_dir']
    return send_file(f"{backup_dir}/{backup_file}", as_attachment=True)


@app.route('/restart_odoo')
@auth.login_required
def restart_odoo():
    try:
        subprocess.run(
            ['sudo', 'service', 'odoo-server', 'restart'], check=True)
        return redirect(url_for('index', message="Odoo reiniciado exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al reiniciar Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


@app.route('/stop_odoo')
@auth.login_required
def stop_odoo():
    try:
        subprocess.run(['sudo', 'service', 'odoo-server', 'stop'], check=True)
        return redirect(url_for('index', message="Odoo detenido exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al detener Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


@app.route('/start_odoo')
@auth.login_required
def start_odoo():
    try:
        subprocess.run(['sudo', 'service', 'odoo-server', 'start'], check=True)
        return redirect(url_for('index', message="Odoo iniciado exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al iniciar Odoo: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))
    

@app.route('/sync_modulos')
@auth.login_required
def sync_modulos():
    try:
        subprocess.run(['rsync', '-avz', '--delete', 'server_user@server_ip:/odoo/Modulos/', '/ruta/de/backups/odoo/Modulos/'], check=True)
        return redirect(url_for('index', message="Sincronización de módulos exitosa."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al sincronizar módulos: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))
    

@app.route('/create_snapshot/')
@auth.login_required
def create_snapshot():
    data = load_config()
    remote_paths = data['remote_snapshot_paths']
    local_snapshot_dir = data['local_snapshot_dir']

    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        snapshot_name = f'snapshot_{timestamp}.zip'
        snapshot_path = os.path.join(local_snapshot_dir, snapshot_name)

        # Copiar archivos del servidor remoto al local
        for remote_path in remote_paths:
            rsync_command = f"rsync -avz --delete {data['server_user']}@{data['server_ip']}:{remote_path} {local_snapshot_dir}"
            subprocess.run(rsync_command, shell=True, check=True)

        # Comprimir los archivos en un archivo ZIP
        shutil.make_archive(os.path.splitext(snapshot_path)[0], 'zip', local_snapshot_dir, snapshot_name)

        # Eliminar archivos individuales copiados
        for remote_path in remote_paths:
            local_path = os.path.join(local_snapshot_dir, os.path.basename(remote_path))
            if os.path.exists(local_path):
                os.remove(local_path)

        # Eliminar snapshots antiguos
        snapshots = get_snapshots_list(local_snapshot_dir)
        if len(snapshots) > 2:
            oldest_snapshot = snapshots[-1]
            os.remove(os.path.join(local_snapshot_dir, oldest_snapshot['name']))

        return redirect(url_for('index', message='Snapshot creado exitosamente.'))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al crear el snapshot: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=error_message))


@app.route('/restore_prod', methods=['GET', 'POST'])
@auth.login_required
def restore_prod():
    if request.method == 'POST':
        master_password = request.form.get('master_password')
        if master_password != MASTER_PASSWORD_RESTORE:
            return redirect(url_for('index', error_message="Contraseña maestra incorrecta."))

        # Resto del código de restauración aquí

    data = load_config()
    #1 crear backup del servidor de respaldo local
    #2 restaurar la base de datos del servidor de respaldo local al servidor de produccion
    #3 copiar la carpeta filestore_ del servidor remoto al servidor local
    admin_password = data['admin_password']
    backup_dir = data['backup_dir']
    databases_to_backup = data['databases_to_backup']
    local_url = data['local_url']
    local_url_backup = local_url+"/web/database/backup"
    server_url = data['server_url']

    backup_file=f"{backup_dir}/{databases_to_backup}_backup_local_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"

    try:
        #1 crear backup del servidor de respaldo local
        backup_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={databases_to_backup}' -F 'backup_format=zip' -o {backup_file} {local_url_backup}"
        print("Ejecutando el comando CURL para respaldar la base de datos: "+backup_command)
        subprocess.run(backup_command, shell=True, check=True)
    except Exception as e:
        error_message = f"Error al respaldar la base de datos {databases_to_backup}: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=f"Error al respaldar la base de datos {databases_to_backup}. Puede que la contraseña MASTER del Servidivor de Producción haya cambiado: {e}"))
    
    try:
        #2 restaurar la base de datos del servidor de respaldo local al servidor de produccion
        drop_db_command = f"curl -X POST -F 'master_pwd={admin_password}' -F 'name={databases_to_backup}' {server_url}/web/database/drop"
        print(
            f"Eliminando la base de datos {databases_to_backup} con  el comando: {drop_db_command}")

        try:
            subprocess.run(drop_db_command, shell=True, check=True)
            print("Base de datos eliminada exitosamente")
        except:
            pass

        # hacer un get a/web/database/manager
        try:
            subprocess.run(f"curl -X GET {server_url}/web/database/manager", shell=True, check=True)     
        except:
            pass

        restore_command = f"curl -F 'master_pwd={admin_password}' -F backup_file=@{backup_file} -F 'copy=true' -F 'name={databases_to_backup}' {server_url}/web/database/restore"
        print(
            f"Restaurando la base de datos {databases_to_backup} con el comando: {restore_command}")
        subprocess.run(restore_command, shell=True, check=True)
        #Eliminar el backup local
        os.remove(backup_file)
    except Exception as e:
        error_message = f"Error al restaurar la base de datos: {e}"
        logging.error(error_message)
        return redirect(url_for('index', error_message=f"Error al restaurar la base de datos: {e}"))
        
    return redirect(url_for('index', message="Restauración en Producción con éxito."))


"""
Metodos Auxiliares
"""

def get_snapshots_list(local_snapshot_dir):
    snapshot_files = glob.glob(os.path.join(local_snapshot_dir, 'snapshot_*.zip'))

    snapshots = []
    for file in snapshot_files:
        snapshot_name = os.path.basename(file)
        snapshot_date = get_snapshot_creation_date(file)
        snapshots.append({'name': snapshot_name, 'date': snapshot_date})

    sorted_snapshots = sorted(snapshots, key=lambda x: x['date'], reverse=True)
    return sorted_snapshots

def get_snapshot_creation_date(snapshot_file):
    return datetime.fromtimestamp(os.path.getctime(snapshot_file)).strftime('%Y-%m-%d %H:%M:%S')

def rename_local_folder(rename_to_backup=False):
    data = load_config()
    local_folder = data['local_folder']
    name_database = data['name_database']
    backup_suffix = '_bk'
    try:
        if rename_to_backup:
            new_folder_name = local_folder + "/" + name_database + backup_suffix
            #borrar la carpeta si existe
            if os.path.exists(new_folder_name):
                shutil.rmtree(new_folder_name)
            os.rename(local_folder + "/" + name_database, new_folder_name)
            return new_folder_name
        else:
            new_folder_name = local_folder + "/" + name_database    
            try:        
                merge_folders(new_folder_name + backup_suffix, new_folder_name)
            except Exception as e:
                logging.error(f"Error al copiar la carpeta: {e}")
            try:
                shutil.rmtree(new_folder_name + backup_suffix)
            except Exception as e:
                logging.error(f"Error al borrar la carpeta: {e}")
            return new_folder_name
    except OSError as e:
        error_message = f"Error : {e}"
        logging.error(error_message)
        raise ValueError(error_message)


def merge_folders(source_folder, destination_folder):
    for item in os.listdir(source_folder):
        source_item = os.path.join(source_folder, item)
        destination_item = os.path.join(destination_folder, item)

        # Si el item es un archivo y no existe en el destino, copiarlo
        if os.path.isfile(source_item) and not os.path.exists(destination_item):
            try:
                shutil.copy2(source_item, destination_item)
                print(f"Copiado: {item}")
            except Exception as e:
                logging.error(f"Error al copiar el archivo: {e}")
            try:
                os.remove(source_item)  # Borrar el archivo del origen
                print(f"Borrado de origen: {item}")
            except Exception as e:
                logging.error(f"Error al borrar el archivo: {e}")
        else:
            print(
                f"El archivo ya existe en destino o no es un archivo: {item}")


def get_backups_list():
    data = load_config()
    backup_dir = data['backup_dir']
    backup_files = glob.glob(f"{backup_dir}/*.dump")

    backups = []
    for file in backup_files:
        backup_name = os.path.basename(file)
        backup_date = get_backup_creation_date(file)  # Nueva función
        backups.append({'name': backup_name, 'date': backup_date})

    sorted_backups = sorted(backups, key=lambda x: x['date'], reverse=True)

    return sorted_backups


def get_backup_creation_date(backup_file):
    return datetime.fromtimestamp(os.path.getctime(backup_file)).strftime('%Y-%m-%d %H:%M:%S')


def copy_folder():
    data = load_config()
    remote_folder = data['server_folder']
    local_folder = data['local_folder']
    server_user = data['server_user']
    server_ip = data['server_ip']
    print(
        f"Se copiará la carpeta {remote_folder} desde el servidor {server_ip} al directorio {local_folder}")
    print(
        f"Comando a ejecutar: rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}")
    rsync_command = f"rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}"
    try:
        subprocess.run(rsync_command, shell=True, check=True)
        # sudo chown -R oodoo:odoo /odoo/.local/share
        chown_command = f"sudo chown -R odoo:odoo {local_folder}"
        subprocess.run(chown_command, shell=True, check=True)
        print(
            f"Comando a ejecutar: rsync -avz --delete {server_user}@{server_ip}:{remote_folder} {local_folder}")
        return redirect(url_for('index', message="Carpeta copiada exitosamente."))
    except subprocess.CalledProcessError as e:
        error_message = f"Error al copiar la carpeta: {e}"
        logging.error(error_message)
        return redirect(url_for('index', message=f"Error al copiar la carpeta: {e}"))


def load_config():
    config = configparser.ConfigParser()
    config_file= os.path.join(os.path.dirname(__file__), 'config.ini')

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
