#!/bin/bash
#
# Generate a list of 50 category names (cat000001 to cat000050)
# One category per line, to be used as queue input for Condor
#

for i in $(seq 1 50); do
    printf "cat%06d\n" $i
done
