#!/bin/bash

set -o errexit

# pmm-managed-init validates environment variables.
pmm-managed-init

# init /srv if necessary: k8s, docker attached new/empty volume
if [[ $(ls -A /srv --ignore=lost+found | wc -l) -eq 0 ]]; then
    time ansible-playbook -v --tags "srv_init" \
        /usr/share/pmm-server/ansible/pmm2/main.yml \
        /usr/share/pmm-server/ansible/pmm2/post-build-actions.yml \
        /usr/share/pmm-update/ansible/playbook/tasks/init.yml \
        /usr/share/pmm-update/ansible/playbook/tasks/update.yml
fi

# Start supervisor in foreground
exec supervisord -n -c /etc/supervisord.conf
