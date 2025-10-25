#!/bin/sh
set -e

# Determine backup pool based on active pool
if [ "$ACTIVE_POOL" = "blue" ]; then
    export BACKUP_POOL="green"
else
    export BACKUP_POOL="blue"
fi

echo "Active Pool: $ACTIVE_POOL"
echo "Backup Pool: $BACKUP_POOL"

# Substitute environment variables in nginx config template
envsubst '${ACTIVE_POOL} ${BACKUP_POOL}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Verify the generated config
echo "Generated Nginx configuration:"
cat /etc/nginx/nginx.conf

# Test nginx configuration
nginx -t

# Start nginx in foreground
exec nginx -g 'daemon off;'