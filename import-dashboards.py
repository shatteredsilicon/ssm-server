#!/usr/bin/env python3

# Grafana dashboard importer script.

import base64
import binascii
import hashlib
import json
import os
import random
import shutil
import sqlite3
import string
import subprocess
import sys
import time
import http.client

import requests

GRAFANA_DB_DIR = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/grafana"
GRAFANA_IMG_DR = "/usr/share/grafana/public/img/"
GRAFANA_CONFIG_FILE = "/etc/grafana/grafana.ini"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = SCRIPT_DIR + "/dashboards/"
NEW_VERSION_FILE = os.path.join(SCRIPT_DIR, "VERSION")
OLD_VERSION_FILE = os.path.join(GRAFANA_DB_DIR, "plugins/ssm-app/VERSION")
HOST = "http://127.0.0.1:3000"
LOGO_FILE = "/usr/share/ssm-server/landing-page/img/ssm-logo.png"
FAVICON_FILE = "/usr/share/ssm-server/landing-page/img/fav32.png"
GRAFANA_LOGO_FILE = "/usr/share/ssm-server/landing-page/img/grafana_icon.svg"
GRAFANA_APPLE_TOUCH_ICON_FILE = "/usr/share/ssm-server/landing-page/img/apple-touch-icon.png"
GRAFANA_MASK_ICON_FILE = os.path.join(GRAFANA_IMG_DR, "grafana_mask_icon.svg")
GRAFANA_MSTILE_FILE = os.path.join(GRAFANA_IMG_DR, "mstile-150x150.png")
SSM_APP_NAME = "ssm-app"
SET_OF_TAGS = {
    "QAN": 0,
    "OS": 0,
    "MySQL": 0,
    "MongoDB": 0,
    "PostgreSQL": 0,
    "HA": 0,
    "Cloud": 0,
    "Insight": 0,
    "SSM": 0,
    "Silicon": 0,
    "Alerts": 0
}
PANEL_REPLACE_DICT = {
    'ssm-add-instance-app-panel': 'ssm-add-instance-panel',
    'ssm-qan-app-panel': 'ssm-qan-panel',
    'ssm-qan-settings-app-panel': 'ssm-qan-settings-panel',
    'ssm-remote-instances-panel': 'ssm-monitored-instances-panel',
    'ssm-system-summary-app-panel': 'ssm-system-summary-panel'
}


def grafana_headers(api_key):
    """
    Returns HTTP headers for all requests to Grafana.
    """

    return {
        "Authorization": "Bearer %s"
        % (api_key if isinstance(api_key, str) else api_key.decode(),),
        "Content-Type": "application/json",
    }


def get_api_key():
    """
    Generates a new API key and returns its name, representation for API, and representation for DB.

    Keep in sync with Grafana implementation:
    * https://sourcegraph.com/github.com/grafana/grafana/-/blob/pkg/api/apikey.go
    * https://sourcegraph.com/github.com/grafana/grafana/-/blob/pkg/components/apikeygen/apikeygen.go
    * https://sourcegraph.com/github.com/grafana/grafana/-/blob/pkg/util/encoding.go
    """

    alphanum = string.digits + string.ascii_uppercase + string.ascii_uppercase.lower()
    name = "SSM Import " + "".join(random.choice(alphanum) for _ in range(16))
    key = "".join(random.choice(alphanum) for _ in range(32))
    api_key = base64.b64encode(json.dumps({"k": key, "n": name, "id": 1}).encode())
    db_key = binascii.hexlify(
        hashlib.pbkdf2_hmac("sha256", key.encode(), name.encode(), 10000, 50)
    )
    return (name, api_key, db_key)


def check_dashboards_version():
    with open(NEW_VERSION_FILE, "r") as f:
        new_ver = f.read().strip()

    old_ver = "N/A"
    if os.path.exists(OLD_VERSION_FILE):
        with open(OLD_VERSION_FILE, "r") as f:
            old_ver = f.read().strip()

    if old_ver == new_ver:
        print(" * The dashboards are up-to-date (%s)." % (old_ver,))
        sys.exit(0)


def start_grafana():
    res = None
    if os.path.exists("/usr/bin/supervisorctl"):
        res = subprocess.call(["/usr/bin/supervisorctl", "start", "grafana"])
    else:
        res = subprocess.call(["/bin/systemctl", "start", "grafana-server"])
    print(" * Grafana start: %r." % (res,))


def stop_grafana():
    res = None
    if os.path.exists("/usr/bin/supervisorctl"):
        res = subprocess.call(["/usr/bin/supervisorctl", "stop", "grafana"])
    else:
        res = subprocess.call(["/bin/systemctl", "stop", "grafana-server"])
    print(" * Grafana stop: %r." % (res,))

    # wait for full stop
    time.sleep(5)


