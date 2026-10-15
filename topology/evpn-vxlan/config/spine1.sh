#!/bin/sh

ip addr replace 10.0.11.2/30 dev eth1
ip addr replace 10.0.21.2/30 dev eth2
ip addr replace 1.1.1.1/32 dev lo

ip link set eth1 up
ip link set eth2 up
