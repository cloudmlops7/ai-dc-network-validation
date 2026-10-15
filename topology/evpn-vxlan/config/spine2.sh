#!/bin/sh

ip addr replace 10.0.12.2/30 dev eth1
ip addr replace 10.0.22.2/30 dev eth2
ip addr replace 2.2.2.2/32 dev lo

ip link set eth1 up
ip link set eth2 up
