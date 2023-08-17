#!/bin/bash

set -o errexit

# Add logging
if [ -n "${ENABLE_DEBUG}" ]; then
    set -o xtrace
    exec > >(tee -a /var/log/$(basename $0).log) 2>&1
fi

# Prometheus
if [[ ! "${METRICS_RESOLUTION:-1s}" =~ ^[1-5]s$ ]]; then
    echo "METRICS_RESOLUTION takes only values from 1s to 5s."
    exit 1
fi
sed "s/1s/${METRICS_RESOLUTION:-1s}/" /etc/prometheus.yml > /tmp/prometheus.yml
cat /tmp/prometheus.yml > /etc/prometheus.yml
rm -rf /tmp/prometheus.yml

sed "s/ENV_METRICS_RETENTION/${METRICS_RETENTION:-720h}/" /etc/supervisord.d/ssm.ini > /tmp/ssm.ini
sed -i "s/ENV_MAX_CONNECTIONS/${MAX_CONNECTIONS:-15}/" /tmp/ssm.ini

if [ -n "$METRICS_MEMORY" ]; then
    # Preserve compatibility with existing METRICS_MEMORY variable.
    # https://jira.percona.com/browse/PMM-969
    METRICS_MEMORY_MULTIPLIED=$(( ${METRICS_MEMORY} * 1024 ))
else
    MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes || :)
    TOTAL_MEMORY=$(( $(grep MemTotal /proc/meminfo | awk '{print$2}') * 1024 ))
    MEMORY_AVAIABLE=$(printf "%i\n%i\n" "$MEMORY_LIMIT" "$TOTAL_MEMORY" | sort -n | grep -v "^0$" | head -1)
    METRICS_MEMORY_MULTIPLIED=$(( (${MEMORY_AVAIABLE} - 256*1024*1024) / 100 * 15 ))
    if [[ $METRICS_MEMORY_MULTIPLIED -lt $((128*1024*1024)) ]]; then
        METRICS_MEMORY_MULTIPLIED=$((128*1024*1024))
    fi
fi
sed -i "s/ENV_METRICS_MEMORY_MULTIPLIED/${METRICS_MEMORY_MULTIPLIED}/" /tmp/ssm.ini

# Orchestrator
if [[ "${ORCHESTRATOR_ENABLED}" = "true" ]]; then
    sed -i "s/autostart = false/autostart = true/" /tmp/ssm.ini
    sed "s/orc_client_user/${ORCHESTRATOR_USER:-orc_client_user}/" /etc/orchestrator.conf.json > /tmp/orchestrator.conf.json
    sed -i "s/orc_client_password/${ORCHESTRATOR_PASSWORD:-orc_client_password}/" /tmp/orchestrator.conf.json
    cat /tmp/orchestrator.conf.json > /etc/orchestrator.conf.json
    rm -rf /tmp/orchestrator.conf.json
fi

# Cron
sed "s/^INTERVAL=.*/INTERVAL=${QUERIES_RETENTION:-8}/" /etc/cron.daily/purge-qan-data > /tmp/purge-qan-data
cat /tmp/purge-qan-data > /etc/cron.daily/purge-qan-data
rm -rf /tmp/purge-qan-data

# HTTP basic auth
if [ -n "${SERVER_PASSWORD}" -a -z "${UPDATE_MODE}" ]; then
	SERVER_USER=${SERVER_USER:-ssm}
	cat > /srv/update/ssm-manage.yml <<-EOF
		users:
		- username: "${SERVER_USER//\"/\"}"
		  password: "${SERVER_PASSWORD//\"/\"}"
	EOF
	ssm-configure -skip-prometheus-reload true -grafana-db-path /var/lib/grafana/grafana.db || :
fi

# copy SSL, follow links
pushd /etc/nginx >/dev/null
    if [ -s ssl/server.crt ]; then
        cat ssl/server.crt  > /srv/nginx/certificate.crt
    fi
    if [ -s ssl/server.key ]; then
        cat ssl/server.key  > /srv/nginx/certificate.key
    fi
    if [ -s ssl/dhparam.pem ]; then
        cat ssl/dhparam.pem > /srv/nginx/dhparam.pem
    fi
popd >/dev/null

migrate_from_pmm() {
    local mysql_pid=
    /usr/sbin/mysqld --user=mysql --basedir=/usr --datadir=/var/lib/mysql --plugin-dir=/usr/lib64/mysql/plugin --pid-file=/var/lib/mysql/mysqld.pid --socket=/var/lib/mysql/mysql.sock & mysql_pid=$!

    # Wait for mysql to start
    sleep 30

    # Migrate mysql to mariadb
    mariadb-upgrade

    # Migrate database 'pmm'
    mysqldump -R pmm > /tmp/pmm.sql
    mysql --execute="CREATE DATABASE IF NOT EXISTS ssm;"
    mysql ssm < /tmp/pmm.sql

    # Migrate database 'pmm-managed'
    mysqldump -R pmm-managed > /tmp/pmm-managed.sql
    mysql --execute="CREATE DATABASE IF NOT EXISTS \`ssm-managed\`;"
    mysql ssm-managed < /tmp/pmm-managed.sql

    # Migrate database data
    mysql --database="ssm-managed" --execute="UPDATE nodes SET \`type\` = 'ssm-server', name = 'SSM Server' WHERE \`type\` = 'pmm-server';"

    kill $mysql_pid
}

migrate_from_ssm() {
    local mysql_pid=
    /usr/sbin/mysqld --user=mysql --basedir=/usr --datadir=/var/lib/mysql --plugin-dir=/usr/lib64/mysql/plugin --pid-file=/var/lib/mysql/mysqld.pid --socket=/var/lib/mysql/mysql.sock & mysql_pid=$!

    # Wait for mariadb to start
    sleep 30

    # Migrate old mariadb
    mariadb-upgrade

    kill $mysql_pid
}

# Upgrade
if [ -f /var/lib/grafana/PERCONA_DASHBOARDS_VERSION ] && [ -f /usr/share/ssm-dashboards/VERSION ] && [[ "$(cat /usr/share/ssm-dashboards/VERSION)" > "$(cat /var/lib/grafana/PERCONA_DASHBOARDS_VERSION)" ]]; then
    chown -R mysql:mysql /var/lib/mysql
    chown -R ssm:ssm /opt/consul-data
    chown -R ssm:ssm /opt/prometheus/data
    chown -R grafana:grafana /var/lib/grafana

    # Check if it's a upgrade from PMM
    if [[ -d /var/lib/grafana/plugins/pmm-app ]]; then
        migrate_from_pmm
        mv /var/lib/grafana/plugins/pmm-app /tmp/pmm-app
    else
        migrate_from_ssm
    fi
fi

cat /tmp/ssm.ini > /etc/supervisord.d/ssm.ini
rm -rf /tmp/ssm.ini
# Start supervisor in foreground
if [ -z "${UPDATE_MODE}" ]; then
    exec supervisord -n -c /etc/supervisord.conf
fi