def wait_for_grafana_start(api_key):
    sys.stdout.write(" * Waiting for Grafana to start")
    sys.stdout.flush()
    for _ in range(60):
        try:
            requests.get("%s/api/datasources" % HOST, timeout=3, headers=grafana_headers(api_key))
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(1)
        else:
            print()
            return
    print("\n * Grafana is unable to start correctly")
    sys.exit(-1)


def add_api_key(name, db_key):
    con = sqlite3.connect(GRAFANA_DB_DIR + "/grafana.db", isolation_level="EXCLUSIVE")
    cur = con.cursor()

    cur.execute(
        "REPLACE INTO api_key (org_id, name, key, role, created, updated, service_account_id) "
        "VALUES (1, ?, ?, 'Admin', datetime('now'), datetime('now'), 1)",
        (name, db_key),
    )

    con.commit()
    con.close()


def delete_api_key(db_key):
    con = sqlite3.connect(GRAFANA_DB_DIR + "/grafana.db", isolation_level="EXCLUSIVE")
    cur = con.cursor()

    cur.execute("DELETE FROM api_key WHERE key = ?", (db_key,))

    con.commit()
    con.close()


def remove_pmm_dashboards():
    con = sqlite3.connect(GRAFANA_DB_DIR + "/grafana.db", isolation_level="EXCLUSIVE")
    cur = con.cursor()

    cur.execute(
        "DELETE FROM dashboard "
        "WHERE plugin_id = ?",
        ('pmm-app',),
    )

    con.commit()
    con.close()


def fix_cloudwatch_datasource():
    """
    Replaces incorrect CloudWatch datasource stored as JSON string with correct JSON object.
    """

    con = sqlite3.connect(GRAFANA_DB_DIR + "/grafana.db", isolation_level="EXCLUSIVE")
    cur = con.cursor()

    cur.execute("SELECT id, json_data FROM data_source WHERE name = 'CloudWatch'")
    for row in cur.fetchall():
        old = None
        try:
            old = json.loads(row[1])
        except:
            pass

        if not isinstance(old, dict) or 'region' not in old:
            new = {
                "authType": "keys",
                "region": "af-south-1"
            }
            cur.execute(
                "UPDATE data_source SET json_data = ? WHERE id = ?",
                (json.dumps(new), row[0]),
            )

    con.commit()
    con.close()


def import_app(api_key):
    print(" * Importing %r" % (SSM_APP_NAME,))
    data = json.dumps({"enabled": False})
    r = requests.post(
        "%s/api/plugins/%s/settings" % (HOST, SSM_APP_NAME),
        data=data,
        headers=grafana_headers(api_key),
    )
    print(" * Plugin disable result: %r %r" % (r.status_code, r.content))
    if r.status_code != http.client.OK:
        print(" * Cannot dissable %s app" % SSM_APP_NAME)
        sys.exit(-1)

    data = json.dumps({"enabled": True})
    r = requests.post(
        "%s/api/plugins/%s/settings" % (HOST, SSM_APP_NAME),
        data=data,
        headers=grafana_headers(api_key)
    )
    print(" * Plugin enable result: %r %r" % (r.status_code, r.content))
    if r.status_code != http.client.OK:
        print(" * Cannot enable %s app" % SSM_APP_NAME)
        sys.exit(-1)


