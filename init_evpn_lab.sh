#!/bin/bash
set -e

echo "Initializing EVPN-VXLAN underlay..."

docker exec clab-evpnvxlan-spine1 sh /opt/spine1.sh
docker exec clab-evpnvxlan-spine2 sh /opt/spine2.sh
docker exec clab-evpnvxlan-leaf1 sh /opt/leaf1.sh
docker exec clab-evpnvxlan-leaf2 sh /opt/leaf2.sh

echo "Underlay interface initialization complete."
echo "Configuring overlay hosts..."

docker exec clab-evpnvxlan-host1 ip addr replace 192.168.10.11/24 dev eth1
docker exec clab-evpnvxlan-host1 ip link set eth1 up

docker exec clab-evpnvxlan-host2 ip addr replace 192.168.10.12/24 dev eth1
docker exec clab-evpnvxlan-host2 ip link set eth1 up
