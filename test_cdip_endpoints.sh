#!/bin/bash
# Test script for CDIP nearshore buoy endpoints
# Tests all three working endpoint types for Hawaiian stations
# Usage: bash test_cdip_endpoints.sh

set -e

STATIONS=(225 106 249 239)
NDBC_IDS=(51207 51201 51214 51213)
STATION_NAMES=("Kaneohe Bay" "Waimea Bay" "Pauwela/Maui" "Barbers Point/Lanai")

echo "=========================================="
echo "CDIP Nearshore Buoy Endpoint Testing"
echo "Date: $(date -u +%Y-%m-%d_%H:%M:%S_UTC)"
echo "=========================================="
echo ""

# Test 1: THREDDS File Server
echo "TEST 1: THREDDS File Server (NetCDF)"
echo "Endpoint: https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/{station}p1_rt.nc"
echo ""

for i in "${!STATIONS[@]}"; do
    station=${STATIONS[$i]}
    name=${STATION_NAMES[$i]}
    url="https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/${station}p1_rt.nc"

    echo -n "  Station $station ($name): "
    status=$(curl -s -o /dev/null -w "%{http_code}" -I "$url")

    if [ "$status" = "200" ]; then
        size=$(curl -s -I "$url" | grep -i "content-length" | awk '{print $2}' | tr -d '\r')
        echo "OK (HTTP $status, Size: ~${size} bytes)"
    else
        echo "FAILED (HTTP $status)"
    fi
done

echo ""
echo "--------"
echo ""

# Test 2: PacIOOS ERDDAP JSON
echo "TEST 2: PacIOOS ERDDAP (JSON format)"
echo "Endpoint: https://pae-paha.pacioos.hawaii.edu/erddap/tabledap/cdip_wave_agg.json?station_id={station}&orderByMax(time)=1"
echo ""

for i in "${!STATIONS[@]}"; do
    station=${STATIONS[$i]}
    name=${STATION_NAMES[$i]}
    url="https://pae-paha.pacioos.hawaii.edu/erddap/tabledap/cdip_wave_agg.json?station_id=${station}&orderByMax(time)=1"

    echo -n "  Station $station ($name): "

    # Use timeout to avoid hanging
    response=$(timeout 10 curl -s "$url" 2>/dev/null || echo "TIMEOUT")

    if [ "$response" = "TIMEOUT" ]; then
        echo "TIMEOUT"
    elif echo "$response" | grep -q "station_id"; then
        row_count=$(echo "$response" | grep -o '"rows"' | wc -l)
        echo "OK (JSON received)"
    else
        echo "FAILED (No valid JSON)"
    fi
done

echo ""
echo "--------"
echo ""

# Test 3: NDBC Real-Time Text
echo "TEST 3: NDBC Real-Time Text (FM-13 format)"
echo "Endpoint: https://www.ndbc.noaa.gov/data/realtime2/{ndbc_id}.txt"
echo ""

for i in "${!STATIONS[@]}"; do
    station=${STATIONS[$i]}
    ndbc_id=${NDBC_IDS[$i]}
    name=${STATION_NAMES[$i]}
    url="https://www.ndbc.noaa.gov/data/realtime2/${ndbc_id}.txt"

    echo -n "  Station $station (NDBC $ndbc_id, $name): "

    status=$(curl -s -o /dev/null -w "%{http_code}" -I "$url")

    if [ "$status" = "200" ]; then
        echo "OK (HTTP $status)"
    else
        echo "FAILED (HTTP $status)"
    fi
done

echo ""
echo "=========================================="
echo "Testing complete"
echo "=========================================="
echo ""
echo "SUMMARY:"
echo "  - THREDDS: Primary endpoint for NetCDF files (full spectral data)"
echo "  - PacIOOS: JSON/CSV format, better for lightweight clients"
echo "  - NDBC: Simple text format, 30-min update cadence"
echo ""
echo "See CDIP_WORKING_ENDPOINTS.md for details and configuration"