def add_datasources(api_key):
    r = requests.get("%s/api/datasources" % (HOST,), headers=grafana_headers(api_key))
    print(" * Datasources: %r %r" % (r.status_code, r.content))
    ds = [x["name"] for x in json.loads(r.content)]
    if "Prometheus" not in ds:
        print(" * Adding Prometheus Data Source")
        data = json.dumps(
            {
                "name": "Prometheus",
                "type": "prometheus",
                "jsonData": {"keepCookies": [], "timeInterval": "1s"},
                "url": "http://127.0.0.1:9090/prometheus/",
                "access": "proxy",
                "isDefault": True,
            }
        )
        r = requests.post(
            "%s/api/datasources" % HOST, data=data, headers=grafana_headers(api_key)
        )
        print(r.status_code, r.content)
        if r.status_code != http.client.OK:
            print(" * Cannot add Prometheus Data Source")
            sys.exit(-1)
    else:
        print(" * Modifing Prometheus Data Source")
        r = requests.get(
            "%s/api/datasources/name/Prometheus" % (HOST,),
            headers=grafana_headers(api_key)
        )
        data = json.loads(r.content)
        data["jsonData"]["timeInterval"] = "1s"
        data["readOnly"] = False
        r = requests.put(
            "%s/api/datasources/%i" % (HOST, data["id"]),
            data=json.dumps(data),
            headers=grafana_headers(api_key)
        )
        print(r.status_code, r.content)
        if r.status_code != 200:
            print(" * Cannot modify Prometheus Data Source")
            sys.exit(-1)

    if "CloudWatch" not in ds:
        print(" * Adding CloudWatch Data Source")
        data = json.dumps(
            {
                "name": "CloudWatch",
                "type": "cloudwatch",
                "jsonData": {
                    "authType": "keys",
                    "region": "af-south-1"
                },
                "access": "proxy",
                "isDefault": False,
            }
        )
        r = requests.post(
            "%s/api/datasources" % HOST, data=data, headers=grafana_headers(api_key)
        )
        print(r.status_code, r.content)
        if r.status_code != http.client.OK:
            print(" * Cannot add CloudWatch Data Source")
            sys.exit(-1)

    qan_db_url = "/var/lib/mysql/mysql.sock"
    if "QAN-API" not in ds:
        print(" * QAN-API Data Source")
        data = json.dumps(
            {
                "name": "QAN-API",
                "type": "mysql",
                "url": qan_db_url,
                "access": "proxy",
                "jsonData": {},
                "secureJsonFields": {},
                "database": "ssm",
                "user": "grafana",
                "secureJsonData": {
                    "password": "N9mutoipdtlxutgi9rHIFnjM",
                },
            }
        )
        r = requests.post(
            "%s/api/datasources" % HOST, data=data, headers=grafana_headers(api_key)
        )
        print(r.status_code, r.content)
        if r.status_code != http.client.OK:
            print(" * Cannot add QAN-API Data Source")
            sys.exit(-1)
    else:
        print(" * Modifing QAN-API Data Source")
        r = requests.get(
            "%s/api/datasources/name/QAN-API" % (HOST,),
            headers=grafana_headers(api_key)
        )
        data = json.loads(r.content)
        if "secureJsonData" in data:
            data["secureJsonData"]["password"] = "N9mutoipdtlxutgi9rHIFnjM"
        else:
            data["secureJsonData"] = {"password": "N9mutoipdtlxutgi9rHIFnjM"}
        if "database" in data and data["database"] != "ssm":
            data["database"] = "ssm"
        if "url" not in data or data["url"] != qan_db_url:
            data["url"] = qan_db_url
        r = requests.put(
            "%s/api/datasources/%i" % (HOST, data["id"]),
            data=json.dumps(data),
            headers=grafana_headers(api_key)
        )
        print(r.status_code, r.content)
        if r.status_code != 200:
            print(" * Cannot modify QAN-API Data Source")
            sys.exit(-1)


def copy_app():
    source_dir = "/usr/share/ssm-dashboards/" + SSM_APP_NAME
    dest_dir = "/var/lib/grafana/plugins/" + SSM_APP_NAME
    if os.path.isdir(source_dir):
        print(" * Copying %r" % (SSM_APP_NAME,))
        if not os.path.isdir(os.path.dirname(dest_dir)):
            subprocess.run(["mkdir", "-p", os.path.dirname(dest_dir)])
        shutil.rmtree(dest_dir, True)
        subprocess.run(["cp", "-r", source_dir, dest_dir])


def get_folders(api_key):
    r = requests.get("%s/api/folders" % (HOST,), headers=grafana_headers(api_key))
    for x in json.loads(r.content):
        SET_OF_TAGS[x["title"]] = x["id"]


def add_folders(api_key):
    for folder in list(SET_OF_TAGS.keys()):
        print(" * Creating folder %r" % (folder,))

        data = json.dumps({"title": folder})
        r = requests.post(
            "%s/api/folders" % (HOST), data=data, headers=grafana_headers(api_key)
        )
        print("   * Result: %r %r" % (r.status_code, r.content))
        if r.status_code != http.client.OK:
            continue

        data = json.loads(r.text)
        print("   * Folder ID: %r" % (data["id"]))
        SET_OF_TAGS[folder] = data["id"]


