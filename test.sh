#!/bin/bash

# Define the number of parallel processes you want to run
NUM_PROCESSES=50  # For example, 5 parallel processes

# Infinite loop to keep launching Python scripts
while true; do
  for ((i=0; i<NUM_PROCESSES; i++)); do
    python -m src.main &
  done
  wait  # Wait for all background processes to complete before the next iteration
  # Optionally add a small delay to control the rate of process launches
  sleep 2
done
