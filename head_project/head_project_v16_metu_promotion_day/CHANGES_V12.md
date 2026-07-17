# Changes v12

- Preserved the user-updated tilt limits: 75 to 120 degrees.
- Replaced fixed-step pan/tilt motion with a non-blocking acceleration profile.
- Added configurable pan/tilt maximum speed, acceleration and 20 ms update period.
- Increased the default gesture count from 2 to 3 on RP2350, Pi API, MANUAL and ROS service paths.
- Increased NOD and CELEBRATE tilt range to +/-10 degrees.
- Made LOOK_AROUND use the full mechanically reachable pan range calculated from servo limits and gear ratio.
- Increased DANCE/DAISY_DANCE to pan +/-30 degrees and tilt +/-9 degrees.
- Increased GREET to pan +/-35 degrees and nod +/-9 degrees.
- Increased DAISY_DANCE arm amplitude from 25 to 35 degrees.
- Corrected the Raspberry Pi status-panel pan direction to match the RP2350 configuration.