def adjust_dashboards():
    print(" * Adjusting dashboards' folder and data")
    con = sqlite3.connect(GRAFANA_DB_DIR + "/grafana.db", isolation_level="EXCLUSIVE")
    cur = con.cursor()
    cur.execute("SELECT data FROM dashboard WHERE is_folder = 0")
    for row in cur.fetchall():
        try:
            data = json.loads(row[0])
        except:
            continue

        if 'panels' in data and type(data['panels']) is list:
            changed = False
            for i, _ in enumerate(data['panels']):
                if 'type' in data['panels'][i] and data['panels'][i]['type'] in PANEL_REPLACE_DICT:
                    data['panels'][i]['type'] = PANEL_REPLACE_DICT[data['panels'][i]['type']]
                    changed = True

            if changed:
                try:
                    cur.execute(
                        "UPDATE dashboard SET data = ? WHERE uid = ?",
                        (json.dumps(data), data["uid"]),
                    )
                    print("   * Replacing pmm panels in dashboard: %s" % (data["title"],))
                except Exception as err:
                    print("   * Replacing pmm panels in dashboard %s failed: %s" % (data["title"], str(err)))

        try:
            tag = data["tags"][0]
            if tag == "Percona":
                tag = data["tags"][1]
        except:
            continue

        try:
            print(
                "   * Uid: %r, Dashboard: %r, Tags: %r"
                % (data["uid"], data["title"], data["tags"])
            )
            print("   * First Tag: %s" % (tag))
            cur.execute(
                "UPDATE dashboard SET folder_id = ? WHERE uid = ?",
                (SET_OF_TAGS[tag], data["uid"]),
            )
            print("   * Moved to the Folder with Id: %s" % (SET_OF_TAGS[tag]))
        except Exception as err:
            print("   * Moving dashboard %s is failed: %s" % (data["title"], str(err)))

    con.commit()
    con.close()


def set_logos():
    if os.path.isfile(LOGO_FILE) and os.access(LOGO_FILE, os.R_OK):
        print(" * Copying %r to grafana directory %r" % (LOGO_FILE, GRAFANA_IMG_DR))
        subprocess.run(["cp", "-f", LOGO_FILE, GRAFANA_IMG_DR])

    if os.path.isfile(FAVICON_FILE) and os.access(FAVICON_FILE, os.R_OK):
        print(" * Copying %r to grafana directory %r" % (FAVICON_FILE, GRAFANA_IMG_DR))
        subprocess.run(["cp", "-f", FAVICON_FILE, GRAFANA_IMG_DR])

    if os.path.isfile(GRAFANA_LOGO_FILE) and os.access(GRAFANA_LOGO_FILE, os.R_OK):
        print(" * Copying %r to grafana directory %r" % (GRAFANA_LOGO_FILE, GRAFANA_IMG_DR))
        subprocess.run(["cp", "-f", GRAFANA_LOGO_FILE, GRAFANA_IMG_DR])

    if os.path.isfile(GRAFANA_APPLE_TOUCH_ICON_FILE) and os.access(GRAFANA_APPLE_TOUCH_ICON_FILE, os.R_OK):
        print(" * Copying %r to grafana directory %r" % (GRAFANA_APPLE_TOUCH_ICON_FILE, GRAFANA_IMG_DR))
        subprocess.run(["cp", "-f", GRAFANA_APPLE_TOUCH_ICON_FILE, GRAFANA_IMG_DR])

    if os.path.isfile(GRAFANA_MASK_ICON_FILE) and os.access(GRAFANA_MASK_ICON_FILE, os.W_OK):
        print(" * Removing grafana mask icon %r" % (GRAFANA_MASK_ICON_FILE))
        subprocess.run(["rm", "-f", GRAFANA_MASK_ICON_FILE])

    if os.path.isfile(GRAFANA_MSTILE_FILE) and os.access(GRAFANA_MSTILE_FILE, os.W_OK):
        print(" * Removing grafana mask icon %r" % (GRAFANA_MSTILE_FILE))
        subprocess.run(["rm", "-f", GRAFANA_MSTILE_FILE])


def main():
    print("Grafana database directory: %s" % (GRAFANA_DB_DIR,))
    check_dashboards_version()

    name, api_key, db_key = get_api_key()

    # modify database when Grafana is stopped to avoid a data race
    stop_grafana()
    try:
        copy_app()
        add_api_key(name, db_key)
        fix_cloudwatch_datasource()
    finally:
        start_grafana()

    wait_for_grafana_start(api_key)

    add_datasources(api_key)
    add_folders(api_key)
    get_folders(api_key)
    import_app(api_key)

    stop_grafana()

    remove_pmm_dashboards()
    adjust_dashboards()

    # restart Grafana to load app and set home dashboard below
    start_grafana()
    wait_for_grafana_start(api_key)
    time.sleep(10)

    set_logos()

    # modify database when Grafana is stopped to avoid a data race
    stop_grafana()
    try:
        delete_api_key(db_key)
    finally:
        start_grafana()

    subprocess.run(["cp", "-f", NEW_VERSION_FILE, OLD_VERSION_FILE])


if __name__ == "__main__":
    main()
