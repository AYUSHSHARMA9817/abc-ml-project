#!/bin/bash

# Array of files
files=(./blif_files/*.blif)

mkdir -p results

for file in "${files[@]}"; do
    filename=$(basename "$file")
    design_name="${filename%.*}"
    echo "Processing $design_name..."

    # Create result folder
    mkdir -p "results/$design_name"

    # Reset cuts_qor.csv
    rm -f cuts_qor.csv
    echo "heuristic_name,area,delay,cuts_processed" > cuts_qor.csv

    # Run for dominance default
    ./abc -c "read_blif $file; strash; read_genlib genlib.genlib; map; print_stats" > /dev/null
    
    # Run for volume
    ABC_CUT_HEURISTIC=volume ./abc -c "read_blif $file; strash; read_genlib genlib.genlib; map; print_stats" > /dev/null

    # Run for random
    ABC_CUT_HEURISTIC=random ./abc -c "read_blif $file; strash; read_genlib genlib.genlib; map; print_stats" > /dev/null

    # Move output files
    mv cuts_all_features.csv "results/$design_name/"
    mv cuts_survivors.csv "results/$design_name/"
    mv cuts_qor.csv "results/$design_name/"
done

echo "All complete!"
