#!/bin/sh

ip addr replace 10.0.11.1/30 dev eth1
ip addr replace 10.0.12.1/30 dev eth2
ip addr replace 11.11.11.11/32 dev lo

ip link set eth1 up
ip link set eth2 up
# EVPN/VXLAN overlay

if ! ip link show br100 >/dev/null 2>&1; then
    ip link add br100 type bridge
fi
ip link set br100 up

if ! ip link show vxlan10100 >/dev/null 2>&1; then
    ip link add vxlan10100 type vxlan id 10100 \
        local 11.11.11.11 dstport 4789 nolearning
fi

ip link set vxlan10100 master br100
ip link set vxlan10100 up

ip link set eth3 master br100
ip link set eth3 up
